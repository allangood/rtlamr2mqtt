"""
Async MQTT publisher using aiomqtt.
Handles connection, discovery, reading publication, and HA status monitoring.
"""

import asyncio
import ssl
import logging
from json import dumps
from datetime import datetime
from uuid import uuid4

import aiomqtt

import helpers.ha_messages as ha_msgs
import helpers.read_output as ro

logger = logging.getLogger('rtlamr2mqtt')


class MQTTPublisher:
    """
    Async MQTT publisher that:
    - Connects to the broker with LWT
    - Publishes HA discovery for all meters
    - Consumes readings from a queue and publishes state/attributes
    - Listens for HA status and re-publishes discovery on HA restart
    - Reconnects with backoff on disconnect
    """

    def __init__(self, config: dict, reading_queue: asyncio.Queue, shutdown_event: asyncio.Event):
        mqtt_config = config['mqtt']
        self.host = mqtt_config['host']
        self.port = mqtt_config['port']
        self.username = mqtt_config['user']
        self.password = mqtt_config['password']
        self.base_topic = mqtt_config['base_topic']
        self.ha_status_topic = mqtt_config['ha_status_topic']
        self.ha_autodiscovery_topic = mqtt_config['ha_autodiscovery_topic']
        self.meters = config['meters']
        self.reading_queue = reading_queue
        self.shutdown_event = shutdown_event

        # Build TLS context if enabled
        self.tls_context = None
        if mqtt_config['tls_enabled']:
            self.tls_context = ssl.create_default_context()
            if mqtt_config['tls_ca']:
                self.tls_context.load_verify_locations(mqtt_config['tls_ca'])
            if mqtt_config['tls_cert'] and mqtt_config['tls_keyfile']:
                self.tls_context.load_cert_chain(mqtt_config['tls_cert'], mqtt_config['tls_keyfile'])
            if mqtt_config['tls_insecure']:
                self.tls_context.check_hostname = False
                self.tls_context.verify_mode = ssl.CERT_NONE

    async def run(self):
        """
        Main loop: connect, publish discovery, consume queue.
        Reconnects with backoff on disconnect.
        """
        while not self.shutdown_event.is_set():
            try:
                will = aiomqtt.Will(
                    topic=f'{self.base_topic}/status',
                    payload='offline',
                    qos=1,
                    retain=False,
                )
                async with aiomqtt.Client(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    tls_context=self.tls_context,
                    will=will,
                    identifier=f'rtlamr2mqtt-{uuid4().hex[-8:]}',
                ) as client:
                    logger.info('Connected to MQTT broker at %s:%d', self.host, self.port)
                    try:
                        await self._run_connected(client)
                    finally:
                        # Publish offline on graceful disconnect (LWT only fires on unclean disconnect)
                        try:
                            await self.publish_status(client, 'offline')
                        except Exception:
                            pass
            except aiomqtt.MqttError as e:
                # Direct MqttError — e.g. initial connection failure, broker
                # unreachable. aiomqtt.Client().__aenter__() raises this
                # before _run_connected is even called.
                if self.shutdown_event.is_set():
                    break
                logger.warning('MQTT connection lost: %s. Reconnecting in 5s...', e)
                await asyncio.sleep(5)
            except BaseException as e:
                # _run_connected uses a TaskGroup whose subtasks can raise
                # MqttError when the broker drops mid-session. The TaskGroup
                # wraps these in an ExceptionGroup — a distinct type that
                # does NOT match `except MqttError` above (ExceptionGroup
                # contains MqttError but is not a subclass of it).
                if isinstance(e, asyncio.CancelledError):
                    break
                if isinstance(e, ExceptionGroup) and any(
                    isinstance(sub, aiomqtt.MqttError) for sub in e.exceptions
                ):
                    if self.shutdown_event.is_set():
                        break
                    logger.warning(
                        'MQTT connection lost (via TaskGroup): %s. Reconnecting in 5s...',
                        e.exceptions[0],
                    )
                    await asyncio.sleep(5)
                    continue
                raise

        logger.info('MQTT publisher shutting down')

    async def _run_connected(self, client: aiomqtt.Client):
        """
        Runs while connected: publish discovery, subscribe to HA status,
        and consume readings concurrently.
        """
        await self.publish_discovery(client)
        await self.publish_status(client, 'online')
        await client.subscribe(self.ha_status_topic, qos=1)

        # Run HA status listener and reading consumer concurrently
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._listen_ha_status(client))
            tg.create_task(self._consume_readings(client))

    async def _listen_ha_status(self, client: aiomqtt.Client):
        """
        Listen for HA status messages. Re-publish discovery when HA restarts.
        Exits cooperatively when shutdown_event is set.
        """
        messages = aiter(client.messages)
        while not self.shutdown_event.is_set():
            try:
                message = await asyncio.wait_for(
                    anext(messages),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                continue
            except (StopAsyncIteration, asyncio.CancelledError):
                break
            if message.topic.matches(self.ha_status_topic):
                payload = message.payload.decode('utf-8', errors='replace')
                logger.info('HA status: %s', payload)
                if payload == 'online':
                    await self.publish_discovery(client)
                    await self.publish_status(client, 'online')

    async def _consume_readings(self, client: aiomqtt.Client):
        """
        Consume readings from the queue and publish them.
        """
        while not self.shutdown_event.is_set():
            try:
                reading = await asyncio.wait_for(self.reading_queue.get(), timeout=1.0)
                await self.publish_reading(client, reading)
                self.reading_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def publish_discovery(self, client):
        """
        Publish HA MQTT discovery messages for all configured meters.
        """
        for meter_id, meter_config in self.meters.items():
            discovery_payload = ha_msgs.meter_discover_payload(self.base_topic, meter_config)
            topic = f'{self.ha_autodiscovery_topic}/device/{meter_id}/config'
            await client.publish(
                topic=topic,
                payload=dumps(discovery_payload),
                qos=1,
                retain=False,
            )
            logger.debug('Published discovery for meter %s', meter_id)

    async def publish_reading(self, client, reading: dict):
        """
        Publish a meter reading: status, state, and attributes.
        """
        meter_id = reading['meter_id']
        meter_config = self.meters.get(meter_id, {})
        consumption = reading['consumption']

        # Format the reading if format is configured
        fmt = meter_config.get('format')
        if fmt:
            formatted = ro.format_number(consumption, fmt)
        else:
            formatted = consumption

        # Publish online status
        await self.publish_status(client, 'online')

        # Publish state
        timestamp = datetime.now().astimezone().replace(microsecond=0).isoformat()
        payload = {'reading': formatted, 'lastseen': timestamp}
        await client.publish(
            topic=f'{self.base_topic}/{meter_id}/state',
            payload=dumps(payload),
            qos=1,
            retain=False,
        )

        # Publish attributes
        attributes = dict(reading['message'])
        attributes['protocol'] = meter_config.get('protocol', 'unknown')
        await client.publish(
            topic=f'{self.base_topic}/{meter_id}/attributes',
            payload=dumps(attributes),
            qos=1,
            retain=False,
        )

        logger.info('Published reading for meter %s: %s', meter_id, formatted)

    async def publish_status(self, client, status: str):
        """
        Publish online/offline status.
        """
        await client.publish(
            topic=f'{self.base_topic}/status',
            payload=status,
            qos=1,
            retain=False,
        )
