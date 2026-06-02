# OTA 故障注入测试框架 - 完整指南

## 📋 项目结构

```
python-ymodem-mqtt-ota/
├── src/
│   ├── ota_cli.py                    # ✓ 生产版OTA CLI
│   ├── ota_cli_test.py               # ✨ 测试版OTA CLI (故障注入)
│   ├── ymodem.py                     # ✓ 原始YMODEM实现
│   ├── ymodem_fault_injector.py      # ✨ 增强YMODEM (故障注入)
│   ├── ota_test_suite.py             # ✨ 自动化多场景测试套件
│   ├── test_scenarios.py             # ✨ 可复用的测试场景配置
│   ├── mqtt_client.py                # ✓ MQTT客户端
│   ├── firmware_selector.py          # ✓ 固件选择器
│   └── ...其他模块
│
├── docs/
│   ├── FAULT_INJECTION_GUIDE.md      # ✨ 故障注入详细文档
│   ├── TESTING_GUIDE.md              # ✨ 测试快速入门
│   └── FAULT_INJECTION_TESTING.md    # ✨ 本文件
│
├── test_reports/                     # 自动化测试报告输出目录
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 🎯 核心功能

### 故障模拟能力

| 故障类型 | 参数 | 说明 |
|---------|------|------|
| **ACK丢失** | `ack_loss_probability` | 0.0-1.0 概率随机丢弃ACK |
| **ACK延迟** | `ack_delay_ms` | 毫秒级延迟 ± 随机抖动 |
| **重复ACK** | `duplicate_ack_probability` | 0.0-1.0 概率重复发送ACK |
| **数据损坏** | `data_corruption_probability` | 0.0-1.0 概率损坏数据 |
| **预设场景** | `scenario` | 5种预定义组合场景 |

### 预定义场景

| 名称 | 组合 | 用途 |
|------|------|------|
| `high_latency` | delay 500-2000ms | 网络延迟测试 |
| `packet_loss` | loss 15% | 正常丢包条件 |
| `intermittent` | loss 5% + delay | 现实基础网络 |
| `corrupted_data` | corrupt 10% | CRC校验测试 |
| `duplicate_acks` | dup 20% | 状态机处理 |

## 🚀 使用方式

### 方式1️⃣：单场景交互测试

**最简单，适合新手和调试**

```bash
python3 src/ota_cli_test.py
```

特点：
- ✓ 实时参数调整
- ✓ 详细输出日志
- ✓ 逐步理解系统行为

### 方式2️⃣：预定义场景快测

**快速验证，无需配置**

```bash
python3 src/ota_cli_test.py
# 在场景选择处直接选 1-5 或 0 使用预设
```

### 方式3️⃣：完整自动化测试

**CI/CD集成，生成报告**

```bash
python3 src/ota_test_suite.py
# 交互选择：all / 1-5 / 2,4,6
```

输出：
- 实时执行日志
- JSON格式测试报告
- 成功率统计

### 方式4️⃣：编程调用

**最灵活，用于自定义场景**

```python
from ymodem_fault_injector import Ymodem, FaultConfig
from test_scenarios import SCENARIO_CONFIGS

# 使用预定义场景
config = SCENARIO_CONFIGS['mobile_3g']
fault_config = FaultConfig(**config['config'])

# 或自定义
custom_config = FaultConfig()
custom_config.ack_loss_probability = 0.2
custom_config.ack_delay_ms = 1000

# 创建OTA实例
ymodem = Ymodem(fault_config=fault_config)
success = ymodem.send(...)
print(ymodem.stats)
```

## 📊 典型场景的预期行为

### 场景1：基准（无故障）

```
Scenario: baseline
Expected time: 45-60秒
Retries: 0
Status: ✓ PASS
```

### 场景2：高延迟

```
Scenario: high_latency  (500-2000ms延迟)
Expected time: 120-180秒
Retries: 158 (所有数据包都会超时等待)
Status: ✓ PASS (会变慢，但最终成功)
```

### 场景3：中等丢包

```
Scenario: packet_loss  (15%丢包率)
Expected time: 80-120秒
Retries: 20-30
Status: ✓ PASS (正常的网络条件)
```

### 场景4：极限条件

```
Scenario: extreme_stress  (30%丢包+2s延迟+15%重复+5%损坏)
Expected time: 300-600秒
Retries: 200-500
Status: ✓ PASS / ? FAIL (取决于系统设计)
```

## 📈 读取测试结果

### 实时日志

```
[FAULT] Packet 158: ACK dropped (random)        # 发生了一个故障
[RECV] Received from /ota/progress/.../: b'\x06' # 收到ACK
Sending data packet 158 (attempt 7/10)...        # 正在重试
```

### 统计信息

```
[FAULT INJECTION STATS]
  acks_dropped: 23                    # 注入的故障数
  packets_delayed: 158                # 延迟的包数
  packets_corrupted: 0                # 损坏的包数
  duplicate_acks_sent: 31             # 重复ACK数
  total_retries: 24                   # 由于超时的重试
