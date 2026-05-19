import os
import sys
import paho.mqtt.client as mqtt
import queue
import time
import threading
try:
    import msvcrt
    _HAS_MSVCRT = True
except Exception:
    _HAS_MSVCRT = False
# show password input (do not hide) per user request
from firmware_selector import select_firmware
from mqtt_client import MQTTClient
from ymodem import Ymodem

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


def build_progress_topic(publish_topic):
    topic = (publish_topic or "").strip()
    parts = topic.split('/')
    if len(parts) != 5 or parts[0] != '' or parts[1] != 'ota' or parts[2] != 'upgrade':
        raise ValueError("Invalid topic format. Expected: /ota/upgrade/<xxx>/<xxx>")
    if not parts[3] or not parts[4]:
        raise ValueError("Invalid topic format. Expected: /ota/upgrade/<xxx>/<xxx>")
    return topic, f"/ota/progress/{parts[3]}/{parts[4]}"

def main():
    print("Welcome to the OTA Firmware Update CLI")

    mqtt_client = None
    topic = None
    stop_event = threading.Event()
    key_thread = None
    accept_responses = threading.Event()

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
        # Connect to MQTT broker (defaults provided)
        mqtt_broker = input("Enter MQTT broker address (default 210.0.159.242): ") or "210.0.159.242"
        mqtt_port = int(input("Enter MQTT broker port (default 1883): ") or 1883)

        # Optional username/password (defaults provided)
        username = input("MQTT username (leave empty to use default 'hkcrctest'): ") or "hkcrctest"
        password = input("MQTT password (visible, leave empty to use default 'crcHK3130'): ") or "crcHK3130"

        mqtt_client = MQTTClient(mqtt_broker, mqtt_port)
        if username:
            mqtt_client.set_credentials(username, password)
        mqtt_client.connect(on_connect=on_mqtt_connect)

        # Start keyboard monitor for Ctrl+Q
        key_thread = threading.Thread(target=_key_monitor, args=(stop_event,), daemon=True)
        key_thread.start()

        # Select and validate publish topic, and build progress response topic
        topic_input = input("Enter publish topic (format: /ota/upgrade/<xxx>/<xxx>) [default /ota/upgrade/tc42/atc01]: ") or "/ota/upgrade/tc42/atc01"
        try:
            topic, response_topic = build_progress_topic(topic_input)
        except ValueError as err:
            print(str(err))
            sys.exit(1)

        # Ask whether to wait for 'C' before starting transfer
        wait_choice = input("Wait for 'C' from receiver before starting transfer? (Y/n) [default Y]: ") or "Y"
        wait_for_crc = False if (wait_choice.lower() == 'n') else True

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
        print("Press Ctrl+Q to abort transfer.")
        _drain_queue(resp_queue)
        accept_responses.set()
        with open(firmware_path, 'rb') as firmware_file:
            success = ymodem.send(
                firmware_file,
                mqtt_client.publish,
                topic,
                recv_queue=resp_queue,
                timeout=30,
                should_stop=stop_event.is_set,
                wait_for_initial_crc=wait_for_crc,
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