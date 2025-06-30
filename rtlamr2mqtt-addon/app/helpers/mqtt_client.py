"""
Helper functions for MQTT connection
"""

import ssl
import paho.mqtt.client as mqtt
from uuid import uuid4

class MQTTClient:
    """
    A class to handle MQTT client operations.
    """
    def __init__(self, logger, broker, port, username=None, password=None, tls_enabled=False, ca_cert=None, client_cert=None, tls_insecure=False, client_key=None, log_level=4):
        """
        Initialize the MQTT client.
        """
        self.client = mqtt.Client(client_id=f'rtlamr2mqtt-{uuid4().hex[-8:]}')
        self.broker = broker
        self.port = port
        self.logger = logger
        self.log_level = log_level
        self.last_message = None

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
        self.client.on_message = self.on_message

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
        if self.log_level >= 3:
            self.logger.info(f"Subscribing to {topic}")
        self.client.subscribe(topic, qos=qos)

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
