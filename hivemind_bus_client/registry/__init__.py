from bitstring import BitArray, BitStream
from hivemind_bus_client.util import cast2bytes
from hivemind_bus_client.message import HiveMessageType
MOCK_REGISTRY = {
    "execute_tts": {"uid": 0, "data": [
        ("utterance", {"description": "Playback text to speech in target",
                      "type": "str16"}),
        ("expect_response", {"default": False,
                            "type": "bool",
                            "description": "Boolean indicating if a user response is expected"}),
         ("lang", {  "default": "auto",  # its up to the handler to detect from text
            "type": "str",
            "description": "Lowercased BCP 47 Language tag associated with `utterance` (i.e. en-us)"
        }),
    ]}
}

# TODO The registry should be distributed outside of this repo
# It should exist in several formats, eg, json / xml / sqllite
# Each implementation loads the registry in the most convenient format

REGISTRY = MOCK_REGISTRY
UID2ACTION = {v["uid"]: k for k, v in REGISTRY.items()}


def encode_action(action, payload, compressed=False):
    s = BitArray()

    s.append(f'uint:6={REGISTRY[action]["uid"]}')  # 6 bit unsigned integer - action id

    for key, meta in REGISTRY[action]["data"]:
        v = payload.get(key) or meta.get("default")
        if v is None:
            # TODO handle required values
            continue
        if meta["type"] == "bool":
            s.append(f'uint:1={int(v)}')  # 1 bit unsigned integer
        elif meta["type"].startswith("str"):
            v = cast2bytes(v, compressed)
            if meta["type"] == "str32":
                s.append(f'uint:32={len(v)}')  # 32 bit unsigned integer - N of bytes for str
            elif meta["type"] == "str16":
                s.append(f'uint:16={len(v)}')  # 16 bit unsigned integer - N of bytes for str
            else:
                s.append(f'uint:8={len(v)}')  # 8 bit unsigned integer - N of bytes for str
            s.append(v)  # the string
    return s


def decode_action(bitstr):
    s = BitStream(bitstr)
    uid = s.read(6).int
    action = UID2ACTION[uid]

    decoded = {"action": action, "uid": uid, "data": {}}

    for key, meta in REGISTRY[action]["data"]:
        v = meta.get("default")
        if meta["type"] == "bool":
            v = bool(s.read(1))
        elif meta["type"].startswith("str"):
            if meta["type"] == "str32":
                str_len = s.read(32).int
                # 32 bit unsigned integer - N of bytes for str
            elif meta["type"] == "str16":
                # 16 bit unsigned integer - N of bytes for str
                str_len = s.read(16).int
            else:
                # 8 bit unsigned integer - N of bytes for str
                str_len = s.read(8).int
            v = s.read(str_len * 8 ).bytes.decode("utf-8")  # the string
        decoded["data"][key] = v
    return decoded


if __name__ == "__main__":
    from pprint import pprint
    compressed = False
    encoded = encode_action("execute_tts",
                            {"utterance": "hello world", "lang": "en-us"},
                            compressed=compressed)

    decoded = decode_action(encoded)
    pprint(decoded)
    # {'action': 'execute_tts',
    #  'data': {'expect_response': False,
    #           'lang': 'en-us',
    #           'utterance': 'hello world'},
    #  'uid': 0}

    from hivemind_bus_client.registry.serialization import get_bitstring, decode_bitstring
    bitstr = get_bitstring(hive_type=HiveMessageType.REGISTRY,
                           payload=encoded)

    decoded = decode_bitstring(bitstr)

    pprint(decoded.as_dict)
    # {'msg_type': <HiveMessageType.REGISTRY: 'registry'>,
    #  'node': None,
    #  'payload': {'action': 'execute_tts',
    #              'data': {'expect_response': False,
    #                       'lang': 'en-us',
    #                       'utterance': 'hello world'},
    #              'uid': 0},
    #  'route': [],
    #  'source_peer': None}