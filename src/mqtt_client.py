class MQTTClient:
    def __init__(self, broker, port=1883, client_id=None):
        import paho.mqtt.client as mqtt
        self.broker = broker
        self.port = port
        self.client_id = client_id or "mqtt_client"
        # paho-mqtt 2.x introduced callback_api_version; prefer VERSION1 for
        # compatibility with the callback signatures used in this project.
        try:
            callback_api = mqtt.CallbackAPIVersion.VERSION1
            self.client = mqtt.Client(
                client_id=self.client_id,
                callback_api_version=callback_api,
            )
        except (AttributeError, TypeError):
            # Older paho-mqtt versions don't accept callback_api_version
            self.client = mqtt.Client(client_id=self.client_id)

    def connect(self, on_connect=None):
        """Connect to broker and optionally set on_connect callback.

        on_connect: callable(client, userdata, flags, rc)
        """
        if on_connect:
            self.client.on_connect = on_connect
        try:
            self.client.connect(self.broker, self.port)
            self.client.loop_start()
            print(f"Connected to MQTT broker at {self.broker}:{self.port}")
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")

    def set_credentials(self, username: str, password: str):
        """Set username and password for broker authentication."""
        try:
            self.client.username_pw_set(username, password)
            print("MQTT credentials set.")
        except Exception as e:
            print(f"Failed to set MQTT credentials: {e}")

    def subscribe(self, topic):
        # Subscribe to a topic. Do not override the global on_message handler here;
        # use `set_on_message` to register a message handler.
        self.client.subscribe(topic)
        print(f"Subscribed to topic: {topic}")

    def set_on_message(self, callback):
        """Set a global on_message callback.

        Callback signature: callback(topic: str, payload: bytes)
        """
        def _on_message(client, userdata, msg):
            try:
                callback(msg.topic, msg.payload)
            except Exception:
                # swallow exceptions from user callback to avoid killing loop
                pass

        self.client.on_message = _on_message

    def publish(self, topic, payload):
        result = self.client.publish(topic, payload)
        # return the rc so caller can check success; also log
        try:
            rc = result.rc
        except AttributeError:
            # Older paho versions may return a tuple (rc, mid)
            rc = result[0] if isinstance(result, tuple) else None
        if rc == 0:
            print(f"Message published to topic {topic}")
        else:
            print(f"Failed to publish message to topic {topic} (rc={rc})")
        return rc

    def disconnect(self):
        """Stop network loop and disconnect from broker."""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            print("Disconnected from MQTT broker.")
        except Exception as e:
            print(f"Error while disconnecting MQTT client: {e}")
