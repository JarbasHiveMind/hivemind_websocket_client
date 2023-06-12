from dataclasses import dataclass
from typing import Optional

from ovos_bus_client import Message as MycroftMessage
from ovos_bus_client import MessageBusClient
from ovos_bus_client.message import Message
from ovos_utils.log import LOG

from hivemind_bus_client.client import HiveMessageBusClient
from hivemind_bus_client.message import HiveMessage, HiveMessageType


@dataclass()
class HiveMindSlaveInternalProtocol:
    """ this class handles all interactions between a hivemind listener and a ovos-core messagebus"""
    hm_bus: HiveMessageBusClient
    share_bus: bool = False
    bus: Optional[MessageBusClient] = None
    node_id: str = ""  # this is how ovos-core bus refers to this slave's master

    def register_bus_handlers(self):
        self.bus.on("hive.send.upstream", self.handle_send)
        self.bus.on("message", self.handle_outgoing_mycroft)  # catch all

    # mycroft handlers  - from slave -> master
    def handle_send(self, message: Message):
        """ ovos wants to send a HiveMessage

        a device can be both a master and a slave, upstream messages are handled here

        HiveMindListenerInternalProtocol will handle requests meant to go downstream
        """

        payload = message.data.get("payload")
        msg_type = message.data["msg_type"]

        hmessage = HiveMessage(msg_type,
                               payload=payload)

        if msg_type == HiveMessageType.BROADCAST:
            # only masters can broadcast, ignore silently
            #   if this device is also a master to something,
            #   HiveMindListenerInternalProtocol will handle the request
            pass
        else:
            self.hm_bus.emit(hmessage)

    def handle_outgoing_mycroft(self, message: Message):
        """ forward internal messages to masters"""
        if isinstance(message, str):
            # "message" is a special case in ovos-bus-client that is not deserialized
            message = Message.deserialize(message)

        # this allows the master node to do passive monitoring of bus events
        if self.share_bus:
            msg = HiveMessage(HiveMessageType.SHARED_BUS,
                              payload=message.serialize())
            self.hm_bus.emit(msg)

        # this message is targeted at master
        # eg, a response to some bus event injected by master
        # note: master might completely ignore it
        peers = message.context.get("destination")
        if peers:
            if not isinstance(peers, list):
                peers = [peers]
            if self.node_id in peers:
                msg = HiveMessage(HiveMessageType.BUS,
                                  payload=message.serialize())
                self.hm_bus.emit(msg)


@dataclass()
class HiveMindSlaveProtocol:
    """
    Joins this instance ovos-core bus with master ovos-core bus
    Master becomes able to inject arbitrary bus messages
    """
    hm: HiveMessageBusClient
    internal_protocol: HiveMindSlaveInternalProtocol = None
    mpubkey: str = ""  # asc public PGP key from master
    shared_bus: bool = False

    def bind(self, bus: Optional[MessageBusClient] = None):
        if bus is None:
            bus = MessageBusClient()
            bus.run_in_thread()
            bus.connected_event.wait()
        self.internal_protocol = HiveMindSlaveInternalProtocol(bus=bus, hm_bus=self.hm)
        self.internal_protocol.register_bus_handlers()
        self.hm.on(HiveMessageType.HELLO, self.handle_hello)
        self.hm.on(HiveMessageType.BROADCAST, self.handle_broadcast)
        self.hm.on(HiveMessageType.PROPAGATE, self.handle_propagate)
        self.hm.on(HiveMessageType.ESCALATE, self.handle_illegal_msg)
        self.hm.on(HiveMessageType.BUS, self.handle_bus)

    @property
    def node_id(self):
        # this is how ovos-core bus refers to this slave's master
        return self.internal_protocol.node_id

    # TODO - handshake handlers
    # hivemind events
    def handle_illegal_msg(self, message: HiveMessage):
        # this should not happen,
        # ESCALATE is only sent from client -> server NOT server -> client
        # TODO log, kill connection (?)
        pass

    def handle_hello(self, message: HiveMessage):
        # this check is because other nodes in the hive
        # may also send HELLO with their pubkey
        # only want this on the first connection
        if not self.node_id:
            self.mpubkey = message.payload.get("pubkey")
            node_id = message.payload.get("node_id", "")
            self.internal_protocol.node_id = node_id
            LOG.info(f"Connected to HiveMind: {node_id}")

    def handle_bus(self, message: HiveMessage):
        assert isinstance(message.payload, MycroftMessage)
        # master wants to inject message into mycroft bus
        pload = message.payload
        pload.context["source"] = self.node_id
        self.internal_protocol.bus.emit(pload)

    def handle_broadcast(self, message: HiveMessage):
        # if this device is also a hivemind server
        # forward to HiveMindListenerInternalProtocol
        data = message.serialize()
        ctxt = {"source": self.node_id}
        self.internal_protocol.bus.emit(MycroftMessage('hive.send.downstream', data, ctxt))

    def handle_propagate(self, message: HiveMessage):
        # if this device is also a hivemind server
        # forward to HiveMindListenerInternalProtocol
        data = message.serialize()
        ctxt = {"source": self.node_id}
        self.internal_protocol.bus.emit(MycroftMessage('hive.send.downstream', data, ctxt))
