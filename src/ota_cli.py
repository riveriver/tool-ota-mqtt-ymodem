import sys
import json
import queue
import time
import threading
from pathlib import Path
try:
    import msvcrt
    _HAS_MSVCRT = True
except Exception:
    _HAS_MSVCRT = False
# show password input (do not hide) per user request
from firmware_selector import select_firmware
from mqtt_client import MQTTClient
from ymodem import Ymodem

OTA_START_TIMEOUT = 180
OTA_COMMAND_INTERVAL = 10
CONFIG_PATH = Path(__file__).with_name("ota_config.json")


def load_config():
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        config = json.load(f)

    required = [
        "mqtt_broker",
        "mqtt_port",
        "mqtt_username",
        "mqtt_password",
        "ota_command_payload",
        "ota_command_topic",
        "ota_response_topic",
        "ota_publish_topic",
    ]
    missing = [key for key in required if key not in config]
    if missing:
        raise KeyError(f"Missing required config keys: {', '.join(missing)}")

    return config

def on_mqtt_connect(client, userdata, flags, rc):
    reasons = {
        0: "Connection accepted",
        1: "Connection refused: unacceptable protocol version",
        2: "Connection refused: identifier rejected",
        3: "Connection refused: server unavailable",
        4: "Connection refused: bad user name or password",
        5: "Connection refused: not authorized",
    }
    reason = reasons.get(rc, f"Unknown return code {rc}")
    print("Connected to MQTT broker with result code " + str(rc) + " (" + reason + ")")


def wait_for_ota_start_signal(mqtt_client, command_topic, ota_command_payload, response_queue, stop_event):
    deadline = time.time() + OTA_START_TIMEOUT
    next_command_at = 0
    start_signal = ord("C")

    print(
        f"Waiting for OTA start signal on response topic (timeout {OTA_START_TIMEOUT}s)..."
    )
    while time.time() < deadline:
        if stop_event.is_set():
            return False

        now = time.time()
        if now >= next_command_at:
            mqtt_client.publish(command_topic, ota_command_payload)
            print(
                f"Published OTA command to '{command_topic}', next retry in {OTA_COMMAND_INTERVAL}s."
            )
            next_command_at = now + OTA_COMMAND_INTERVAL

        remaining = max(0.1, min(0.5, deadline - now))
        try:
            item = response_queue.get(timeout=remaining)
        except queue.Empty:
            continue

        if item is None:
            continue

        payload = item[1] if isinstance(item, tuple) and len(item) >= 2 else item
        payload_bytes = payload.encode(errors="ignore") if isinstance(payload, str) else payload
        if any(b == start_signal for b in payload_bytes):
            print("Received OTA start signal 'C'.")
            return True

    print(f"Timed out waiting for OTA start signal after {OTA_START_TIMEOUT}s.")
    return False

