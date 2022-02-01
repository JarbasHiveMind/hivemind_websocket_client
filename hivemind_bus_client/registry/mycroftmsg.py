""" This module provides a translation layer between actions and expected mycroft payloads
This is not hivemind native functionality and only provided as convenience due to that being a common use case"""
from hivemind_bus_client.message import Message, HiveMessageType
from hivemind_bus_client.registry import REGISTRY, encode_action
from hivemind_bus_client.registry.serialization import get_bitstring, decode_bitstring


def mycroft2bitstring(msg, compressed=False):
    if isinstance(msg, str):
        msg = Message.deserialize(msg)
    # look up the registry
    if msg.msg_type == "speak":
        action = encode_action("execute_tts", msg.data,
                               compressed=compressed)
        return get_bitstring(HiveMessageType.ACTION, action,
                             compressed=compressed, hivemeta=msg.context)

    else:  # default encoding
        return get_bitstring(HiveMessageType.BUS,
                             payload=msg, hivemeta=msg.context)


if __name__ == "__main__":
    encoded = mycroft2bitstring(Message("speak", {"utterance": "WHWHOWHWOHWOW"}))

    decoded = decode_bitstring(encoded)
    # {'msg_type': <HiveMessageType.REGISTRY: 'registry'>,
    #  'node': None,
    #  'payload': {'action': 'execute_tts',
    #              'data': {'expect_response': False,
    #                       'lang': 'auto',
    #                       'utterance': 'WHWHOWHWOHWOW'},
    #              'uid': 0},
    #  'route': [],
    #  'source_peer': None}
