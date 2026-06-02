"""
OTA CLI Test with Fault Injection
用于测试OTA在各种网络故障条件下的表现
"""
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

from firmware_selector import select_firmware
from mqtt_client import MQTTClient
from ymodem_fault_injector import Ymodem, FaultConfig


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


def configure_faults(config: FaultConfig) -> None:
    """Interactive fault configuration"""
    print("\n=== Fault Injection Configuration ===")
    print("Available preset scenarios:")
    print("  1. high_latency   - High network latency (500-2000ms delays)")
    print("  2. packet_loss    - Random ACK drops (~15% loss rate)")
    print("  3. intermittent   - Intermittent issues (5% loss + delays)")
    print("  4. corrupted_data - Data corruption (10% corruption rate)")
    print("  5. duplicate_acks - Duplicate ACK responses (20% rate)")
    print("  0. custom         - Manual configuration")
    
    choice = input("Select scenario (0-5) [default: 0 - no faults]: ").strip() or "0"
    
    if choice in ['1', '2', '3', '4', '5']:
        scenarios = {
            '1': 'high_latency',
            '2': 'packet_loss',
            '3': 'intermittent',
            '4': 'corrupted_data',
            '5': 'duplicate_acks',
        }
        config.scenario = scenarios[choice]
    else:
        # Custom configuration
        print("\n=== Custom Fault Configuration ===")
        
        ack_loss = input("ACK loss probability (0.0-1.0, default 0.0): ").strip() or "0.0"
        config.ack_loss_probability = float(ack_loss)
        
        ack_delay = input("ACK delay in ms (default 0): ").strip() or "0"
        config.ack_delay_ms = int(ack_delay)
        
        dup_ack = input("Duplicate ACK probability (0.0-1.0, default 0.0): ").strip() or "0.0"
        config.duplicate_ack_probability = float(dup_ack)
        
        data_corrupt = input("Data corruption probability (0.0-1.0, default 0.0): ").strip() or "0.0"
        config.data_corruption_probability = float(data_corrupt)
        
        print(f"\nCustom fault config applied:")
        print(f"  ACK loss: {config.ack_loss_probability}")
        print(f"  ACK delay: {config.ack_delay_ms}ms")
        print(f"  Duplicate ACK: {config.duplicate_ack_probability}")
        print(f"  Data corruption: {config.data_corruption_probability}")


def main():
    print("Welcome to the OTA Firmware Update Test CLI with Fault Injection")

    mqtt_client = None
    topic = None
    stop_event = threading.Event()
    key_thread = None
    accept_responses = threading.Event()

    def _key_monitor(ev: threading.Event):
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
                return

    try:
        # Connect to MQTT broker
        mqtt_broker = input("Enter MQTT broker address (default 210.0.159.242): ") or "210.0.159.242"
        mqtt_port = int(input("Enter MQTT broker port (default 1883): ") or 1883)

        username = input("MQTT username (leave empty to use default 'hkcrctest'): ") or "hkcrctest"
        password = input("MQTT password (visible, leave empty to use default 'crcHK3130'): ") or "crcHK3130"

        mqtt_client = MQTTClient(mqtt_broker, mqtt_port)
        if username:
            mqtt_client.set_credentials(username, password)
        mqtt_client.connect(on_connect=on_mqtt_connect)

        # Start keyboard monitor
        key_thread = threading.Thread(target=_key_monitor, args=(stop_event,), daemon=True)
        key_thread.start()

        # Input device name and build publish/command topics
        device_name = input("Enter device name (format: <xxx>/<xxx>) [default tc42/atc01]: ") or "tc42/atc01"
        topic_input = f"/ota/upgrade/{device_name}"
        command_topic = f"/device/command/{device_name}"
        try:
            topic, response_topic = build_progress_topic(topic_input)
        except ValueError as err:
            print(str(err))
            sys.exit(1)

        # Configure faults
        fault_config = FaultConfig()
        configure_faults(fault_config)

        wait_choice = input("Wait for 'C' from receiver before starting transfer? (Y/n) [default Y]: ") or "Y"
        wait_for_crc = False if (wait_choice.lower() == 'n') else True

        # Setup response queue
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
                    resp_queue.put((tpc, payload, time.monotonic()))
                    print(f"{tpc} recv: {repr(payload)}")
            except Exception:
                pass

        mqtt_client.set_on_message(_on_message)
        mqtt_client.subscribe(response_topic)

        # Select firmware
        firmware_path = select_firmware()
        if not firmware_path:
            print("No firmware file selected. Exiting.")
            sys.exit(1)

        # Send OTA start command to device
        print(f"\nSending OTA start command to {command_topic}...")
        mqtt_client.publish(command_topic, "craner#AT+OTASTART")
        print(f"Waiting for device to respond with 'C' (timeout {180}s)...")

        # Initialize Ymodem with fault injection
        ymodem = Ymodem(fault_config=fault_config)

        # Start transfer
        print(f"\nSending firmware file '{firmware_path}' to topic '{topic}'...")
        print(f"Listening progress/response on '{response_topic}'")
        print("Press Ctrl+Q to abort transfer.")
        print("=" * 60)
        
        _drain_queue(resp_queue)
        accept_responses.set()
        
        start_time = time.time()
        with open(firmware_path, 'rb') as firmware_file:
            success = ymodem.send(
                firmware_file,
                mqtt_client.publish,
                topic,
                recv_queue=resp_queue,
                timeout=5,
                should_stop=stop_event.is_set,
                wait_for_initial_crc=wait_for_crc,
                initial_crc_timeout=180,
                block0_timeout=180,
            )
            elapsed = time.time() - start_time
            
            print("=" * 60)
            if success:
                print(f"✓ Firmware transfer completed successfully in {elapsed:.1f}s")
            else:
                print(f"✗ Firmware transfer failed after {elapsed:.1f}s")
                
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
        try:
            accept_responses.clear()
            stop_event.set()
            if key_thread is not None:
                key_thread.join(timeout=1.0)
        except Exception:
            pass
        try:
            if mqtt_client is not None:
                mqtt_client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
