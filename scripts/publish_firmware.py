import os
import sys
import paho.mqtt.client as mqtt
from src.firmware_selector import select_firmware
from src.ymodem import Ymodem

def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))

def on_publish(client, userdata, mid):
    print("Firmware published successfully!")

def publish_firmware(firmware_path, topic, broker):
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_publish = on_publish

    client.connect(broker, 1883, 60)
    client.loop_start()

    with open(firmware_path, 'rb') as firmware_file:
        ymodem = Ymodem()
        ymodem.send(firmware_file)

    client.publish(topic, firmware_path)
    client.loop_stop()
    client.disconnect()

def main():
    if len(sys.argv) < 4:
        print("Usage: python publish_firmware.py <broker_address> <topic> <firmware_file>")
        sys.exit(1)

    broker_address = sys.argv[1]
    topic = sys.argv[2]
    firmware_file = select_firmware()

    if not os.path.isfile(firmware_file):
        print(f"Error: {firmware_file} is not a valid file.")
        sys.exit(1)

    publish_firmware(firmware_file, topic, broker_address)

if __name__ == "__main__":
    main()