```

### JSON报告

```json
{
  "scenario": "Scenario 4: Medium Packet Loss",
  "success": true,
  "elapsed_time": 95.3,
  "stats": {
    "acks_dropped": 15,
    "packets_delayed": 0,
    "total_retries": 12
  }
}
```

## 🔍 测试用例模板

### 验证基本重试

```python
# 目标：验证系统能处理偶发丢包
# 参数：5%丢包率
# 预期：成功完成，10次左右重试

config = FaultConfig()
config.ack_loss_probability = 0.05
```

### 验证超时处理

```python
# 目标：验证超时重试逻辑
# 参数：1000ms延迟
# 预期：成功，但每包都超时等待
# 注意：超时参数需要 > 1000ms

config = FaultConfig()
config.ack_delay_ms = 1000
```

### 压力测试

```python
# 目标：找到系统的失败点
# 参数：逐步提高故障强度
# 流程：
#   1. 测试 loss=10%, delay=500
#   2. 测试 loss=20%, delay=1000
#   3. 测试 loss=30%, delay=2000
# 输出：第一个失败的场景即为系统极限
```

## 📝 测试报告示例

### 完整测试周期

```bash
python3 src/ota_test_suite.py
# 输入：all

Running: Scenario 1: No Faults
✓ PASS | Elapsed: 48.2s | Retries: 0

Running: Scenario 2: High Latency
✓ PASS | Elapsed: 156.3s | Retries: 158

Running: Scenario 3: Light Packet Loss
✓ PASS | Elapsed: 72.1s | Retries: 8

Running: Scenario 4: Medium Packet Loss
✓ PASS | Elapsed: 95.5s | Retries: 18

Running: Scenario 5: Heavy Packet Loss
✓ PASS | Elapsed: 278.9s | Retries: 145

Running: Scenario 6: Intermittent Issues
✓ PASS | Elapsed: 108.4s | Retries: 25

Running: Scenario 7: Duplicate ACKs
✓ PASS | Elapsed: 52.3s | Retries: 0

Running: Scenario 8: Combined Stress
✓ PASS | Elapsed: 142.6s | Retries: 32

Running: Scenario 9: Extreme Conditions
✓ FAIL | Elapsed: 600.0s (timeout) | Retries: 500+

================================================================================
TEST REPORT - 2024-05-19 14:30:45
================================================================================

Total Tests: 9
Passed: 8 ✓
Failed: 1 ✗
Success Rate: 88.9%

Report saved: test_reports/test_report_20240519_143045.json
```

## 🎓 学习路径

### 初级：理解基本概念

1. 运行baseline场景
   ```bash
   python3 src/ota_cli_test.py  # 选 0 - no faults
   ```

2. 查看输出，理解YMODEM流程

3. 阅读 `docs/TESTING_GUIDE.md`

### 中级：实验各种故障

1. 依次测试预定义场景1-5
   ```bash
   python3 src/ota_cli_test.py  # 逐个选择 1,2,3,4,5
   ```

2. 观察每种故障的影响

3. 调整参数看效果

### 高级：自定义测试

1. 编辑 `test_scenarios.py` 添加场景

2. 在代码中调用故障注入版本

3. 集成到自动化测试流程

4. 分析和优化系统设计

## ⚙️ 性能参考（无故障基准）

| 固件大小 | 预期时间 | 数据包数 |
|---------|---------|---------|
| 100KB | 2-5秒 | ~100 |
| 500KB | 10-25秒 | ~500 |
| 1MB | 20-50秒 | ~1000 |
| 10MB | 200-500秒 | ~10000 |

**注**：实际时间取决于网络延迟和MCU处理速度

## 🔧 调试技巧

### 保存完整日志

```bash
python3 src/ota_cli_test.py > debug_$(date +%s).log 2>&1
```

### 增加更多输出

编辑 `ymodem_fault_injector.py`，在 `wait_for()` 中添加：

```python
print(f"[DEBUG] Waiting for {fmt_expected(expected_set)}")
print(f"[DEBUG] Queue size: {recv_queue.qsize()}")
print(f"[DEBUG] Elapsed: {time.time() - end + timeout_sec}s")
```

### 单步调试特定数据包

修改 `packet_num` 条件：

```python
if packet_num == 158:  # 只对包158注入故障
    self._should_drop_ack(packet_num)
```

## ⚠️ 注意事项

1. **不影响生产**
   - 原始 `ota_cli.py` 未被修改
   - 生产环境继续使用 `ota_cli.py`
   - 故障注入仅在测试版本中启用

2. **网络条件影响**
   - 故障是在客户端注入，不是真实网络损坏
   - 实际网络条件可能不同
   - 建议结合真实弱网环境测试

3. **MCU限制**
   - MCU处理速度不受此工具影响
   - 如果MCU本身很慢，会掩盖其他问题
   - 建议用快速的测试固件

4. **重试次数**
   - 默认10次重试/包
   - 如超过10次失败将立即返回
   - 可在源码中调整 `retries = 10`

## 📚 相关文档

- [故障注入详细指南](docs/FAULT_INJECTION_GUIDE.md)
- [测试快速入门](docs/TESTING_GUIDE.md)
- [原始README](README.md)

## 🤝 反馈与改进

如果您发现：
- Bug或异常行为
- 建议的优化
- 新的测试场景

欢迎贡献！

---

**版本**: 1.0  
**最后更新**: 2024-05-19  
**维护者**: OTA Testing Team
