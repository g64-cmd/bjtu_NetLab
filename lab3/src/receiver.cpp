#include <iostream>
#include <fstream>
#include <cstring>
#include <cstdlib>
#include <ctime>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#endif

#include "packet.h"
#include "network_sim.h"

// 发送 ACK 包
static void send_ack(int sockfd, const sockaddr_in& dest, int ack_num, const SimConfig& cfg) {
    Packet ack_pkt{};
    ack_pkt.ack_num = ack_num;
    ack_pkt.is_ack = 1;
    ack_pkt.data_len = 0;
    ack_pkt.checksum = compute_packet_checksum(ack_pkt);
    simulate_send(sockfd, &ack_pkt, HEADER_SIZE,
                  reinterpret_cast<const sockaddr*>(&dest), sizeof(dest), cfg, true);
    std::cout << "[接收] 发送 ACK 确认号=" << ack_num << std::endl;
}

int main(int argc, char* argv[]) {
    if (argc != 7) {
        std::cerr << "用法: " << argv[0]
                  << " <端口> <输出文件>"
                  << " <丢包概率> <ACK丢失概率> <损坏概率> <延迟毫秒>" << std::endl;
        return 1;
    }

    int port = std::atoi(argv[1]);
    const char* output_file = argv[2];

    SimConfig cfg;
    cfg.packet_loss_prob = std::atof(argv[3]);
    cfg.ack_loss_prob    = std::atof(argv[4]);
    cfg.corrupt_prob     = std::atof(argv[5]);
    cfg.delay_ms         = std::atoi(argv[6]);

    std::srand(static_cast<unsigned>(std::time(nullptr)));

#ifdef _WIN32
    // Windows 下初始化 Winsock
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        std::cerr << "WSAStartup 失败" << std::endl;
        return 1;
    }
#endif

    // 创建 UDP 套接字
    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) {
        std::cerr << "socket() 失败" << std::endl;
        return 1;
    }

    // 绑定本地地址
    sockaddr_in local_addr{};
    local_addr.sin_family = AF_INET;
    local_addr.sin_port = htons(port);
    local_addr.sin_addr.s_addr = INADDR_ANY;

    if (bind(sockfd, reinterpret_cast<const sockaddr*>(&local_addr), sizeof(local_addr)) < 0) {
        std::cerr << "bind() 失败" << std::endl;
        return 1;
    }

    // 打开输出文件
    std::ofstream outfile(output_file, std::ios::binary);
    if (!outfile) {
        std::cerr << "无法打开输出文件: " << output_file << std::endl;
        return 1;
    }

    int expected_seq_num = 0; // 期望接收的下一个序列号
    bool finished = false;

    sockaddr_in sender_addr{};
    socklen_t sender_len = sizeof(sender_addr);

    while (!finished) {
        Packet pkt{};
        ssize_t n = simulate_recv(sockfd, &pkt, sizeof(Packet),
                                  reinterpret_cast<sockaddr*>(&sender_addr), &sender_len, cfg, false);
        if (n <= 0) continue;

        // 校验和错误：发送重复 ACK
        if (!verify_packet_checksum(pkt)) {
            std::cout << "[接收] 收到损坏的数据包，发送重复 ACK 确认号="
                      << (expected_seq_num - 1 + MAX_SEQ_NUM) % MAX_SEQ_NUM << std::endl;
            send_ack(sockfd, sender_addr, (expected_seq_num - 1 + MAX_SEQ_NUM) % MAX_SEQ_NUM, cfg);
            continue;
        }

        // EOF 结束标记
        if (pkt.is_ack == 2) {
            std::cout << "[接收] 收到 EOF，传输完成" << std::endl;
            send_ack(sockfd, sender_addr, expected_seq_num == 0 ? MAX_SEQ_NUM - 1 : expected_seq_num - 1, cfg);
            finished = true;
            continue;
        }

        int seq = static_cast<int>(pkt.seq_num);
        if (seq == expected_seq_num) {
            // 收到期望的分组：写入文件并发送 ACK
            std::cout << "[接收] 收到期望分组 序列号=" << seq << " 长度=" << pkt.data_len << std::endl;
            if (pkt.data_len > 0) {
                outfile.write(pkt.data, pkt.data_len);
            }
            expected_seq_num = (expected_seq_num + 1) % MAX_SEQ_NUM;
            send_ack(sockfd, sender_addr, seq, cfg);
        } else {
            // 乱序分组：丢弃并发送重复 ACK
            std::cout << "[接收] 乱序分组 序列号=" << seq << " 期望=" << expected_seq_num
                      << "，发送重复 ACK 确认号="
                      << (expected_seq_num - 1 + MAX_SEQ_NUM) % MAX_SEQ_NUM << std::endl;
            send_ack(sockfd, sender_addr, (expected_seq_num - 1 + MAX_SEQ_NUM) % MAX_SEQ_NUM, cfg);
        }
    }

    outfile.close();

#ifdef _WIN32
    closesocket(sockfd);
    WSACleanup();
#else
    close(sockfd);
#endif

    std::cout << "[接收] 文件已保存到 " << output_file << std::endl;
    return 0;
}
