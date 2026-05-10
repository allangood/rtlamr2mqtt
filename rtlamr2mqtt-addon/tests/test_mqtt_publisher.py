import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from mqtt_publisher import MQTTPublisher


@pytest.fixture
def publisher(sample_config):
    queue = asyncio.Queue()
    shutdown = asyncio.Event()
    return MQTTPublisher(
        config=sample_config,
        reading_queue=queue,
        shutdown_event=shutdown,
    )


class TestMQTTPublisherInit:
    def test_creates_instance(self, publisher):
        assert publisher is not None
        assert publisher.base_topic == 'rtlamr'

    def test_builds_tls_context_when_enabled(self, sample_config):
        sample_config['mqtt']['tls_enabled'] = True
        sample_config['mqtt']['tls_ca'] = '/etc/ssl/ca.crt'
        queue = asyncio.Queue()
        shutdown = asyncio.Event()
        with patch('ssl.create_default_context') as mock_ssl:
            mock_ctx = MagicMock()
            mock_ssl.return_value = mock_ctx
            pub = MQTTPublisher(config=sample_config, reading_queue=queue, shutdown_event=shutdown)
        assert pub.tls_context is not None

    def test_no_tls_context_when_disabled(self, publisher):
        assert publisher.tls_context is None


class TestMQTTPublisherDiscovery:
    async def test_publish_discovery_all_meters(self, publisher):
        mock_client = AsyncMock()
        await publisher.publish_discovery(mock_client)
        # Should publish one discovery message per meter
        assert mock_client.publish.call_count == len(publisher.meters)

    async def test_discovery_payload_structure(self, publisher):
        mock_client = AsyncMock()
        await publisher.publish_discovery(mock_client)
        call_args = mock_client.publish.call_args_list[0]
        topic = call_args.kwargs.get('topic') or call_args[0][0]
        assert 'homeassistant/device/' in topic
        assert '/config' in topic


class TestMQTTPublisherReadings:
    async def test_publish_reading(self, publisher):
        mock_client = AsyncMock()
        reading = {
            'meter_id': '33333333',
            'consumption': 1978226,
            'message': {'Type': 7, 'TamperPhy': 3},
        }
        await publisher.publish_reading(mock_client, reading)
        # Should publish status, state, and attributes = 3 calls
        assert mock_client.publish.call_count == 3

    async def test_publish_reading_formats_number(self, publisher):
        mock_client = AsyncMock()
        reading = {
            'meter_id': '33333333',
            'consumption': 1978226,
            'message': {'Type': 7},
        }
        await publisher.publish_reading(mock_client, reading)
        # Find the state publish call
        for call in mock_client.publish.call_args_list:
            topic = call.kwargs.get('topic') or call[0][0]
            if '/state' in topic and 'status' not in topic:
                import json
                payload = json.loads(call.kwargs.get('payload') or call[0][1])
                assert payload['reading'] == '001978.226'
                break


class _FakeClient:
    """Async context manager that behaves like aiomqtt.Client but doesn't
    connect to a real broker. Properly propagates exceptions (unlike
    AsyncMock, whose __aexit__ returns a truthy mock and swallows them)."""

    async def __aenter__(self):
        return AsyncMock()  # stands in for the connected client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False  # never suppress exceptions


class TestMQTTPublisherReconnect:
    async def test_run_survives_mqtt_exception_group(self, sample_config):
        """Publisher.run() must not crash when _run_connected raises
        ExceptionGroup wrapping MqttError.

        Reproduces the production crash from 2026-04-14:
            ERROR: Task error: unhandled errors in a TaskGroup (1 sub-exception)
            INFO: Goodbye!

        Without the fix, the ExceptionGroup propagates out of run() because
        `except aiomqtt.MqttError` doesn't match ExceptionGroup. With the
        fix, it's caught and run() reconnects.
        """
        import aiomqtt

        queue = asyncio.Queue()
        shutdown = asyncio.Event()
        pub = MQTTPublisher(
            config=sample_config,
            reading_queue=queue,
            shutdown_event=shutdown,
        )

        call_count = 0
        original_run_connected = pub._run_connected

        async def fake_run_connected(client):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Simulate the ExceptionGroup that TaskGroup produces
                # when both subtasks hit MqttError on broker disconnect
                raise ExceptionGroup(
                    "unhandled errors in a TaskGroup",
                    [aiomqtt.MqttError("Connection lost")],
                )
            # Second call: shut down cleanly so run() exits
            shutdown.set()

        pub._run_connected = fake_run_connected

        with patch('mqtt_publisher.aiomqtt.Client', return_value=_FakeClient()):
            with patch('mqtt_publisher.aiomqtt.Will'):
                try:
                    await asyncio.wait_for(pub.run(), timeout=10.0)
                except (ExceptionGroup, Exception) as e:
                    pytest.fail(
                        f"run() crashed with {type(e).__name__}: {e}\n"
                        "The MqttError ExceptionGroup was not caught by the "
                        "reconnection loop."
                    )

        assert call_count == 2, (
            f"Expected 2 connection attempts (crash + reconnect), got {call_count}"
        )


class TestMQTTPublisherStatus:
    async def test_publish_online(self, publisher):
        mock_client = AsyncMock()
        await publisher.publish_status(mock_client, 'online')
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        topic = call_args.kwargs.get('topic') or call_args[0][0]
        assert topic == 'rtlamr/status'
        payload = call_args.kwargs.get('payload') or call_args[0][1]
        assert payload == 'online'
