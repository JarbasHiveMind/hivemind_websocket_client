import base64
import json
import logging
import ssl
import time
import traceback
from threading import Event, Thread

from pyee import ExecutorEventEmitter
from websocket import WebSocketApp, WebSocketConnectionClosedException, \
    WebSocketException

from hivemind_bus_client.message import HiveMessage, HiveMessageType
from hivemind_bus_client.util import serialize_message, \
    encrypt_as_json, decrypt_from_json
from ovos_bus_client import Message as MycroftMessage

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
                 useragent="HiveMessageBusClientV0.0.1", self_signed=False):
        self.ssl = host.startswith("wss://")
        self.key = key
        self.useragent = useragent
        self.crypto_key = crypto_key
        self.host = host.replace("ws://", "").replace("wss://", "").strip()
        self.port = port
        self.emitter = ExecutorEventEmitter()
        self.client = self.create_client()
        self.retry = 5
        self.connected_event = Event()
        self.started_running = False
        self.allow_self_signed = self_signed
        self._mycroft_events = {}  # msg_type: [handler]

    @staticmethod
    def build_url(key, host='127.0.0.1', port=5678,
                  useragent="HiveMessageBusClientV0.0.1", ssl=True):
        scheme = 'wss' if ssl else 'ws'
        key = base64.b64encode(f"{useragent}:{key}".encode("utf-8")) \
            .decode("utf-8")
        return f'{scheme}://{host}:{port}?authorization={key}'

    def create_client(self):
        url = self.build_url(ssl=self.ssl,
                             host=self.host,
                             port=self.port,
                             key=self.key,
                             useragent=self.useragent)
        return WebSocketApp(url, on_open=self.on_open, on_close=self.on_close,
                            on_error=self.on_error, on_message=self.on_message)

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
    def on_open(self, _):
        LOG.info("Connected")
        self.connected_event.set()
        self.emitter.emit("open")
        # Restore reconnect timer to 5 seconds on sucessful connect
        self.retry = 5

    def on_close(self, _):
        self.emitter.emit("close")

    def on_error(self, _, error):
        """ On error start trying to reconnect to the websocket. """
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

    def on_message(self, _, message):
        if self.crypto_key:
            if "ciphertext" in message:
                message = decrypt_from_json(self.crypto_key, message)
            else:
                LOG.warning("Message was unencrypted")
        if isinstance(message, str):
            message = json.loads(message)
        self.emitter.emit('message', message)  # raw message
        self._handle_hive_protocol(HiveMessage(**message))

    def _handle_hive_protocol(self, message):
        if message.msg_type == HiveMessageType.BUS:
            self._fire_mycroft_handlers(message)
        self.emitter.emit(message.msg_type, message)  # hive message

    def emit(self, message):
        if not self.connected_event.wait(10):
            if not self.started_running:
                raise ValueError('You must execute run_forever() '
                                 'before emitting messages')
            self.connected_event.wait()

        if isinstance(message, MycroftMessage):
            message = HiveMessage(msg_type=HiveMessageType.BUS,
                                  payload=message)
        try:
            # auto inject context for proper routing, this is confusing for
            # end users if they need to do it manually, error prone and easy
            # to forget
            if message.msg_type == HiveMessageType.BUS:
                ctxt = dict(message.payload.context)
                if "source" not in ctxt:
                    ctxt["source"] = self.useragent
                if "platform" not in message.payload.context:
                    ctxt["platform"] = self.useragent
                if "destination" not in message.payload.context:
                    ctxt["destination"] = "HiveMind"
                message.payload.context = ctxt
            payload = serialize_message(message)
            if self.crypto_key:
                payload = encrypt_as_json(self.crypto_key, payload)

            self.client.send(payload)
        except WebSocketConnectionClosedException:
            LOG.warning(f'Could not send {message.msg_type} message because connection '
                        'has been closed')

    # mycroft events api
    def _fire_mycroft_handlers(self, message):
        handlers = []
        if isinstance(message, MycroftMessage):
            handlers = self._mycroft_events.get(message.msg_type) or []
        elif message.msg_type == HiveMessageType.BUS:
            handlers = self._mycroft_events.get(message.payload.msg_type) or []
        for func in handlers:
            try:
                func(message.payload)
            except Exception as e:
                LOG.exception("Failed to call event handler")
                continue

    def emit_mycroft(self, message):
        message = HiveMessage(msg_type=HiveMessageType.BUS, payload=message)
        self.emit(message)

    def on_mycroft(self, mycroft_msg_type, func):
        self._mycroft_events[mycroft_msg_type] = self._mycroft_events.get(mycroft_msg_type) or []
        self._mycroft_events[mycroft_msg_type].append(func)

    # event api
    def on(self, event_name, func):
        if event_name not in list(HiveMessageType):
            # assume it's a mycroft message
            # this could be done better,
            # but makes this lib almost a drop in replacement
            # for the mycroft bus client
            self.on_mycroft(event_name, func)
        else:
            # hivemind message
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

    def wait_for_mycroft(self, mycroft_msg_type, timeout=3.0):
        return self.wait_for_payload(mycroft_msg_type, timeout=timeout,
                                     message_type=HiveMessageType.BUS)

    def wait_for_response(self, message, reply_type=None, timeout=3.0):
        """Send a message and wait for a response.

        Arguments:
            message (HiveMessage): message to send, mycroft Message objects also accepted
            reply_type (HiveMessageType): the message type of the expected reply.
                                          Defaults to "<message.msg_type>".
            timeout: seconds to wait before timeout, defaults to 3

        Returns:
            The received message or None if the response timed out
        """
        if isinstance(message, MycroftMessage):
            message = HiveMessage(msg_type=HiveMessageType.BUS, payload=message)
        message_type = reply_type or message.msg_type
        waiter = HiveMessageWaiter(self, message_type)  # Setup response handler
        # Send message and wait for it's response
        self.emit(message)
        return waiter.wait(timeout)

    def wait_for_payload_response(self, message, payload_type,
                                  reply_type=None, timeout=3.0):
        """Send a message and wait for a response.

        Arguments:
            message (HiveMessage): message to send, mycroft Message objects also accepted
            payload_type (str): the message type of the expected payload
            reply_type (HiveMessageType): the message type of the expected reply.
                                          Defaults to "<message.msg_type>".
            timeout: seconds to wait before timeout, defaults to 3

        Returns:
            The received message or None if the response timed out
        """
        if isinstance(message, MycroftMessage):
            message = HiveMessage(msg_type=HiveMessageType.BUS, payload=message)
        message_type = reply_type or message.msg_type
        waiter = HivePayloadWaiter(bus=self, payload_type=payload_type,
                                   message_type=message_type)  # Setup
        # response handler
        # Send message and wait for it's response
        self.emit(message)
        return waiter.wait(timeout)


