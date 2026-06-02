# OTA 故障注入测试框架

## 概述

本文档说明如何使用故障注入版本的OTA工具来测试系统的恢复能力。

## 文件说明

### 1. `ymodem_fault_injector.py`
增强的YMODEM实现，支持各种网络故障模拟。

**主要组件：**

- `FaultConfig` 类：故障配置对象
  - `packet_faults`: 按包号配置故障
  - `ack_loss_probability`: ACK丢包概率 (0.0-1.0)
  - `ack_delay_ms`: ACK延迟时间 (毫秒)
  - `duplicate_ack_probability`: 重复ACK概率
  - `data_corruption_probability`: 数据损坏概率
  - `scenario`: 预设故障场景

- `Ymodem` 类：
  - 基于原始 `ymodem.py` 扩展
  - 自动应用预设场景
  - 收集故障统计信息
  - 返回详细的故障注入统计

### 2. `ota_cli_test.py`
测试版CLI工具，支持交互式故障配置。

**功能：**
- 连接到MQTT broker（与生产版相同）
- 交互式选择故障场景或手动配置
- 收集并显示故障统计
- 完整的错误恢复演示

## 使用指南

### 快速开始

```bash
python3 src/ota_cli_test.py
```

### 工作流程

1. **输入MQTT配置**
   - Broker地址（默认：210.0.159.242）
   - 端口（默认：1883）
   - 用户名/密码

2. **输入发布主题**
   - 格式：`/ota/upgrade/<xxx>/<xxx>`
   - 默认：`/ota/upgrade/tc42/atc01`

3. **选择故障场景**
   ```
   Available preset scenarios:
     1. high_latency   - 高延迟 (500-2000ms)
     2. packet_loss    - 随机丢包 (~15%)
     3. intermittent   - 间歇性问题 (5% 丢包 + 延迟)
     4. corrupted_data - 数据损坏 (10%)
     5. duplicate_acks - 重复ACK (20%)
     0. custom         - 手动配置
   ```

4. **传输与监控**
   - 按 Ctrl+Q 中止传输
   - 实时查看故障注入日志
   - 传输完成后显示统计信息

## 预设场景详解

### 1. 高延迟 (high_latency)
模拟网络延迟很高的场景
- **效果**：所有ACK响应增加 500-2000ms 延迟
- **用途**：测试超时重试逻辑
- **预期行为**：正常完成，但重试次数较多

### 2. 丢包 (packet_loss)
模拟随机丢失ACK的场景
- **效果**：随机丢弃约 15% 的ACK
- **用途**：测试NAK/重试机制
- **预期行为**：需要多次重试才能完成

### 3. 间歇性问题 (intermittent)
结合延迟和丢包的现实场景
- **效果**：5% 丢包率 + 100-500ms 随机延迟
- **用途**：完整的网络可靠性测试
- **预期行为**：频繁重试但最终应成功

### 4. 数据损坏 (corrupted_data)
模拟数据被破坏的极端情况
- **效果**：约 10% 的数据包会翻转几个比特
- **用途**：测试CRC校验和错误恢复
- **预期行为**：低概率成功（需要更强的错误检测）

### 5. 重复ACK (duplicate_acks)
模拟接收方发送多次ACK的场景
- **效果**：约 20% 的ACK会发送两次
- **用途**：测试状态机对重复消息的处理
- **预期行为**：正常完成，忽略额外的ACK

## 手动配置示例

```
Select scenario (0-5) [default: 0 - no faults]: 0

=== Custom Fault Configuration ===
ACK loss probability (0.0-1.0, default 0.0): 0.1
ACK delay in ms (default 0): 500
Duplicate ACK probability (0.0-1.0, default 0.0): 0.0
Data corruption probability (0.0-1.0, default 0.0): 0.0

Custom fault config applied:
  ACK loss: 0.1
  ACK delay: 500ms
  Duplicate ACK: 0.0
  Data corruption: 0.0
```

## 故障注入统计

传输完成后，会显示以下统计信息：

```
[FAULT INJECTION STATS]
  acks_dropped: 15
  packets_delayed: 158
  packets_corrupted: 0
  duplicate_acks_sent: 32
  total_retries: 18
```

