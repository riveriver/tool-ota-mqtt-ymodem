# Craner LTE MQTT YMODEM OTA Tool

这个工具是 `craner_sub_atc` 项目的 OTA 上位机，用 Python 通过 MQTT 与 4G LTE 模块通信，并用 YMODEM 协议把 MCUboot signed update image 发送到设备应用区。

设备端分工：

```text
LTE/YMODEM 只负责接收固件并写入 MCUboot slot1
mcumgr 负责 image test / confirm / reset
MCUboot 负责 swap / rollback
```

## MQTT Topic 约定

LTE 模块已配置的 topic index：

| LTE index | 配置字段 | 方向 | 用途 |
| ---: | --- | --- | --- |
| `1` | `ota_command_topic` | PC -> LTE -> MCU | 发送 OTA 启动命令 |
| `1` | `system_response_topic` | MCU -> LTE -> PC | 接收 ASCII key-value 状态响应 |
| `2` | `ota_publish_topic` | PC -> LTE -> MCU | 发送 YMODEM 固件包 |
| `2` | `ota_response_topic` | MCU -> LTE -> PC | 接收 YMODEM 控制字节 |

PC 侧 MQTT payload 不需要添加 `N,` 前缀。LTE 模块会在串口侧自动输出：

```text
1,device_id
1,ota_start <short_id>
2,<YMODEM packet>
```

设备返回 YMODEM 控制字节时，MCU 写给 LTE 模块：

```text
2,<C/ACK/NAK/CAN>
```

上位机在 `ota_response_topic` 收到的 payload 是逗号后的原始控制字节。

设备返回 ASCII 状态时，MCU 写给 LTE 模块：

```text
1,<key-value response>
```

上位机在 `system_response_topic` 原样打印这些 key-value 响应。

## 安装

```powershell
cd tool\tool-ota-mqtt-ymodem
python -m pip install -r requirements.txt
```

## 配置

编辑：

```text
src\ota_config.json
```

示例：

```json
{
  "mqtt_broker": "mqtt.craner.hk",
  "mqtt_port": 1883,
  "mqtt_username": "hkcrctest",
  "mqtt_password": "crcHK3130",
  "ota_command_payload": "ota_start",
  "ota_command_topic": "ai_satefy/ais999/system/server/hook",
  "system_response_topic": "ai_satefy/ais999/system/hook/server",
  "ota_publish_topic": "ai_satefy/ais999/ota/server/hook",
  "ota_response_topic": "ai_satefy/ais999/ota/hook/server"
}
```

## 使用

先在固件工程生成 OTA 镜像：

```powershell
.\build.ps1 -OtaImages
```

需要发送的文件是：

```text
build\craner_general_stm32h743vit6\ota_images\app_update_signed.bin
```

启动上位机：

```powershell
cd tool\tool-ota-mqtt-ymodem\src
python ota_cli.py
```

流程：

1. 工具连接 MQTT broker。
2. 工具订阅 `system_response_topic` 和 `ota_response_topic`。
3. 用户选择 `app_update_signed.bin`。
4. 工具向 `ota_command_topic` 发布 `device_id`，读取 4 位 short id。
5. 工具向 `ota_command_topic` 周期性发布 `ota_start <short_id>`。
6. 设备启动 OTA 后通过 `ota_response_topic` 返回 YMODEM `C`。
7. 工具向 `ota_publish_topic` 发送 YMODEM block0、数据包、EOT、结束包。
8. 设备接收完成后进入 `ready_for_mcumgr`。
9. 工具自动查询 `ota_status`、`image_list` 和 `image_info <slot1_hash>`。
10. 用户可选择执行 `image_test <short_id>` 和 `reset <short_id>`。

传输过程中可以按 `Ctrl+Q` 中止，工具会尝试向 OTA 数据 topic 发送 `CAN CAN`。

## 后续 mcumgr 操作

固件写入 slot1 后，设备不会自动 test 或 reset。维护端需要执行：

```powershell
mcumgr --conntype udp --connstring=[设备IP]:1337 image list
mcumgr --conntype udp --connstring=[设备IP]:1337 image test <slot1_hash>
mcumgr --conntype udp --connstring=[设备IP]:1337 reset
mcumgr --conntype udp --connstring=[设备IP]:1337 image confirm
```

只有 4G、没有以太网的设备，可以通过 topic 1 执行等效操作：

```text
device_id
image_list
image_info <hash>
image_test <short_id>
reset <short_id>
image_confirm <short_id>
```

## 注意事项

- 不要发送 `zephyr.bin`、`zephyr.signed.confirmed.bin` 或 `app_initial_confirmed.bin`。
- MQTT payload 必须按二进制处理，不能转 HEX 或 Base64。
- YMODEM 1K 数据包是 1029 字节，LTE 模块串口侧带 `2,` 后是 1031 字节。
- OTA 传输期间设备会暂停业务数据上报，减少 topic `3` 干扰。
