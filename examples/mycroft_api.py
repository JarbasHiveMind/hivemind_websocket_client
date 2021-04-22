from hivemind_bus_client import HiveMessageBusClient, HiveMessage, \
    HiveMessageType
from mycroft_bus_client import Message

# these should never be equal! one travels down the wire and is an access token
key = "ivf1NQSkQNogWYyr"
# the other is a pre-shared encryption key for a crude initial e2e encryption
# NOTE: needs to be exactly 16chars
crypto_key = "ivf1NQSkQNogWYyr"

bus = HiveMessageBusClient(key, crypto_key=crypto_key, ssl=False)
bus.run_in_thread()

# simulate a user utterance
# - tell the hivemind this is for mycroft - HiveMessageType.BUS
# - payload is a regular mycroft Message
# - you need to provide message.context for proper routing
print("User:", "tell me a joke")
mycroft_msg = Message("recognizer_loop:utterance",
                      {"utterances": ["tell me a joke"]})
msg = HiveMessage(HiveMessageType.BUS, mycroft_msg)


# wait for a specific payload
# - mycroft bus Message
# - Message.msg_type == "speak"
response = bus.wait_for_payload_response(message=msg,
                                         reply_type=HiveMessageType.BUS,
                                         payload_type="speak",
                                         timeout=20)
if response:
    print("Mycroft:", response.payload.data["utterance"])
else:
    print("[NO RESPONSE] timed out....")

bus.close()
