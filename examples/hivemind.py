from hivemind_bus_client import HiveMessageBusClient, HiveMessage, \
    HiveMessageType
from mycroft_bus_client import Message
from time import sleep

key = "my_access_token"
crypto_key = "ivf1NQSkQNogWYyr"

bus = HiveMessageBusClient(key, crypto_key=crypto_key, ssl=False)

bus.run_in_thread()


def printmsg(msg):
    print(msg)  # dict


def printhivemsg(msg):
    print(msg.msg_type, msg.payload)


# special catch all - receives serialized messages (dict)
# bus.on("message", printmsg)

bus.on(HiveMessageType.BUS, printhivemsg)

sleep(3)

mycroft_msg = Message("recognizer_loop:utterance",
                      {"utterances": ["tell me a joke"]})
msg = HiveMessage(HiveMessageType.BUS, mycroft_msg)

bus.emit(msg)

sleep(50)

bus.close()
sleep(5)
