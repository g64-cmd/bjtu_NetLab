#include <iostream>
#include <fstream>
#include <vector>
#include <cstring>
#include <cstdlib>
#include <ctime>
#include <chrono>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <sys/select.h>
#endif

#include "packet.h"
#include "network_sim.h"

// GBN 发送端状态
struct SenderState {
    int base = 0;                 // 窗口基地址（最早未确认的分组）
    int next_seq_num = 0;         // 下一个待发送的序列号
    int window_size = 8;          // 窗口大小 N
    int max_seq_num = MAX_SEQ_NUM;// 最大序列号
    bool timer_running = false;   // 定时器是否运行
    std::chrono::steady_clock::time_point timer_start; // 定时器启动时间
    int timeout_ms = 1000;        // 超时时间（毫秒）
    std::vector<Packet> window_packets; // 窗口内已发送的分组缓存
};

// 初始化发送端状态
static void init_sender(SenderState& state, int window_size, int timeout_ms) {
    state.base = 0;
    state.next_seq_num = 0;
    state.window_size = window_size;
    state.timer_running = false;
    state.timeout_ms = timeout_ms;
    state.window_packets.clear();
}

// 启动定时器
static void start_timer(SenderState& state) {
    state.timer_running = true;
    state.timer_start = std::chrono::steady_clock::now();
}

// 停止定时器
static void stop_timer(SenderState& state) {
    state.timer_running = false;
}

// 重启定时器
static void restart_timer(SenderState& state) {
    start_timer(state);
}

// 检查是否超时
static bool is_timeout(const SenderState& state) {
    if (!state.timer_running) return false;
    auto now = std::chrono::steady_clock::now();
    auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - state.timer_start).count();
    return elapsed >= state.timeout_ms;
}

// 计算模意义下的距离 (b - a) mod mod
static int seq_distance(int a, int b, int mod) {
    int d = b - a;
    if (d < 0) d += mod;
    return d;
}

// 发送单个数据包（经过网络模拟层）
static void send_packet(int sockfd, const sockaddr_in& dest, const Packet& pkt, const SimConfig& cfg, bool is_ack) {
    simulate_send(sockfd, &pkt, HEADER_SIZE + pkt.data_len,
                  reinterpret_cast<const sockaddr*>(&dest), sizeof(dest), cfg, is_ack);
}

int main(int argc, char* argv[]) {
    if (argc != 10) {
        std::cerr << "用法: " << argv[0]
                  << " <接收端IP> <接收端端口> <输入文件>"
                  << " <窗口大小> <超时毫秒>"
                  << " <丢包概率> <ACK丢失概率> <损坏概率> <延迟毫秒>" << std::endl;
        return 1;
    }

    const char* receiver_ip = argv[1];
    int receiver_port = std::atoi(argv[2]);
    const char* input_file = argv[3];
    int window_size = std::atoi(argv[4]);
    int timeout_ms = std::atoi(argv[5]);

    SimConfig cfg;
    cfg.packet_loss_prob = std::atof(argv[6]);
    cfg.ack_loss_prob    = std::atof(argv[7]);
    cfg.corrupt_prob     = std::atof(argv[8]);
    cfg.delay_ms         = std::atoi(argv[9]);

    std::srand(static_cast<unsigned>(std::time(nullptr)));

#ifdef _WIN32
    // Windows 下初始化 Winsock
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        std::cerr << "WSAStartup 失败" << std::endl;
        return 1;
    }
