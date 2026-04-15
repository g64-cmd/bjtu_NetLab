# Lab 3: Go-Back-N Reliable Data Transfer

## Objective

Implement a reliable file transfer application over UDP using the Go-Back-N (GBN) protocol in C/C++.

## Project Structure

```
lab3/
├── src/
│   ├── packet.h              # Shared packet structure and checksum
│   ├── network_sim.h         # Unreliable network simulation interface
│   ├── network_sim.cpp       # Drop/corrupt/delay simulation
│   ├── sender.cpp            # GBN sender
│   └── receiver.cpp          # GBN receiver
├── test/
│   ├── small.txt             # Small text test file
│   └── image.png             # Binary test file
├── Makefile
└── README.md
```

## Features

**Go-Back-N Sender:**
- Sliding window with configurable window size `N`
- Cumulative ACKs
- Single timer for the oldest unacknowledged packet
- Timeout-based retransmission of all unacknowledged packets in the window

**Go-Back-N Receiver:**
- In-order delivery only
- Discards out-of-order packets
- Sends cumulative ACK for the highest in-order packet received

**Unreliable Network Simulation:**
- Configurable packet loss probability
- Configurable ACK loss probability
- Configurable packet corruption probability
- Configurable random delay

## Supported Protocol Behaviors

| Component | Behavior |
|-----------|----------|
| Sender Window | Slides forward on cumulative ACK |
| Sender Timer | Single timer for `base`; restart on ACK advance |
| Timeout | Retransmit all packets from `base` to `next_seq_num - 1` |
| Receiver ACK | ACK highest in-order `seq_num` received |
| Out-of-order | Discard packet and send duplicate ACK |
| Corruption | Detected by checksum; treated as lost packet |

## Requirements

- C++17 compiler (g++ / clang++)
- POSIX sockets (Linux / WSL / macOS) or Winsock2 (Windows)
- `make` (optional, for Makefile builds)

## Compile

Using `make`:

```bash
cd lab3
make
```

Manual compilation:

```bash
cd lab3
g++ -std=c++17 -Wall -O2 -o build/sender src/sender.cpp src/network_sim.cpp
g++ -std=c++17 -Wall -O2 -o build/receiver src/receiver.cpp src/network_sim.cpp
```

## Run

**Receiver:**

```bash
./build/receiver <port> <output_file> <pkt_loss_prob> <ack_loss_prob> <corrupt_prob> <delay_ms>
```

**Sender:**

```bash
./build/sender <receiver_ip> <receiver_port> <input_file> <window_size> <timeout_ms> <pkt_loss_prob> <ack_loss_prob> <corrupt_prob> <delay_ms>
```

### Example

```bash
# Terminal 1: start receiver
./build/receiver 8080 received.txt 0 0 0 0

# Terminal 2: start sender
./build/sender 127.0.0.1 8080 test/small.txt 8 1000 0 0 0 0
```

## Testing

### 1. Basic Functional Test (No Loss)

```bash
./build/receiver 8080 received.txt 0 0 0 0
./build/sender 127.0.0.1 8080 test/small.txt 8 1000 0 0 0 0
```

Verify the output file matches the input:

```bash
diff test/small.txt received.txt
```

### 2. Packet Loss Test

```bash
./build/receiver 8080 received_loss.txt 0.2 0 0 0
./build/sender 127.0.0.1 8080 test/small.txt 8 1000 0.2 0 0 0
```

Observe retransmissions in sender output and verify file integrity with `diff`.

### 3. ACK Loss Test

```bash
./build/receiver 8080 received_ackloss.txt 0 0.3 0 0
./build/sender 127.0.0.1 8080 test/small.txt 8 1000 0 0.3 0 0
```

Observe timeouts and retransmissions; verify file integrity.

### 4. Corruption Test

```bash
./build/receiver 8080 received_corrupt.txt 0 0 0.3 0
./build/sender 127.0.0.1 8080 test/small.txt 8 1000 0 0 0.3 0
```

Observe duplicate ACKs and retransmissions; verify file integrity.

### 5. Binary File Test

```bash
./build/receiver 8080 received_image.png 0.1 0.1 0.05 50
./build/sender 127.0.0.1 8080 test/image.png 8 1000 0.1 0.1 0.05 50
```

Verify with:

```bash
diff test/image.png received_image.png
```

### 6. Performance Observation (Optional)

Compare transfer time with different window sizes on a large file:

```bash
# Window size 4
./build/sender 127.0.0.1 8080 test/large.txt 4 1000 0 0 0 0

# Window size 16
./build/sender 127.0.0.1 8080 test/large.txt 16 1000 0 0 0 0
```

## Implementation Details

### Packet Format

The `Packet` structure (defined in `packet.h`) contains:

| Field | Type | Description |
|-------|------|-------------|
| `seq_num` | `uint32_t` | Sequence number |
| `ack_num` | `uint32_t` | ACK number (used in ACK packets) |
| `data_len` | `uint16_t` | Payload length |
| `checksum` | `uint16_t` | Internet checksum over header + payload |
| `is_ack` | `uint8_t` | `1` = ACK, `2` = EOF, `0` = data |
| `data` | `char[1024]` | Payload buffer |

### Timer Management

Go-Back-N uses a single timer for the oldest unacknowledged packet (`base`):
- **Start** when the first packet in a window is sent (`base == next_seq_num`)
- **Restart** when `base` advances due to a new cumulative ACK
- **Stop** when all packets in the window are acknowledged (`base == next_seq_num`)
- On **timeout**, retransmit all unacknowledged packets and restart the timer

### Checksum

A 16-bit ones'-complement (Internet checksum) is computed over the entire packet with the `checksum` field set to `0`. The receiver recalculates and compares; mismatches indicate corruption.

### Network Simulation Integration

The simulation is implemented as wrapper functions (`simulate_send` / `simulate_recv`) in `network_sim.cpp`. They intercept UDP sends to probabilistically drop, corrupt, or delay packets and ACKs. This keeps the architecture simple without requiring a separate proxy process.
