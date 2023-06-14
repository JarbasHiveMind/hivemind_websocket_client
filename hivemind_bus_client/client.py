import base64
import json
import ssl
from threading import Event
from typing import Union

from ovos_bus_client import Message as MycroftMessage, MessageBusClient as OVOSBusClient
from ovos_utils.log import LOG
from ovos_utils.messagebus import FakeBus
from websocket import WebSocketApp, WebSocketConnectionClosedException

from hivemind_bus_client.message import HiveMessage, HiveMessageType
from hivemind_bus_client.util import serialize_message, \
    encrypt_as_json, decrypt_from_json


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


class HiveMessageBusClient(OVOSBusClient):
    def __init__(self, key, password=None, crypto_key=None, host='127.0.0.1', port=5678,
                 useragent="HiveMessageBusClientV0.0.1", self_signed=True, share_bus=False):
        ssl = host.startswith("wss://")
        host = host.replace("ws://", "").replace("wss://", "").strip()
        self.key = key
        self.useragent = useragent
        self.crypto_key = crypto_key
        self.password = password
        self.allow_self_signed = self_signed
        self._mycroft_events = {}  # msg_type: [handler]
        self.password = password
        self.share_bus = share_bus
        self.handshake_event = Event()
        super().__init__(host=host, port=port, ssl=ssl)

    def connect(self, bus=FakeBus()):
        from hivemind_bus_client.protocol import HiveMindSlaveProtocol
        from hivemind_bus_client.identity import NodeIdentity
        ident = NodeIdentity()
        ident.password = self.password or ident.password
        LOG.info("Initializing HiveMindSlaveProtocol")
        self.protocol = HiveMindSlaveProtocol(self,
                                              shared_bus=self.share_bus,
                                              identity=ident)
        LOG.info("Connecting to Hivemind")
        self.run_in_thread()
        self.protocol.bind(bus)
        self.handshake_event.wait()

    @staticmethod
    def build_url(key, host='127.0.0.1', port=5678,
                  useragent="HiveMessageBusClientV0.0.1", ssl=True):
        scheme = 'wss' if ssl else 'ws'
        key = base64.b64encode(f"{useragent}:{key}".encode("utf-8")) \
            .decode("utf-8")
        return f'{scheme}://{host}:{port}?authorization={key}'

    def create_client(self):
        url = self.build_url(ssl=self.config.ssl,
                             host=self.config.host,
                             port=self.config.port,
                             key=self.key,
                             useragent=self.useragent)
        return WebSocketApp(url, on_open=self.on_open, on_close=self.on_close,
                            on_error=self.on_error, on_message=self.on_message)

    def run_forever(self):
        self.started_running = True
        if self.allow_self_signed:
            self.client.run_forever(sslopt={
                "cert_reqs": ssl.CERT_NONE,
                "check_hostname": False,
                "ssl_version": ssl.PROTOCOL_TLSv1})
        else:
            self.client.run_forever()

    # event handlers
    def on_message(self,*args):
        if len(args) == 1:
            message = args[0]
        else:
            message = args[1]
        if self.crypto_key:
            if "ciphertext" in message:
                LOG.info(f"got encrypted message: {len(message)}")
                message = decrypt_from_json(self.crypto_key, message)
            else:
                LOG.warning("Message was unencrypted")
        if isinstance(message, str):
            message = json.loads(message)
        LOG.info(f"received HiveMind message: {message}")
        self.emitter.emit('message', message)  # raw message
        self._handle_hive_protocol(HiveMessage(**message))

    def _handle_hive_protocol(self, message: HiveMessage):
        if message.msg_type == HiveMessageType.BUS:
            self._fire_mycroft_handlers(message)
        self.emitter.emit(message.msg_type, message)  # hive message

    def emit(self, message: Union[MycroftMessage, HiveMessage]):
        if isinstance(message, MycroftMessage):
            message = HiveMessage(msg_type=HiveMessageType.BUS,
                                  payload=message)
        if not self.connected_event.is_set():
            LOG.warning("hivemind connection not ready")
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
                ctxt = dict(message.payload.context)
                if "source" not in ctxt:
                    ctxt["source"] = self.useragent
                if "platform" not in message.payload.context:
                    ctxt["platform"] = self.useragent
                if "destination" not in message.payload.context:
                    ctxt["destination"] = "HiveMind"
                message.payload.context = ctxt
            payload = serialize_message(message)
            LOG.info(f"sending to HiveMind: {payload}")
            if self.crypto_key:
                payload = encrypt_as_json(self.crypto_key, payload)
                LOG.info(f"encrypted size: {len(payload)}")

            self.client.send(payload)
        except WebSocketConnectionClosedException:
            LOG.warning(f'Could not send {message.msg_type} message because connection '
                        'has been closed')

    # mycroft events api
    def _fire_mycroft_handlers(self, message: Union[MycroftMessage, HiveMessage]):
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

    def emit_mycroft(self, message: MycroftMessage):
        message = HiveMessage(msg_type=HiveMessageType.BUS, payload=message)
        self.emit(message)

    def on_mycroft(self, mycroft_msg_type, func):
        LOG.info(f"registering mycroft event: {mycroft_msg_type}")
        self._mycroft_events[mycroft_msg_type] = self._mycroft_events.get(mycroft_msg_type) or []
        self._mycroft_events[mycroft_msg_type].append(func)

    # event api
    def on(self, event_name, func):
        if event_name not in list(HiveMessageType):
            # assume it's a mycroft message
            # this could be done better,
            # but makes this lib almost a drop in replacement
            # for the mycroft bus client
            LOG.info(f"registering mycroft handler: {event_name}")
            self.on_mycroft(event_name, func)
        else:
            # hivemind message
            LOG.info(f"registering handler: {event_name}")
            self.emitter.on(event_name, func)

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

    def wait_for_payload(self, payload_type: str,
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

    def wait_for_mycroft(self, mycroft_msg_type: str, timeout: float=3.0):
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
