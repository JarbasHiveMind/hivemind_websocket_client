import json
import zlib
from binascii import hexlify
from binascii import unhexlify

from ovos_utils.security import encrypt, decrypt, AES

from hivemind_bus_client.exceptions import EncryptionKeyError, DecryptionKeyError
from hivemind_bus_client.message import HiveMessage, HiveMessageType, Message


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


def payload2dict(payload):
    """helper to ensure all subobjects of a payload are a dict safe for serialization
    eg. ensure payload is valid to send over mycroft messagebus object """
    if isinstance(payload, HiveMessage):
        payload = payload.as_dict
    if isinstance(payload, Message):
        payload = payload.serialize()
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except:
            pass
    assert isinstance(payload, dict)

    def can_serialize(val):
        if isinstance(val, HiveMessage) \
                or isinstance(val, Message) \
                or isinstance(val, dict):
            return True
        return False

    for k, v in payload.items():
        if can_serialize(v):
            payload[k] = payload2dict(v)
        if isinstance(v, list):
            for idx, l in enumerate(v):
                if can_serialize(l):
                    payload[k][idx] = payload2dict(l)
    return payload


def get_payload(msg):
    """ helper to read normalized payload
    from all supported formats (HiveMessage, Message, json str)
    """
    if isinstance(msg, HiveMessage):
        msg = msg.payload
    if isinstance(msg, Message):
        msg = msg.serialize()
    if isinstance(msg, str):
        msg = json.loads(msg)
    return msg


def get_hivemsg(msg):
    """ helper to create a normalized HiveMessage object
    from all supported formats (Message, json str, dict)
    """
    if isinstance(msg, str):
        msg = json.loads(msg)
    if isinstance(msg, dict):
        msg = HiveMessage(**msg)
    if isinstance(msg, Message):
        msg = HiveMessage(msg_type=HiveMessageType.BUS, payload=msg)
    assert isinstance(msg, HiveMessage)
    return msg


def get_mycroft_msg(pload):
    if isinstance(pload, HiveMessage):
        assert pload.msg_type == HiveMessageType.BUS
        pload = pload.payload

    if isinstance(pload, str):
        try:
            pload = Message.deserialize(pload)
        except:
            pload = json.loads(pload)
    if isinstance(pload, dict):
        msg_type = pload.get("msg_type") or pload["type"]
        data = pload.get("data") or {}
        context = pload.get("context") or {}
        pload = Message(msg_type, data, context)

    assert isinstance(pload, Message)
    return pload


def encrypt_as_json(key, data):
    if isinstance(data, dict):
        data = json.dumps(data)
    if len(key) > 16:
        key = key[0:16]
    ciphertext = encrypt_bin(key, data)
    nonce, ciphertext, tag = ciphertext[:16], ciphertext[16:-16], ciphertext[-16:]
    return json.dumps({"ciphertext": hexlify(ciphertext).decode('utf-8'),
                       "tag": hexlify(tag).decode('utf-8'),
                       "nonce": hexlify(nonce).decode('utf-8')})


def decrypt_from_json(key, data):
    if isinstance(data, str):
        data = json.loads(data)
    if len(key) > 16:
        key = key[0:16]
    ciphertext = unhexlify(data["ciphertext"])
    if data.get("tag") is None:  # web crypto
        ciphertext, tag = ciphertext[:-16], ciphertext[-16:]
    else:
        tag = unhexlify(data["tag"])
    nonce = unhexlify(data["nonce"])
    try:
        return decrypt(key, ciphertext, tag, nonce)
    except ValueError:
        raise DecryptionKeyError


def encrypt_bin(key, data):
    if len(key) > 16:
        key = key[0:16]
    try:
        ciphertext, tag, nonce = encrypt(key, data)
    except:
        raise EncryptionKeyError

    return nonce + ciphertext + tag


def decrypt_bin(key, ciphertext):
    if len(key) > 16:
        key = key[0:16]

    nonce, ciphertext, tag = ciphertext[:16], ciphertext[16:-16], ciphertext[-16:]

    try:
        if not isinstance(key, bytes):
            key = bytes(key, encoding="utf-8")
        cipher = AES.new(key, AES.MODE_GCM, nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)
    except ValueError:
        raise DecryptionKeyError


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


def cast2bytes(payload, compressed=False):
    if isinstance(payload, dict):
        payload = json.dumps(payload)
    if compressed:
        payload = compress_payload(payload)
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    assert isinstance(payload, bytes)
    return payload


def bytes2str(payload, compressed=False):
    if compressed:
        return decompress_payload(payload).decode("utf-8")
    else:
        return payload.decode("utf-8")
