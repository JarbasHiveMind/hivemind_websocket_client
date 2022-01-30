import json
import sys
import zlib
from binascii import unhexlify
from inspect import signature
from bitstring import BitArray, BitStream
from enum import IntEnum

from hivemind_bus_client.message import HiveMessageType, HiveMessage


class HiveMindBinaryPayloadType(IntEnum):
    UNKNOWN = 0  # no info provided about binary contents
    RAW_AUDIO = 1  # binary content is raw audio  (TODO spec exactly what "raw audio" means)
    NUMPY_ARRAY = 2  # binary content is a numpy array, eg, webcam image
    FILE = 3  # binary is a file to be saved, additional metadata provided elsewhere



_INT2TYPE = {0: HiveMessageType.HANDSHAKE,
             1: HiveMessageType.BUS,
             2: HiveMessageType.SHARED_BUS,
             3: HiveMessageType.BROADCAST,
             4: HiveMessageType.PROPAGATE,
             5: HiveMessageType.ESCALATE,
             6: HiveMessageType.HELLO,
             7: HiveMessageType.QUERY,
             8: HiveMessageType.CASCADE,
             9: HiveMessageType.PING,
             10: HiveMessageType.RENDEZVOUS,
             11: HiveMessageType.THIRDPRTY,
             12: HiveMessageType.BINARY,
             13: HiveMessageType.REGISTRY}


def serialize_message(message):
    # convert a Message object into raw data that can be sent over
    # websocket
    if hasattr(message, 'serialize'):
        return message.serialize()
    elif isinstance(message, dict):
        message = {
            k: v if not hasattr(v, 'serialize') else serialize_message(v)
            for k, v in message.items()}
        return json.dumps(message)
    else:
        return json.dumps(message.__dict__)


def compress_payload(text):
    # Compressing text
    if isinstance(text, str):
        decompressed = text.encode("utf-8")
    else:
        decompressed = text
    return zlib.compress(decompressed)


def decompress_payload(compressed):
    # Decompressing text
    if isinstance(compressed, str):
        # assume hex
        compressed = unhexlify(compressed)
    return zlib.decompress(compressed)


def _tobytes(payload, compressed=False):
    if isinstance(payload, dict):
        payload = json.dumps(payload)
    if compressed:
        payload = compress_payload(payload)
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    assert isinstance(payload, bytes)
    return payload


def _frombytes(payload, compressed=False):
    if compressed:
        return decompress_payload(payload).decode("utf-8")
    else:
        return payload.decode("utf-8")


def get_bitstring(hive_type=HiveMessageType.BUS, payload=None,
                  compressed=False, hivemeta=None,
                  binary_type=HiveMindBinaryPayloadType.UNKNOWN):
    # there are 13 hivemind message main types
    typemap = {v: k for k, v in _INT2TYPE.items()}
    binmap = {e: e.value for e in HiveMindBinaryPayloadType}

    s = BitArray()
    s.append(f'uint:5={typemap.get(hive_type, 11)}')  # 5 bit unsigned integer - the hive msg type
    s.append(f'uint:1={int(bool(compressed))}')  # 1 bit unsigned integer - payload is zlib compressed

    # NOTE: hivemind meta is reserved TBD arbitrary data
    hivemeta = _tobytes(hivemeta or {}, compressed)
    s.append(f'uint:8={len(hivemeta)}')  # 8 bit unsigned integer - N of bytes for metadata
    s.append(hivemeta)  # arbitrary hivemind meta

    # the remaining bits are the payload
    if hasattr(payload, "serialize"):
        payload = payload.serialize()
    payload = _tobytes(payload, compressed)

    # when payload is binary data meant to be passed along raw and not parsed
    if hive_type == HiveMessageType.BINARY:
        # 4 bit unsigned integer - integer indicating pseudo format of bin content
        s.append(f'uint:4={binmap.get(binary_type, 0)}')
    s.append(payload)

    return s