#endif

    // 读取输入文件
    std::ifstream infile(input_file, std::ios::binary);
    if (!infile) {
        std::cerr << "无法打开输入文件: " << input_file << std::endl;
        return 1;
    }
    std::vector<char> file_data((std::istreambuf_iterator<char>(infile)),
                                 std::istreambuf_iterator<char>());
    infile.close();
    size_t file_size = file_data.size();

    // 创建 UDP 套接字
    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) {
        std::cerr << "socket() 失败" << std::endl;
        return 1;
    }

    // 设置接收端地址
    sockaddr_in dest_addr{};
    dest_addr.sin_family = AF_INET;
    dest_addr.sin_port = htons(receiver_port);
    if (inet_pton(AF_INET, receiver_ip, &dest_addr.sin_addr) <= 0) {
        std::cerr << "无效的接收端 IP" << std::endl;
        return 1;
    }

    SenderState state;
    init_sender(state, window_size, timeout_ms);

    size_t next_chunk_offset = 0;
    bool all_data_sent = false;
    bool finished = false;

    sockaddr_in from_addr{};
    socklen_t from_len = sizeof(from_addr);

    while (!finished) {
        // 窗口未满且还有数据时，发送新分组
        while (seq_distance(state.base, state.next_seq_num, state.max_seq_num) < state.window_size
               && !all_data_sent) {
            Packet pkt{};
            pkt.seq_num = state.next_seq_num;
            pkt.is_ack = 0;

            size_t chunk_start = next_chunk_offset;
            size_t chunk_len = 0;
            if (chunk_start < file_size) {
                chunk_len = (file_size - chunk_start > PACKET_SIZE) ? PACKET_SIZE : (file_size - chunk_start);
                std::memcpy(pkt.data, file_data.data() + chunk_start, chunk_len);
            }
            pkt.data_len = static_cast<uint16_t>(chunk_len);
            pkt.checksum = compute_packet_checksum(pkt);

            send_packet(sockfd, dest_addr, pkt, cfg, false);
            std::cout << "[发送] 序列号=" << pkt.seq_num << " 长度=" << pkt.data_len << std::endl;

            // 如果窗口中第一个分组，启动定时器
            if (state.base == state.next_seq_num) {
                start_timer(state);
            }

            // 缓存分组用于重传
            if (state.window_packets.size() < static_cast<size_t>(state.window_size * 2)) {
                state.window_packets.push_back(pkt);
            }

            state.next_seq_num = (state.next_seq_num + 1) % state.max_seq_num;
            next_chunk_offset += chunk_len;

            if (chunk_start >= file_size) {
                all_data_sent = true;
            }
        }

        // 使用 select 等待 ACK 或超时
        fd_set readfds;
        FD_ZERO(&readfds);
        FD_SET(sockfd, &readfds);

        timeval tv{};
        if (state.timer_running) {
            auto now = std::chrono::steady_clock::now();
            auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - state.timer_start).count();
            long remaining = state.timeout_ms - elapsed;
            if (remaining < 0) remaining = 0;
            tv.tv_sec = remaining / 1000;
            tv.tv_usec = (remaining % 1000) * 1000;
        } else {
            tv.tv_sec = 1;
            tv.tv_usec = 0;
        }

        int ret = select(sockfd + 1, &readfds, nullptr, nullptr, &tv);

        if (ret > 0 && FD_ISSET(sockfd, &readfds)) {
            Packet ack_pkt{};
            ssize_t n = simulate_recv(sockfd, &ack_pkt, sizeof(Packet),
                                      reinterpret_cast<sockaddr*>(&from_addr), &from_len, cfg, true);
            if (n > 0) {
                if (!verify_packet_checksum(ack_pkt)) {
                    std::cout << "[发送] 收到损坏的 ACK，忽略" << std::endl;
                } else if (ack_pkt.is_ack) {
                    int ack_num = static_cast<int>(ack_pkt.ack_num);
                    int dist = seq_distance(state.base, ack_num, state.max_seq_num);
                    if (dist >= 0 && dist < state.window_size) {
                        std::cout << "[发送] 收到 ACK 确认号=" << ack_num << std::endl;
                        state.base = (ack_num + 1) % state.max_seq_num;
                        // 滑动窗口：移除已确认的分组缓存
                        while (!state.window_packets.empty()) {
                            int first_seq = static_cast<int>(state.window_packets.front().seq_num);
                            int d = seq_distance(first_seq, state.base, state.max_seq_num);
                            if (d > 0 && d < state.window_size * 2) {
                                state.window_packets.erase(state.window_packets.begin());
                            } else {
                                break;
                            }
                        }
                        if (state.base == state.next_seq_num) {
                            stop_timer(state);
                            if (all_data_sent) {
                                finished = true;
                            }
                        } else {
                            restart_timer(state);
                        }
                    } else {
                        std::cout << "[发送] 收到重复/过期的 ACK 确认号=" << ack_num << std::endl;
                    }
                }
            }
        }

        // 超时处理：重传窗口内所有未确认分组
        if (is_timeout(state)) {
            std::cout << "[发送] 超时！重传窗口基地址=" << state.base << std::endl;
            restart_timer(state);
            int count = seq_distance(state.base, state.next_seq_num, state.max_seq_num);
            for (int i = 0; i < count; ++i) {
                int seq = (state.base + i) % state.max_seq_num;
                for (const auto& pkt : state.window_packets) {
                    if (static_cast<int>(pkt.seq_num) == seq) {
                        send_packet(sockfd, dest_addr, pkt, cfg, false);
                        std::cout << "[发送] 重传 序列号=" << seq << std::endl;
                        break;
                    }
                }
            }
        }
    }

    // 发送 EOF 结束标记
    Packet eof_pkt{};
    eof_pkt.seq_num = state.next_seq_num;
    eof_pkt.is_ack = 2; // EOF 标记
    eof_pkt.data_len = 0;
    eof_pkt.checksum = compute_packet_checksum(eof_pkt);
    send_packet(sockfd, dest_addr, eof_pkt, cfg, false);
    std::cout << "[发送] 发送 EOF 结束标记" << std::endl;

#ifdef _WIN32
    closesocket(sockfd);
    WSACleanup();
#else
    close(sockfd);
#endif

    std::cout << "[发送] 传输完成" << std::endl;
    return 0;
}
