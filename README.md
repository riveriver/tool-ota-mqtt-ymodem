# python-ymodem-mqtt-ota

This project implements an Over-The-Air (OTA) firmware update mechanism using the Ymodem protocol and MQTT for communication. It allows users to select firmware files and publish them to a specified MQTT topic for remote devices to download and update.

## Project Structure

```
python-ymodem-mqtt-ota
├── src
│   ├── __init__.py
│   ├── ota_cli.py          # Command-line interface for OTA process
│   ├── firmware_selector.py # Functionality to select firmware files
│   ├── mqtt_client.py      # MQTT client management
│   ├── ymodem.py           # Ymodem protocol implementation
│   ├── uart_serial.py      # UART serial communication management
│   └── utils.py            # Utility functions
├── tests
│   ├── test_ymodem.py      # Unit tests for Ymodem protocol
│   └── test_mqtt.py        # Unit tests for MQTT client
├── scripts
│   └── publish_firmware.py  # Script to publish firmware files
├── requirements.txt         # Project dependencies
├── pyproject.toml          # Project configuration
├── .gitignore               # Files to ignore in version control
└── README.md                # Project documentation
```

## Installation

To install the required dependencies, run:

```
pip install -r requirements.txt
```

## Usage

Below are concrete steps and examples to run the tool on Windows (PowerShell) or any shell with Python available.

1) Install dependencies

```powershell
cd tool\python-ymodem-mqtt-ota
python3 -m pip install -r requirements.txt
```

2) Interactive CLI (recommended)

- Run the CLI which guides you through selecting broker, topic and firmware:

```powershell
cd tool\python-ymodem-mqtt-ota\src
python3 ota_cli.py
```

- Interactive flow summary:
	- Enter MQTT broker address (default `210.0.159.242`).
	- Enter MQTT port (default `1883`).
	- Enter MQTT username/password (defaults: `hkcrctest` / `crcHK3130`). Password input is visible.
	- Enter the MQTT topic to publish the firmware to.
	- Choose a firmware file when prompted (the CLI calls `select_firmware()`).
	- The tool sends the firmware using the Ymodem protocol over MQTT and listens for receiver responses (default timeout in `ota_cli.py` is 180 seconds).

3) Non-interactive / script mode (automation)

- The included script `scripts/publish_firmware.py` can be used from the project root. Example:

```powershell
cd tool\python-ymodem-mqtt-ota
python scripts\publish_firmware.py <broker_address> <topic> <firmware_file>
```

- Note: the current `publish_firmware.py` attempts to use the helper `select_firmware()`; if you want fully non-interactive behavior, pass a firmware path or modify the script to use the provided CLI argument directly.

4) Defaults and important notes

- Default broker: `210.0.159.242`
- Default port: `1883`
- Default username: `hkcrctest`
- Default password: `crcHK3130` (visible by design in the CLI)
- Main CLI file: `tool/python-ymodem-mqtt-ota/src/ota_cli.py`
- Publish script: `tool/python-ymodem-mqtt-ota/scripts/publish_firmware.py`
- The Ymodem transfer is implemented in `src/ymodem.py` and the MQTT wrapper in `src/mqtt_client.py`.

5) Troubleshooting

- If dependency installation fails, ensure you are using a supported Python version and that `pip` is up-to-date.
- If MQTT connection fails, verify network access to the broker and credentials.
- For automating in CI or scripts, consider editing `scripts/publish_firmware.py` to skip any interactive `select_firmware()` calls.

If you want, I can update `scripts/publish_firmware.py` to accept the firmware file strictly from the command line (non-interactive). 

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.