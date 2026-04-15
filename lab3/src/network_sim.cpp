#include "network_sim.h"

#include <cstdlib>
#include <cstring>
#include <iostream>
#include <thread>
#include <chrono>
#include <vector>

#ifdef _WIN32
#include <winsock2.h>
#else
#include <sys/socket.h>
#endif

// 生成 [0, 1] 之间的随机概率
static double random_prob() {
    return static_cast<double>(rand()) / RAND_MAX;
}

bool simulate_send(int sockfd, const void* buf, size_t len,
                   const sockaddr* dest, socklen_t destlen,
                   const SimConfig& cfg, bool is_ack) {
    double loss_prob = is_ack ? cfg.ack_loss_prob : cfg.packet_loss_prob;
    double r = random_prob();

    // 模拟丢包
    if (r < loss_prob) {
        if (is_ack) {
            std::cout << "[SIM] 丢弃 ACK" << std::endl;
        } else {
            std::cout << "[SIM] 丢弃数据包" << std::endl;
        }
        return false;
    }

    // 准备可变副本，以便损坏时修改
    std::vector<char> buffer(static_cast<const char*>(buf),
                             static_cast<const char*>(buf) + len);

    // 模拟数据包损坏：随机翻转一个比特位
    if (r < loss_prob + cfg.corrupt_prob) {
        size_t byte_idx = rand() % len;
        int bit_idx = rand() % 8;
        buffer[byte_idx] ^= (1 << bit_idx);
        std::cout << "[SIM] 损坏数据包/ACK 字节 " << byte_idx << " 比特 " << bit_idx << std::endl;
    }

    // 模拟延迟
    if (cfg.delay_ms > 0) {
        int delay = rand() % (cfg.delay_ms + 1);
        std::this_thread::sleep_for(std::chrono::milliseconds(delay));
    }

    ssize_t sent = sendto(sockfd, buffer.data(), buffer.size(), 0, dest, destlen);
    return sent == static_cast<ssize_t>(buffer.size());
}

ssize_t simulate_recv(int sockfd, void* buf, size_t len,
                      sockaddr* src, socklen_t* srclen,
                      const SimConfig& /*cfg*/, bool /*is_ack*/) {
    return recvfrom(sockfd, static_cast<char*>(buf), len, 0, src, srclen);
}
