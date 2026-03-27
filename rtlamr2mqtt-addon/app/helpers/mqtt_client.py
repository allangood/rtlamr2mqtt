"""
Helper functions for MQTT connection
"""

import ssl
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from uuid import uuid4

class MQTTClient:
    """
    A class to handle MQTT client operations.
    """
    def __init__(self, logger, broker, port, username=None, password=None, tls_enabled=False, ca_cert=None, client_cert=None, tls_insecure=False, client_key=None, log_level=4):
        """
        Initialize the MQTT client.
        """
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f'rtlamr2mqtt-{uuid4().hex[-8:]}')
        self.broker = broker
        self.port = port
        self.logger = logger
        self.log_level = log_level
        self.last_message = None
        self.subscriptions = []

        # Set username and password if provided
        if username and password:
            self.client.username_pw_set(username, password)

        # Configure TLS if enabled
        if tls_enabled:
            self.client.tls_set(
                ca_certs=ca_cert,
                certfile=client_cert,
                keyfile=client_key,
                tls_version=ssl.PROTOCOL_TLSv1_2,
                cert_reqs=ssl.CERT_NONE if tls_insecure else ssl.CERT_REQUIRED
            )
            self.client.tls_insecure_set(tls_insecure)

        # Set callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        if self.log_level >= 4:
            self.client.on_log = self.on_log

    def on_connect(self, client, userdata, flags, reason_code, properties):
        """
        Callback for when the client receives a CONNACK response from the server.
        """
        if reason_code == 0:
            if self.log_level >= 3:
                self.logger.info("Connected to MQTT broker")
            # Re-subscribe to topics on connect/reconnect
            for topic, qos in self.subscriptions:
                if self.log_level >= 3:
                    self.logger.info(f"Subscribing to {topic}")
                self.client.subscribe(topic, qos)
        else:
            self.logger.error(f"Failed to connect to MQTT broker: {reason_code}")

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        """
        Callback for when the client disconnects from the broker.
        """
        if self.log_level >= 3:
            self.logger.warning(f"Disconnected from MQTT broker: {reason_code}")

    def on_log(self, client, userdata, level, buf):
        """
        Callback for MQTT logging.
        """
        if self.log_level >= 4:
            self.logger.debug(f"MQTT Log: {buf}")

    def set_last_will(self, topic, payload, qos=0, retain=False):
        """
        Set the Last Will and Testament (LWT).
        """
        self.client.will_set(topic, payload=payload, qos=qos, retain=retain)

    def connect(self):
        """
        Connect to the MQTT broker.
        """
        if self.log_level >= 3:
            self.logger.info(f"Connecting to MQTT broker at {self.broker}:{self.port}")
        self.client.connect(self.broker, self.port)

    def publish(self, topic, payload, qos=0, retain=False):
        """
        Publish a message to a topic.
        """
        if self.log_level >= 3:
            self.logger.info(f"Publishing to {topic}: {payload}")
        self.client.publish(topic, payload=payload, qos=qos, retain=retain)

    def subscribe(self, topic, qos=0):
        """
        Subscribe to a topic.
        """
        if (topic, qos) not in self.subscriptions:
            self.subscriptions.append((topic, qos))
        if self.client.is_connected():
            if self.log_level >= 3:
                self.logger.info(f"Subscribing to {topic}")
            self.client.subscribe(topic, qos)

    def on_message(self, client, userdata, message):
        """
        Default callback for incoming messages.
        """
        self.last_message = message

    def loop_start(self):
        """
        Start the MQTT client loop.
        """
        self.client.loop_start()

    def loop_stop(self):
        """
        Stop the MQTT client loop.
        """
        self.client.loop_stop()

    def loop(self):
        """
        Stop the MQTT client loop.
        """
        self.client.loop()

    def disconnect(self):
        """
        Disconnect from the MQTT broker.
        """
        if self.log_level >= 3:
            self.logger.info("Disconnecting from MQTT broker")
        self.client.disconnect()
