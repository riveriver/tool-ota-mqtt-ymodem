import unittest
from src.mqtt_client import MQTTClient

class TestMQTTClient(unittest.TestCase):

    def setUp(self):
        self.client = MQTTClient("test_broker", 1883, "test_client")

    def test_connect(self):
        result = self.client.connect()
        self.assertTrue(result)

    def test_subscribe(self):
        self.client.connect()
        result = self.client.subscribe("test/topic")
        self.assertTrue(result)

    def test_publish(self):
        self.client.connect()
        result = self.client.publish("test/topic", "Hello, MQTT!")
        self.assertTrue(result)

    def tearDown(self):
        self.client.disconnect()

if __name__ == '__main__':
    unittest.main()