# python-ymodem-mqtt-ota 使用指南（中文）

本文档面向新手，介绍如何在本项目中通过 MQTT 和 Ymodem 协议对远端设备（通过 4G 模块转发到 MCU）进行 OTA 固件更新。

目录
- 简介
- 先决条件
- 安装与依赖
- 快速开始（交互式运行）
- 命令行参数与默认值
- 工作流程与协议要点
- 调试技巧
- 常见问题
- 文件结构（简要）

---

简介
-----
本项目实现了一个 Python CLI 工具，用于通过 MQTT 向远端设备发送固件。发送端实现了一个简化的 Ymodem 发送流程（CRC 握手、分块、ACK/NAK 校验、EOT 结束），并通过 MQTT 发布原始二进制包。接收端（4G 模块 + MCU）须能从 MQTT 接收到这些包并按 Ymodem 协议处理。

先决条件
--------
- Linux 或 macOS（Windows 也可，路径/虚拟环境方式略有不同）
- Python 3.8+
- 能访问的 MQTT Broker；设备（通过 4G 模块）可订阅/发布相应话题

安装与依赖
----------
1. 进入仓库目录（本例中为 `tool/python-ymodem-mqtt-ota`）：
```bash
cd tool/python-ymodem-mqtt-ota
```
2. 创建并激活虚拟环境：
```bash
python3 -m venv .venv
source .venv/bin/activate
```
3. 安装依赖：
```bash
pip install -r requirements.txt
```
注意：如果 `requirements.txt` 中的第三方包不存在，请按 README 或脚本中的注释替换为 `ymodem` 等可用包，或使用项目自带的 `src/ymodem.py` 实现（默认已经包含）。

快速开始（交互式运行）
--------------------
在虚拟环境激活后运行：
```bash
python src/ota_cli.py
```
程序会按顺序提示：
1. 输入 MQTT Broker（默认：210.0.159.242，直接回车使用默认）
2. 输入端口（默认：1883）
3. 输入 MQTT 用户名（默认：hkcrctest）
4. 输入 MQTT 密码（明文显示，默认：crcHK3130）
5. 输入要发布的 topic（例如 `/tc42/atc02/encoder`）
6. 在弹出的文件选择对话框中选择固件（选择框现在显示所有文件）

默认值方便快速测试，请根据实际 Broker/设备调整。

命令行参数
---------
当前 CLI 主要为交互式设计，也可在代码中调用 `src/ota_cli.py` 的逻辑并传入参数（如需批量化或自动化运行，我可以添加 argparse 支持）。

工作流程与协议要点
------------------
发送端（本脚本）要点：
- 在调用 `Ymodem.send()` 前会订阅你的 topic（和 topic + "/resp"）以便接收应答。
- `Ymodem.send()` 会等待从端发出 ASCII 'C' (0x43) 表示要求 CRC 模式，然后发送 block0（文件名/大小），再发送 1K 数据块（STX），对每个包等待 ACK (0x06) 或 NAK (0x15)。
- EOT (0x04) 的交互也在实现内处理。

接收端（4G 模块 + MCU）要点：
- 模块需要把从 MCU 收到的 ACK/NAK/'C' 等控制字节通过 MQTT 发布到你在 CLI 中订阅的 `topic + '/resp'`（或能被 CLI 识别的回复话题）。
- 发送的包是原始二进制：发送端不会在终端打印二进制 payload，但会打印状态提示（等待、发送第几包、预期回复等）。

调试技巧
--------
- 如果传输失败，请先查看 CLI 输出的 DEBUG 行（只会显示 `topic+'/resp'` 的返回内容），确认从端是否发送了 'C' / ACK / NAK（显示为 hex，如 `43` 表示 'C'，`06` 表示 ACK）。
- 如果设备把控制字节作为文本（例如发送字符串 `2,6`），你需要让网关/模块也发送纯字节，或在 CLI 中添加对应的解析规则（我已实现部分静态解析）。
- 超时时间默认较长（3 分钟）以支持模块启动或唤醒延迟；如需更短可在 CLI 中修改 `timeout` 参数。

常见问题
--------
1. 无法连接 MQTT：确认 Broker 地址、端口、用户名/密码是否正确，端口是否需要 TLS（8883）。
2. CLI 未识别 ACK：确认设备在 `topic+'/resp'` 发布的是原始字节（0x06）而不是字符 '6'（0x36）或带前缀的文本。
3. 传输中被打断：确保在传输中不要按 Ctrl+C，若需要中断，CLI 已处理 KeyboardInterrupt，会断开并清理。

文件结构（简要）
----------------
- src/
  - `ota_cli.py`：主交互脚本
  - `firmware_selector.py`：文件选择对话框（现在显示所有文件）
  - `mqtt_client.py`：MQTT 封装，订阅/发布/回调处理
  - `ymodem.py`：Ymodem 发送端实现（简化的完整握手 + ACK/NAK 处理）

---

需要我帮你：
- 将 README_CN.md 添加到仓库（我已经创建）并在 README 中链接；
- 添加自动化参数（argparse），或把传输结果上报到日志文件；
- 根据你 MCU 的实际回复格式调整解析规则（如果模块在 payload 前加前缀或使用文本形式）。

如果要我把 README_CN.md 中的示例命令或说明扩展为更详细的操作步骤（例如如何在 Broker 上观察消息，如何用 mosquitto_sub 测试等），告诉我我会补充。