class HiveNodeClient(HiveMessageBusClient):
    """
    Same as HiveMessageBusClient, but parses hivemind protocol messages.
        ie, it will execute PROPAGATE, ESCALATE, BROADCAST etc.

    Some message types can only be handled by hivemind server (eg. BROADCAST)
    a mycroft websocket connection is needed to forward requests over it,
    if a hivemind server is connected to the same bus they will be handled

    """

    def __init__(self, key, bus=None, crypto_key=None, host='127.0.0.1', port=5678,
                 useragent="HiveNodeClientV0.0.1", share_bus=False, *args, **kwargs):
        self.bus = None
        self.peer = None
        self.node_id = None
        self.share_bus = share_bus
        if bus:
            self.bind(bus)
        super().__init__(key, crypto_key=crypto_key, host=host, port=port,
                         useragent=useragent, *args, **kwargs)

    def bind(self, bus):
        self.bus = bus
        self.bus.on('hive.send.upstream', self.handle_mycroft_send)
        self.bus.on("message", self.handle_outgoing_mycroft)

    def _handle_hive_protocol(self, message):
        if self.bus:
            self.bus.emit(MycroftMessage("hive.message.received"))

        if message.msg_type == HiveMessageType.HELLO:
            self.handle_hello(message)
        if message.msg_type == HiveMessageType.BROADCAST:
            self.handle_broadcast(message)
        if message.msg_type == HiveMessageType.PROPAGATE:
            self.handle_propagate(message)
        if message.msg_type == HiveMessageType.ESCALATE:
            self.handle_illegal_msg(message)
        if message.msg_type == HiveMessageType.BUS:
            self.handle_bus(message)
        super()._handle_hive_protocol(message)

    # hivemind events
    def handle_illegal_msg(self, message):
        # this should not happen,
        # ESCALATE is only sent from client -> server NOT server -> client
        # TODO log, kill connection (?)
        pass

    def handle_hello(self, message):
        node_id = message.payload.get("node_id", "").replace("127.0.0.1", "0.0.0.0")
        expected_id = f"tcp4:{self.host}:{self.port}:".replace("127.0.0.1", "0.0.0.0")
        # HACK: this check is because other nodes in the hive
        # may also send HELLO with their pubkey
        # only want this on the first connection
        if not self.peer and node_id.startswith(expected_id):
            self.node_id = node_id
            LOG.info(f"Connected to HiveMind: {node_id}")
            self.peer = message.payload["peer"]

    def handle_bus(self, message):
        assert isinstance(message.payload, MycroftMessage)
        # inject message into mycroft bus
        if not self.bus:
            LOG.warning("Can not inject mycroft message, not connected to mycroft bus")
            return
        self.bus.emit(message.payload)

    def handle_broadcast(self, message):
        # tell any connected hivemind server to send this to all clients
        if not self.bus:
            LOG.warning("Can not broadcast hive message, not connected to mycroft bus")
            return
        data = json.loads(serialize_message(message))
        self.bus.emit(MycroftMessage('hive.send.downstream', data))

    def handle_propagate(self, message):
        # tell any connected hivemind server to send this to all clients
        # (we don't send it upstream because it came from there)
        if not self.bus:
            LOG.warning("Can not propagate hive message, not connected to mycroft bus")
            return
        data = json.loads(serialize_message(message))
        ctxt = {"node_id": self.node_id, "peer": self.peer}
        self.bus.emit(MycroftMessage('hive.send.downstream', data, ctxt))

    # mycroft bus events
    def handle_outgoing_mycroft(self, message):
        peer = message.context.get("destination")
        message.context["source"] = message.context["node_id"] = self.node_id

        # this allows the master node to do passive monitoring of bus events
        if self.share_bus:
            msg = HiveMessage(HiveMessageType.SHARED_BUS,
                              source_peer=self.peer,
                              payload=message.serialize())
            self.emit(msg)

        # message is explicitly targeted to master
        if peer and peer == self.peer:
            msg = HiveMessage(HiveMessageType.BUS,
                              source_peer=self.peer,
                              payload=message.serialize())
            self.emit(msg)

    def handle_mycroft_send(self, message):
        # something connected to mycroft bus wants to send a hive message
        msg_type = message.data.get("msg_type")
        msg = HiveMessage(msg_type, message.data["payload"])

        if msg_type == HiveMessageType.BUS:
            self.emit(msg)
        if msg_type == HiveMessageType.SHARED_BUS:
            self.emit(msg)
        if msg_type == HiveMessageType.ESCALATE:
            self.emit(msg)
        if msg_type == HiveMessageType.PROPAGATE:
            self.emit(msg)

        self.bus.emit(message.reply("hive.message.sent"))
