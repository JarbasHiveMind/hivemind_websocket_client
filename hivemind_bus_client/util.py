import json
from binascii import hexlify, unhexlify
import zlib
from binascii import unhexlify
from ovos_utils.security import encrypt, decrypt


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


def encrypt_as_json(key, data, nonce=None):
    if isinstance(data, dict):
        data = json.dumps(data)
    if len(key) > 16:
        key = key[0:16]
    try:
        ciphertext, tag, nonce = encrypt(key, data, nonce=nonce)
    except:
        raise RuntimeError("EncryptionKeyError")
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
        raise RuntimeError("DecryptionKeyError")



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
