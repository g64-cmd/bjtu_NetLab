#ifndef PACKET_H
#define PACKET_H

#include <cstdint>
#include <cstddef>

// 数据包配置常量
constexpr int PACKET_SIZE = 1024;      // 最大负载字节数
constexpr int MAX_SEQ_NUM = 256;       // 序列号空间大小
constexpr int HEADER_SIZE = 13;        // 包头大小（约等于 sizeof(Packet) - payload）

#pragma pack(push, 1)
struct Packet {
    uint32_t seq_num;      // 序列号
    uint32_t ack_num;      // 确认号
    uint16_t data_len;     // 负载长度（纯 ACK 包为 0）
    uint16_t checksum;     // 校验和（覆盖包头 + 负载）
    uint8_t  is_ack;       // 1 = ACK 包, 2 = EOF 结束标记, 0 = 数据包
    char     data[PACKET_SIZE];
};
#pragma pack(pop)

// 计算 Internet 校验和（16 位反码求和）
inline uint16_t calculate_checksum(const void* data, size_t len) {
    const uint16_t* buf = reinterpret_cast<const uint16_t*>(data);
    uint32_t sum = 0;

    while (len > 1) {
        sum += *buf++;
        len -= 2;
    }

    if (len == 1) {
        sum += *reinterpret_cast<const uint8_t*>(buf);
    }

    while (sum >> 16) {
        sum = (sum & 0xFFFF) + (sum >> 16);
    }

    return static_cast<uint16_t>(~sum);
}

// 计算数据包校验和（计算时将 checksum 字段视为 0）
inline uint16_t compute_packet_checksum(const Packet& pkt) {
    Packet temp = pkt;
    temp.checksum = 0;
    return calculate_checksum(&temp, HEADER_SIZE + pkt.data_len);
}

// 验证数据包校验和
inline bool verify_packet_checksum(const Packet& pkt) {
    return compute_packet_checksum(pkt) == pkt.checksum;
}

#endif // PACKET_H
