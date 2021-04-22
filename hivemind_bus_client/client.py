import base64
import time
import traceback
from threading import Event, Thread
import ssl
import json
import logging
from pyee import ExecutorEventEmitter
from websocket import WebSocketApp, WebSocketConnectionClosedException,  \
    WebSocketException
from hivemind_bus_client.message import HiveMessage, HiveMessageType
from hivemind_bus_client.util import serialize_message, \
    encrypt_as_json, decrypt_from_json


LOG = logging.getLogger("HiveMind-websocket-client")


class HiveMessageWaiter:
    """Wait for a single message.

    Encapsulate the wait for a message logic separating the setup from
    the actual waiting act so the waiting can be setuo, actions can be
    performed and _then_ the message can be waited for.

    Argunments:
        bus: Bus to check for messages on
        message_type: message type to wait for
    """

    def __init__(self, bus, message_type):
        self.bus = bus
        self.msg_type = message_type
        self.received_msg = None
        # Setup response handler
        self.response_event = Event()
        self.bus.once(message_type, self._handler)

    def _handler(self, message):
        """Receive response data."""
        self.received_msg = message
        self.response_event.set()

    def wait(self, timeout=3.0):
        """Wait for message.

        Arguments:
            timeout (int or float): seconds to wait for message

        Returns:
            HiveMessage or None
        """
        self.response_event.wait(timeout)
        if not self.response_event.is_set():
            # Clean up the event handler
            try:
                self.bus.remove(self.msg_type, self._handler)
            except (ValueError, KeyError):
                # ValueError occurs on pyee 5.0.1 removing handlers
                # registered with once.
                # KeyError may theoretically occur if the event occurs as
                # the handler is removed
                pass
        return self.received_msg


class HivePayloadWaiter(HiveMessageWaiter):
    def __init__(self, payload_type=HiveMessageType.THIRDPRTY, *args, **kwargs):
        super(HivePayloadWaiter, self).__init__(*args, **kwargs)
        self.payload_type = payload_type

    def _handler(self, message):
        """Receive response data."""
        if message.payload.msg_type == self.payload_type:
            self.received_msg = message
            self.response_event.set()
        else:
            self.bus.once(self.msg_type, self._handler)


