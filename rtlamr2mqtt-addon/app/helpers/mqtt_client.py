"""
Helper functions for MQTT connection
"""

import ssl
import paho.mqtt.client as mqtt
from paho.mqtt.enums import MQTTErrorCode,CallbackAPIVersion
from uuid import uuid4

class MQTTClient:
    """
    A class to handle MQTT client operations.
    """
    def __init__(self, logger, broker, port, username=None, password=None, tls_enabled=False, ca_cert=None, client_cert=None, tls_insecure=False, client_key=None, log_level=4):
        """
        Initialize the MQTT client.
        """
        self.client = mqtt.Client(client_id=f'rtlamr2mqtt-{uuid4().hex[-8:]}', callback_api_version = CallbackAPIVersion.VERSION2)
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
            self.logger.info(f"MQTT: Connecting to MQTT broker at {self.broker}:{self.port}")
        self.client.on_connect = self.on_connect
        self.client.connect(self.broker, self.port)
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe
        self.client.on_publish = self.on_publish

    def on_connect(self, client, userdata, connect_flags, reason_code, properties):
        if reason_code != 0: # 0 = Success
            self.logger.error(f"MQTT: Unable to connect to {self.broker}:{self.port} ({reason_code})")
        else:
            if self.log_level >= 3:
                self.logger.info(f"MQTT: Successfully connected to {self.broker}:{self.port}")

    def publish(self, topic, payload, qos=0, retain=False):
        """
        Publish a message to a topic.
        """
        if self.log_level >= 3:
            self.logger.info(f"MQTT: Publishing to {topic}  with {qos=} and {retain=}: {payload}")
        (result, mid) = self.client.publish(topic, payload=payload, qos=qos, retain=retain)
        if self.log_level >= 4:
            self.logger.debug(f"MQTT: `- mid for this publish is {mid}")
        # At this stage we could receive MQTT_ERR_NO_CONN if the client is not currently connected
        if result != MQTTErrorCode.MQTT_ERR_SUCCESS:
            self.logger.error(f"MQTT: Unable to publish to {topic} ({result.name})")

    def on_publish(self, client, userdata, mid, reason_code, properties):
        # Note: MQTT < 5 does not support reason codes for publish
        if reason_code != 0: # 0 = success
            self.logger.error(f"MQTT: Unable to publish mid {mid} ({reason_code})")
        else:
            if self.log_level >= 3:
                self.logger.info(f"MQTT: Successfully published mid {mid}")

    def subscribe(self, topic, qos=0):
        """
        Subscribe to a topic.
        """
        if self.log_level >= 3:
            self.logger.info(f"MQTT: Subscribing to {topic}")
        (result, mid) = self.client.subscribe(topic, qos=qos)
        if self.log_level >= 4:
            self.logger.debug(f"MQTT: `- mid for this subscription is {mid}")
        # At this stage we could receive MQTT_ERR_NO_CONN if the client is not currently connected
        if result != MQTTErrorCode.MQTT_ERR_SUCCESS:
            self.logger.error(f"MQTT: Unable to subscribe to {topic} ({result.name})")

    def on_subscribe(self, client, userdata, mid, reason_code_list, properties):
        # Reason code list: https://github.com/eclipse-paho/paho.mqtt.python/blob/d45de3737879cfe7a6acc361631fa5cb1ef584bb/src/paho/mqtt/reasoncodes.py#L61
        # Note: MQTT < 5 only supports 1 kind of failure reason code
        for reason in reason_code_list:
            if reason in [0,1,2]: # Granted QoS levels
                if self.log_level >= 3:
                    self.logger.info(f"MQTT: Successfully subscribed to mid {mid} with {reason}")
            elif reason >= 128: # Errors (>= 0x80)
                self.logger.error(f"MQTT: Failed to subscribe to mid {mid} ({reason})")
 
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

    def is_connected(self):
        return self.client.is_connected()

    def disconnect(self):
        """
        Disconnect from the MQTT broker.
        """
        if self.log_level >= 3:
            self.logger.info("MQTT: Disconnecting from MQTT broker")
        self.client.disconnect()