| 指标 | 说明 |
|------|------|
| `acks_dropped` | 被故意丢弃的ACK数 |
| `packets_delayed` | 被延迟的包数 |
| `packets_corrupted` | 被损坏的数据包数 |
| `duplicate_acks_sent` | 发送的重复ACK数 |
| `total_retries` | 因超时进行的重试总数 |

## 日志格式

### 故障注入日志
```
[FAULT] Packet 158: ACK dropped (random)
[FAULT] Packet 151: Delaying ACK by 867ms
[FAULT] Duplicate ACK will be sent for packet 82
```

### 接收日志
```
[RECV] Received from /ota/progress/tc42/atc01: b'\x06'
```

### 重试日志
```
Sending data packet 158 (attempt 7/10)...
Timeout waiting for ACK/NAK for packet 158, retrying...
```

## 测试场景组合

### 场景1：弱网验收测试
```
场景：intermittent
预期：3-5分钟内通过
目标：验证系统在现实网络条件下的表现
```

### 场景2：压力测试
```
启用：
- ACK loss: 0.3 (30%)
- ACK delay: 2000ms
- Duplicate ACK: 0.1
预期：仍能最终完成
目标：验证极端条件下的状态机稳定性
```

### 场景3：数据完整性验证
```
启用：
- Data corruption: 0.05
- ACK loss: 0.1
预期：通过（需要强CRC校验）
目标：验证CRC和重试能否保护数据
```

## 与生产版本的比较

| 功能 | ota_cli.py | ota_cli_test.py |
|------|-----------|-----------------|
| MQTT通信 | ✓ | ✓ |
| 基本OTA传输 | ✓ | ✓ |
| 故障注入 | ✗ | ✓ |
| 交互式配置 | 基础 | 完整 |
| 统计信息 | 无 | 详细 |
| 预设场景 | N/A | 5种 |

## 故障排查指南

### ACK完全没收到
```
[FAULT] Packet 158: ACK dropped (random)
...
[FAULT] Packet 158: ACK dropped (random)
...
Timeout waiting for ACK/NAK for packet 158, retrying...
```
**原因**：ACK丢包率过高，超过重试次数  
**解决**：降低丢包概率或增加重试次数

### 频繁重试但最终成功
```
Sending data packet 50 (attempt 1/10)...
Timeout waiting for ACK/NAK for packet 50, retrying...
Sending data packet 50 (attempt 2/10)...
...
Sending data packet 50 (attempt 5/10)...
/ota/progress/tc42/atc01 recv: b'\x06'
```
**原因**：网络延迟达到或超过超时时间  
**改进**：在配置中增大timeout参数或降低延迟

### 异常高重试次数
```
[FAULT INJECTION STATS]
  total_retries: 500
```
**原因**：故障配置造成的系统压力过大  
**建议**：逐步增加故障强度进行测试

## 开发者指南

### 添加自定义故障

编辑 `ymodem_fault_injector.py`:

```python
def _custom_fault_handler(self, packet_num: int):
    # 自定义故障逻辑
    if packet_num == 100:  # 在包100注入特定故障
        print(f"[FAULT] Custom fault at packet {packet_num}")
        return True
    return False
```

### 添加更详细的日志

在 `wait_for()` 函数中添加：

```python
print(f"[DEBUG] Packet {packet_num}: attempt {current_attempt}, "
      f"elapsed_time={elapsed_time}ms, queue_size={recv_queue.qsize()}")
```

## 参考资源

- YMODEM协议文档
- MQTT QoS 说明
- 网络超时处理最佳实践

## 注意事项

1. **测试环境隔离**：
   - 使用测试用固件（不要用生产固件）
   - 确保MCU连接正常

2. **逐步提升难度**：
   - 从低故障率开始测试
   - 逐步增加难度评估系统容错能力

3. **日志收集**：
   - 重定向输出到文件以便分析
   - 记录异常情况用于改进

```bash
python3 src/ota_cli_test.py > test_log_$(date +%Y%m%d_%H%M%S).txt 2>&1
```

## 许可证

与主项目相同