class HiveMessageBusClient:
    def __init__(self, key, crypto_key=None, host='127.0.0.1', port=5678,
                 useragent="HiveMessageBusClientV0.0.1", ssl=True,
                 self_signed=False):
        self.ssl = ssl
        self.key = key
        self.useragent = useragent
        self.crypto_key = crypto_key
        self.host = host
        self.port = port
        self.emitter = ExecutorEventEmitter()
        self.client = self.create_client()
        self.retry = 5
        self.connected_event = Event()
        self.started_running = False
        self.allow_self_signed = self_signed

    @staticmethod
    def build_url(key, host='127.0.0.1', port=5678,
                  useragent="HiveMessageBusClientV0.0.1", ssl=True):
        scheme = 'wss' if ssl else 'ws'
        key = base64.b64encode(f"{useragent}:{key}".encode("utf-8"))\
            .decode("utf-8")
        return f'{scheme}://{host}:{port}?authorization={key}'

    def create_client(self):
        url = self.build_url(ssl=self.ssl,
                             host=self.host,
                             port=self.port,
                             key=self.key,
                             useragent=self.useragent)
        return WebSocketApp(url, on_open=self.on_open, on_close=self.on_close,
                            on_error=self.on_error,
                            on_message=self.on_message)

    def run_in_thread(self):
        """Launches the run_forever in a separate daemon thread."""
        t = Thread(target=self.run_forever)
        t.daemon = True
        t.start()
        return t

    def run_forever(self):
        self.started_running = True
        if self.allow_self_signed:
            self.client.run_forever(sslopt={
                "cert_reqs": ssl.CERT_NONE,
                "check_hostname": False,
                "ssl_version": ssl.PROTOCOL_TLSv1})
        else:
            self.client.run_forever()

    def close(self):
        self.client.close()
        self.connected_event.clear()

    # event handlers
    def on_open(self):
        LOG.info("Connected")
        self.connected_event.set()
        self.emitter.emit("open")
        # Restore reconnect timer to 5 seconds on sucessful connect
        self.retry = 5

    def on_close(self):
        self.emitter.emit("close")

    def on_error(self, error):
        """ On error start trying to reconnect to the websocket. """
        if isinstance(error, WebSocketConnectionClosedException):
            LOG.warning('Could not send message because connection has closed')
        else:
            LOG.exception('=== ' + repr(error) + ' ===')

        try:
            self.emitter.emit('error', error)
            if self.client.keep_running:
                self.client.close()
        except Exception as e:
            LOG.error('Exception closing websocket: ' + repr(e))

        LOG.warning(
            "HiveMessage Bus Client will reconnect in %d seconds." % self.retry
        )
        time.sleep(self.retry)
        self.retry = min(self.retry * 2, 60)
        try:
            self.emitter.emit('reconnecting')
            self.client = self.create_client()
            self.run_forever()
        except WebSocketException:
            pass

    def on_message(self, message):
        if self.crypto_key:
            if "ciphertext" in message:
                message = decrypt_from_json(self.crypto_key,  message)
            else:
                LOG.warning("Message was unencrypted")
        if isinstance( message, str):
            message = json.loads(message)
        self.emitter.emit('message', message)
        parsed_message = HiveMessage(**message)
        self.emitter.emit(parsed_message.msg_type, parsed_message)

    def emit(self, message):
        if not self.connected_event.wait(10):
            if not self.started_running:
                raise ValueError('You must execute run_forever() '
                                 'before emitting messages')
            self.connected_event.wait()
        try:
            # auto inject context for proper routing, this is confusing for
            # end users if they need to do it manually, error prone and easy
            # to forget
            if message.msg_type == HiveMessageType.BUS:
                ctxt = message.payload.context
                if "source" not in ctxt :
                    ctxt["source"] = self.useragent
                if "platform" not in message.payload.context:
                    ctxt["platform"] = self.useragent
                if "destination" not in message.payload.context:
                    ctxt["destination"] = "JarbasHiveMind"
                message._payload["context"] = ctxt
            payload = serialize_message(message)
            if self.crypto_key:
                payload = encrypt_as_json(self.crypto_key, payload)

            self.client.send(payload)
        except WebSocketConnectionClosedException:
            LOG.warning('Could not send {} message because connection '
                        'has been closed'.format(message.msg_type))

    # event api
    def on(self, event_name, func):
        self.emitter.on(event_name, func)

    def once(self, event_name, func):
        self.emitter.once(event_name, func)

    def remove(self, event_name, func):
        try:
            if not event_name in self.emitter._events:
                LOG.debug("Not able to find '" + str(event_name) + "'")
            self.emitter.remove_listener(event_name, func)
        except ValueError:
            LOG.warning('Failed to remove event {}: {}'.format(event_name,
                                                               str(func)))
            for line in traceback.format_stack():
                LOG.warning(line.strip())

            if not event_name in self.emitter._events:
                LOG.debug("Not able to find '" + str(event_name) + "'")
            LOG.warning("Existing events: " + str(self.emitter._events))
            for evt in self.emitter._events:
                LOG.warning("   " + str(evt))
                LOG.warning("       " + str(self.emitter._events[evt]))
            if event_name in self.emitter._events:
                LOG.debug("Removing found '" + str(event_name) + "'")
            else:
                LOG.debug("Not able to find '" + str(event_name) + "'")
            LOG.warning('----- End dump -----')

    def remove_all_listeners(self, event_name):
        """Remove all listeners connected to event_name.

            Arguments:
                event_name: event from which to remove listeners
        """
        if event_name is None:
            raise ValueError
        self.emitter.remove_all_listeners(event_name)

    # utility
    def wait_for_message(self, message_type, timeout=3.0):
        """Wait for a message of a specific type.

        Arguments:
            message_type (HiveMessageType): the message type of the expected message
            timeout: seconds to wait before timeout, defaults to 3

        Returns:
            The received message or None if the response timed out
        """

        return HiveMessageWaiter(self, message_type).wait(timeout)

    def wait_for_payload(self, payload_type,
                         message_type=HiveMessageType.THIRDPRTY,
                         timeout=3.0):
        """Wait for a message of a specific type + payload of a specific type.

        Arguments:
            payload_type (str): the message type of the expected payload
            message_type (HiveMessageType): the message type of the expected message
            timeout: seconds to wait before timeout, defaults to 3

        Returns:
            The received message or None if the response timed out
        """

        return HivePayloadWaiter(bus=self, payload_type=payload_type,
                                 message_type=message_type).wait(timeout)

    def wait_for_response(self, message, reply_type=None, timeout=3.0):
        """Send a message and wait for a response.

        Arguments:
            message (HiveMessage): message to send
            reply_type (HiveMessageType): the message type of the expected reply.
                                          Defaults to "<message.msg_type>".
            timeout: seconds to wait before timeout, defaults to 3

        Returns:
            The received message or None if the response timed out
        """
        message_type = reply_type or message.msg_type
        waiter = HiveMessageWaiter(self, message_type)  # Setup response handler
        # Send message and wait for it's response
        self.emit(message)
        return waiter.wait(timeout)

    def wait_for_payload_response(self, message, payload_type,
                                  reply_type=None, timeout=3.0):
        """Send a message and wait for a response.

        Arguments:
            message (HiveMessage): message to send
            payload_type (str): the message type of the expected payload
            reply_type (HiveMessageType): the message type of the expected reply.
                                          Defaults to "<message.msg_type>".
            timeout: seconds to wait before timeout, defaults to 3

        Returns:
            The received message or None if the response timed out
        """
        message_type = reply_type or message.msg_type
        waiter = HivePayloadWaiter(bus=self, payload_type=payload_type,
                                   message_type=message_type)  # Setup
        # response handler
        # Send message and wait for it's response
        self.emit(message)
        return waiter.wait(timeout)