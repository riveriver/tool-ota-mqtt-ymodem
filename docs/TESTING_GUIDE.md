# OTA 故障注入测试框架快速入门

## 概述

本项目包含一个完整的YMODEM/MQTT OTA故障注入测试框架，用于验证系统在各种网络故障条件下的健壮性。

## 核心文件

| 文件 | 用途 |
|------|------|
| `ota_cli.py` | 生产版 - 正常OTA无故障注入 |
| `ota_cli_test.py` | 测试版 - 交互式单场景故障注入 |
| `ymodem_fault_injector.py` | 增强的YMODEM实现，支持故障模拟 |
| `ota_test_suite.py` | 自动化多场景测试套件 |
| `docs/FAULT_INJECTION_GUIDE.md` | 详细的测试文档 |

## 快速开始

### 方式一：交互式单场景测试（推荐新手）

```bash
python3 src/ota_cli_test.py
```

按照提示：
1. 输入MQTT服务器信息
2. 选择发布主题
3. 选择故障场景或手动配置参数
4. 系统自动注入故障并显示统计信息

### 方式二：自动化多场景测试集

```bash
python3 src/ota_test_suite.py
```

类型支持的操作：
- `all` - 运行所有9个预定义场景
- `1-5` - 运行场景1到5
- `2,4,6` - 运行指定的场景

## 预定义场景

| 场景 | 描述 | 用途 |
|------|------|------|
| 1 | 无故障基准 | 基线性能测试 |
| 2 | 高延迟 | 测试超时处理 |
| 3 | 轻度丢包(5%) | 基础重试测试 |
| 4 | 中等丢包(15%) | 正常网络性能 |
| 5 | 重型丢包(30%) | 极限条件 |
| 6 | 间歇性问题 | 真实网络模拟 |
| 7 | 重复ACK | 状态机鲁棒性 |
| 8 | 综合压力 | 完整压力测试 |
| 9 | 极限条件 | 最严苛测试 |

## 故障类型

### 支持的故障模式

1. **ACK丢失** (`ack_loss_probability`)
   - 模拟网络丢包
   - 触发重试机制

2. **ACK延迟** (`ack_delay_ms`)
   - 模拟高延迟网络
   - 延迟时间 ± 随机抖动

3. **重复ACK** (`duplicate_ack_probability`)
   - 模拟MQTT消息重复传送
   - 测试状态机处理

4. **数据损坏** (`data_corruption_probability`)
   - 模拟CRC错误
   - 需要强错误检测逻辑

5. **组合故障** (scenario)
   - 预设的现实场景组合

## 测试输出解析

### 实时日志

```
[FAULT] Packet 158: ACK dropped (random)        # 故障注入事件
[RECV] Received from /ota/progress/...: b'\x06' # 收到的响应
Timeout waiting for packet 158, retrying...      # 重试事件
```

### 最终统计

```
[FAULT INJECTION STATS]
  acks_dropped: 15              # 被丢弃的ACK数
  packets_delayed: 158          # 被延迟的包数
  packets_corrupted: 0          # 被损坏的数据包
  duplicate_acks_sent: 32       # 发送的重复ACK
  total_retries: 18             # 总重试次数
```

## 典型测试场景

### 场景A：验证基本重试机制
```bash
python3 src/ota_cli_test.py
# 选择 "3. packet_loss" (5% 丢包)
# 预期：多次重试后成功完成
```

### 场景B：压力测试系统容错能力
```bash
python3 src/ota_cli_test.py
# 选择 "0. custom"
# 配置：ACK loss 0.3, delay 1000ms
# 预期：应该在30-60秒内完成（有大量重试）
```

### 场景C：完全自动化回归测试
```bash
python3 src/ota_test_suite.py
# 选择 "all"
# 系统将运行全部9个场景并生成报告
```

## 测试报告

测试完成后，在 `test_reports/` 目录下生成JSON报告：

```json
{
  "timestamp": "2024-05-19T10:30:45.123456",
  "results": [
    {
      "scenario": "Scenario 1: No Faults",
      "success": true,
      "elapsed_time": 45.23,
      "stats": {
        "total_retries": 0,
        "acks_dropped": 0
      },
      "error": null,
      "timestamp": "2024-05-19T10:30:45.654321"
    },
    ...
  ]
}
```

## 故障排查

### 问题：测试总是失败
- 检查MQTT连接是否正常
- 降低故障强度重试
- 检查MCU是否正常响应

### 问题：重试次数很多
- 这是正常的！高故障率下会有大量重试
- 如果重试 > 1000次，可能需要调整超时参数

### 问题：传输超时
- 增加MCU端的处理速度
- 为高延迟场景增加timeout参数
- 检查MQTT broker负载

## 运行模式详解

### 交互式测试 (ota_cli_test.py)

```
优点：
✓ 灵活配置参数
✓ 实时查看日志
✓ 容易调试单个问题

用途：
- 开发和调试
- 理解系统行为
- 快速问题诊断
```

### 自动化测试 (ota_test_suite.py)

```
优点：
✓ 全自动化
✓ 生成对比报告
✓ 适合CI/CD集成

用途：
- 回归测试
- 性能基准测试
- 自动化验收测试
```

## 与生产环境的关系

| 特性 | 开发测试 | 生产环境 |
|------|---------|---------|
| 故障注入 | ✓ 启用 | ✗ 禁用 |
| 详细日志 | ✓ 完整 | ✗ 最小化 |
| 超时参数 | 可调 | 固定 |
| 重试次数 | 可调 | 10次 |

**生产版 (ota_cli.py) 仍然使用原始的ymodem.py，不涉及故障注入。**

## 进阶用法

### 自定义故障注入

编辑 `ymodem_fault_injector.py` 中的 `FaultConfig` 类：

```python
config = FaultConfig()
config.packet_loss_map = {100: True, 200: True}  # 特定包丢失
config.packet_delay_map = {50: 2000}  # 包50延迟2秒
config.scenario = 'custom'
```

### 集成到CI/CD

```bash
python3 src/ota_test_suite.py << EOF
1-3
EOF
```

## 技术细节

- **YMODEM实现**：基于标准YMODEM协议
- **时间模拟**：使用time.sleep()
- **CRC验证**：CRC-16-CCITT
- **并发处理**：多线程MQTT接收

## 性能基准（无故障）

| 数据量 | 预期时间 |
|--------|---------|
| 100KB | 2-5秒 |
| 1MB | 20-50秒 |
| 10MB | 200-500秒 |

实际时间取决于网络延迟和MCU处理速度。

## 已知限制

1. 故障注入为客户端（发送端）模拟，不涉及MCU处理
2. 不支持MCU端故障注入（需要MCU固件配合）
3. MQTT QoS设置为0（可靠性依赖应用层重试）

## 获取更多帮助

- 查看 `docs/FAULT_INJECTION_GUIDE.md` 获取详细文档
- 修改源码中的 `print()` 语句获取更详细的debug信息
- 保存日志用于离线分析

```bash
# 将输出保存到文件
python3 src/ota_cli_test.py 2>&1 | tee test_log_$(date +%s).txt
```

## 反馈

发现bug或有改进建议？欢迎提交issue或PR！