def main():
    print("Welcome to the OTA Firmware Update CLI")

    mqtt_client = None
    topic = None
    stop_event = threading.Event()
    key_thread = None
    accept_responses = threading.Event()
    config = load_config()
    topic = config["ota_publish_topic"]
    response_topic = config["ota_response_topic"]
    command_topic = config["ota_command_topic"]

    print("Loaded MQTT/OTA configuration:")
    print(f"  Broker: {config['mqtt_broker']}:{config['mqtt_port']}")
    print(f"  Username: {config['mqtt_username']}")
    print(f"  Publish topic: {topic}")
    print(f"  Response topic: {response_topic}")
    print(f"  Command topic: {command_topic}")
    print(f"  OTA command payload: {config['ota_command_payload']}")

    confirm = input('Type yes to confirm the configuration and continue: ').strip().lower()
    if confirm != "yes":
        print("Configuration not confirmed. Exiting.")
        return

    def _key_monitor(ev: threading.Event):
        # Monitor keyboard for Ctrl+Q (0x11). On Windows use msvcrt, otherwise fallback to stdin select.
        if _HAS_MSVCRT:
            while not ev.is_set():
                try:
                    if msvcrt.kbhit():
                        ch = msvcrt.getch()
                        if ch == b"\x11":
                            print("\nCtrl+Q detected, aborting...")
                            ev.set()
                            return
                except Exception:
                    pass
                time.sleep(0.05)
        else:
            # Fallback for Unix-like: use select on stdin
            try:
                import sys, select, tty, termios
                fd = sys.stdin.fileno()
                old = termios.tcgetattr(fd)
                tty.setcbreak(fd)
                while not ev.is_set():
                    dr, _, _ = select.select([sys.stdin], [], [], 0.1)
                    if dr:
                        ch = sys.stdin.read(1)
                        if ch == '\x11':
                            print("\nCtrl+Q detected, aborting...")
                            ev.set()
                            return
            except Exception:
                # If fallback fails, do nothing; Ctrl+C remains available
                return

    try:
        mqtt_client = MQTTClient(config["mqtt_broker"], config["mqtt_port"])
        mqtt_client.set_credentials(config["mqtt_username"], config["mqtt_password"])
        mqtt_client.connect(on_connect=on_mqtt_connect)

        # Start keyboard monitor for Ctrl+Q
        key_thread = threading.Thread(target=_key_monitor, args=(stop_event,), daemon=True)
        key_thread.start()

        # Subscribe to topic(s) to receive receiver responses
        resp_queue = queue.Queue()

        def _drain_queue(q: queue.Queue):
            while True:
                try:
                    q.get_nowait()
                except queue.Empty:
                    break

        def _on_message(tpc, payload):
            try:
                if accept_responses.is_set() and tpc == response_topic:
                    # Only response-topic payloads should drive the Ymodem state machine.
                    resp_queue.put((tpc, payload))
                    print(f"{tpc} recv: {repr(payload)}")
            except Exception:
                pass

        mqtt_client.set_on_message(_on_message)
        mqtt_client.subscribe(response_topic)

        # Select firmware file AFTER topic is entered
        firmware_path = select_firmware()
        if not firmware_path:
            print("No firmware file selected. Exiting.")
            sys.exit(1)

        # Initialize Ymodem for firmware transfer
        ymodem = Ymodem()

        # Send firmware file using Ymodem with handshake/ACKs
        print(f"Sending firmware file '{firmware_path}' to topic '{topic}'...")
        print(f"Listening progress/response on '{response_topic}'")
        print(f"Using OTA command topic '{command_topic}'")
        print("Press Ctrl+Q to abort transfer.")
        _drain_queue(resp_queue)
        accept_responses.set()
        if not wait_for_ota_start_signal(
            mqtt_client,
            command_topic,
            config["ota_command_payload"],
            resp_queue,
            stop_event,
        ):
            accept_responses.clear()
            print("OTA start handshake failed. Exiting without sending firmware.")
            return
        with open(firmware_path, 'rb') as firmware_file:
            success = ymodem.send(
                firmware_file,
                mqtt_client.publish,
                topic,
                recv_queue=resp_queue,
                timeout=30,
                should_stop=stop_event.is_set,
                wait_for_initial_crc=False,
            )
            if success:
                print("Firmware transfer completed.")
            else:
                print("Firmware transfer failed.")
    except KeyboardInterrupt:
        print("\nInterrupted by user (KeyboardInterrupt). Cleaning up and exiting...")
        stop_event.set()
        try:
            if (mqtt_client is not None) and topic:
                mqtt_client.publish(topic, bytes([0x18]))
                mqtt_client.publish(topic, bytes([0x18]))
        except Exception:
            pass
        sys.exit(130)
    finally:
        # stop key monitor thread
        try:
            accept_responses.clear()
            stop_event.set()
            if key_thread is not None:
                key_thread.join(timeout=1.0)
        except Exception:
            pass
        # Ensure we disconnect cleanly if still connected
        try:
            if mqtt_client is not None:
                mqtt_client.disconnect()
        except Exception:
            pass

if __name__ == "__main__":
    main()