def decode_bitstring(bitstr):
    binmap = {e: e.value for e in HiveMindBinaryPayloadType}

    s = BitStream(bitstr)

    hive_type = _INT2TYPE.get(s.read(5).int, 11)
    compressed = bool(s.read(1))

    metalen = s.read(8).int
    meta = s.read(metalen * 8).bytes
    meta = _frombytes(meta, compressed)

    is_bin = hive_type == HiveMessageType.BINARY
    bin_type = HiveMindBinaryPayloadType.UNKNOWN
    if is_bin:
        bin_type = binmap.get(s.read(4).int, 0)

    payload_len = len(s) - 14 - metalen * 8
    payload = s.read(payload_len).bytes

    if not is_bin:
        payload = _frombytes(payload, compressed)
    else:
        meta["bin_type"] = bin_type
        # error correction
        # a manually crafted message could have a hive type mismatch
        if hive_type != HiveMessageType.BINARY:
            meta["msg_type"] = hive_type
            hive_type = HiveMessageType.BINARY

    # TODO standardize hivemind meta
    kwargs = {a: meta[a] for a in signature(HiveMessage).parameters if a in meta}
    return HiveMessage(hive_type, payload, meta=meta, **kwargs)



if __name__ == "__main__":
    d = {e: e.value for e in HiveMindBinaryPayloadType}
    from hivemind_bus_client.message import Message

    text = """The Mycroft project is also working on and selling smart speakers that run its software. All of its hardware is open-source, released under the CERN Open Hardware Licence.
Its first hardware project was the Mark I, targeted primarily at developers. Its production was partially funded through a Kickstarter campaign, which finished successfully. Units started shipping out in April 2016.
Its most recent hardware project is the Mark II, intended for general usage, not just for developers. Unlike the Mark I, the Mark II is equipped with a screen, being able to relay information both visually as well as acoustically. As with the Mark I, the Mark II's production was partially funded through a Kickstarter campaign, which wrapped up in February 2018, hitting almost 8 times its original goal. As of February 2021, the Mark II had not yet begun shipping to crowd-funders, though shipping of the Development Kit was imminent.
Mycroft announced that a third hardware project, Mark III, will be offered through Kickstarter, and that an entire product line of Mark I, II, and III will be released to stores by November, 2019"""

    payload = Message("speak", {"utterance": text})

    print(len(payload.serialize().encode("utf-8")))
    bitstr = get_bitstring(hive_type=HiveMessageType.BUS,
                           payload=payload,
                           compressed=True)
    print(bitstr)

    print(len(bitstr) / 8)  # 5045
    exit()
    bitstr = get_bitstring(hive_type=HiveMessageType.BUS,
                           payload=payload,
                           compressed=True)
    print(len(bitstr))  # 2917
    decode_bitstring(bitstr)

    decoded = decode_bitstring(bitstr)
    print(decoded)

    payload = HiveMessage(HiveMessageType.BUS,
                          payload=Message("speak", {"utterance": "RED ALERT"}))
    bitstr = get_bitstring(hive_type=HiveMessageType.BROADCAST,
                           payload=payload,
                           compressed=False)
    print(len(bitstr))  # 1205
    decoded = decode_bitstring(bitstr)
    print(decoded)


    compressed = compress_payload(text).hex()
    # 789c5590c16e84300c44ef7cc51c5ba942bdee1fb4528ffb03261848156c9418e8fe7d9daebab0b72863cfbcf1758a05c32ac1a20afc6d1363c971a67c4314e33c506098bae0eaacfd9a18945446ecd126343d079d97cca5bcbc3e9c5a5c9f8c33db9aa5a0bb1943bb6f0ee66ffc6f4677abc13d19a119e3c65223a3810a16ca34b39354533e3c27d748d4f7f231834029718fc41b27ec530c8e18542c6bba97e31f6331e870a457de4fcf92bfc6a3bb746c3b3bc47bc5b8b4f8d29d8b61a3b4b27f36c5487aefa719a2672337e971c149efeae253d4471c2b7385b9633a4b739a78c39899ec3122a3dff9c4ebf54e776c7f0106a5a377

    def measure_compression(text):
        text_size = sys.getsizeof(text)
        print("\nsize of original text", text_size)

        compressed = compress_payload(text)
        csize = sys.getsizeof(compressed)
        print("\nsize of compressed text", csize)

        decompressed = decompress_payload(compressed)
        dsize = sys.getsizeof(decompressed)
        print("\nsize of decompressed text", dsize)

        sdiff = text_size - csize
        print("\nDifference of size= ", sdiff)

        print("\nSize reduced by", sdiff * 100 / text_size, "%")

        return sdiff * 100 / text_size


    measure_compression(text)
    # size of original text 484
    # size of compressed text 280
    # size of decompressed text 484
    # Difference of size=  204
    # Size reduced by 42.14876033057851 %
