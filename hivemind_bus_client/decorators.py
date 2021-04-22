from hivemind_bus_client.message import HiveMessageType


class HiveMessageListener:
    def __init__(self, bus, message_type):
        self.bus = bus
        self.message_type = message_type
        self._handlers = []

    def _handler(self, message):
        """Receive response data."""
        for handler in self._handlers:
            handler(message)
        self.bus.once(self.message_type, self._handler)

    def listen(self):
        self.bus.once(self.message_type, self._handler)
        return self

    def add_handler(self, handler):
        self._handlers.append(handler)

    def clear_handlers(self):
        self._handlers = []

    def shutdown(self):
        self.bus.remove(self.message_type, self._handler)


class HivePayloadListener(HiveMessageListener):
    def __init__(self, payload_type=HiveMessageType.THIRDPRTY, *args,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.payload_type = payload_type

    def _handler(self, message):
        """Receive response data."""
        if message.payload.msg_type == self.payload_type:
            for handler in self._handlers:
                handler(message.payload)
        self.bus.once(self.message_type, self._handler)


def on_hive_message(message_type, bus):
    # Begin wrapper
    def wrapped_handler(func):
        bus.on(message_type, func)
        return func

    return wrapped_handler


def on_mycroft_message(payload_type, bus):
    # Begin wrapper
    def wrapped_handler(func):
        waiter = HivePayloadListener(bus=bus, payload_type=payload_type,
                                     message_type=HiveMessageType.BUS)
        waiter.add_handler(func)
        waiter.listen()
        func.shutdown = waiter.shutdown
        return func

    return wrapped_handler


def on_shared_bus(payload_type, bus):
    # Begin wrapper
    def wrapped_handler(func):
        waiter = HivePayloadListener(bus=bus, payload_type=payload_type,
                                     message_type=HiveMessageType.SHARED_BUS)
        waiter.add_handler(func)
        waiter.listen()
        func.shutdown = waiter.shutdown
        return func

    return wrapped_handler


def on_broadcast(payload_type, bus):
    # Begin wrapper
    def wrapped_handler(func):
        waiter = HivePayloadListener(bus=bus, payload_type=payload_type,
                                     message_type=HiveMessageType.BROADCAST)
        waiter.add_handler(func)
        waiter.listen()
        func.shutdown = waiter.shutdown
        return func

    return wrapped_handler


def on_ping(payload_type, bus):
    # Begin wrapper
    def wrapped_handler(func):
        waiter = HivePayloadListener(bus=bus, payload_type=payload_type,
                                     message_type=HiveMessageType.PING)
        waiter.add_handler(func)
        waiter.listen()
        func.shutdown = waiter.shutdown
        return func

    return wrapped_handler


def on_propagate(payload_type, bus):
    # Begin wrapper
    def wrapped_handler(func):
        waiter = HivePayloadListener(bus=bus, payload_type=payload_type,
                                     message_type=HiveMessageType.PROPAGATE)
        waiter.add_handler(func)
        waiter.listen()
        func.shutdown = waiter.shutdown
        return func

    return wrapped_handler


def on_escalate(payload_type, bus):
    # Begin wrapper
    def wrapped_handler(func):
        waiter = HivePayloadListener(bus=bus, payload_type=payload_type,
                                     message_type=HiveMessageType.ESCALATE)
        waiter.add_handler(func)
        waiter.listen()
        func.shutdown = waiter.shutdown
        return func

    return wrapped_handler


def on_registry_opcode(payload_type, bus):
    # Begin wrapper
    def wrapped_handler(func):
        waiter = HivePayloadListener(bus=bus, payload_type=payload_type,
                                     message_type=HiveMessageType.REGISTRY)
        waiter.add_handler(func)
        waiter.listen()
        func.shutdown = waiter.shutdown
        return func

    return wrapped_handler


# low level
def on_third_party(bus):
    # Begin wrapper
    def wrapped_handler(func):
        waiter = HiveMessageListener(bus=bus,
                                     message_type=HiveMessageType.THIRDPRTY)
        waiter.add_handler(func)
        waiter.listen()
        func.shutdown = waiter.shutdown
        return func

    return wrapped_handler


def on_payload(message_type, payload_type, bus):
    # Begin wrapper
    def wrapped_handler(func):
        waiter = HivePayloadListener(bus=bus, payload_type=payload_type,
                                     message_type=message_type)
        waiter.add_handler(func)
        waiter.listen()
        func.shutdown = waiter.shutdown
        return func

    return wrapped_handler
