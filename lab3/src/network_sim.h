#ifndef NETWORK_SIM_H
#define NETWORK_SIM_H

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <sys/types.h>
#include <sys/socket.h>
#endif

#include <cstddef>
#include <cstdint>

// 网络模拟配置
struct SimConfig {
    double packet_loss_prob = 0.0;  // 数据包丢失概率
    double ack_loss_prob    = 0.0;  // ACK 包丢失概率
    double corrupt_prob     = 0.0;  // 数据包损坏概率
    int    delay_ms         = 0;    // 最大额外延迟（毫秒）
};

// 模拟发送：可能丢弃、损坏或延迟数据包
// 返回 true 表示成功发送（未丢弃），false 表示被丢弃
bool simulate_send(int sockfd, const void* buf, size_t len,
                   const sockaddr* dest, socklen_t destlen,
                   const SimConfig& cfg, bool is_ack);

// 模拟接收：直接调用 recvfrom（损坏通过校验和在应用层检测）
// 返回接收到的字节数，出错返回 -1
ssize_t simulate_recv(int sockfd, void* buf, size_t len,
                      sockaddr* src, socklen_t* srclen,
                      const SimConfig& cfg, bool is_ack);

#endif // NETWORK_SIM_H
