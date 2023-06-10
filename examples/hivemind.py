from hivemind_bus_client import HiveMessageBusClient, HiveMessage, \
    HiveMessageType
from hivemind_bus_client.decorators import on_hive_message
from ovos_bus_client import Message
from time import sleep

key = "ivf1NQSkQNogWYyr"
crypto_key = "ivf1NQSkQNogWYyr"

bus = HiveMessageBusClient(key, crypto_key=crypto_key, ssl=False)

bus.run_in_thread()


@on_hive_message(HiveMessageType.BUS, bus=bus)
def printbusmsg(msg):
    print(msg.msg_type, msg.payload)


# special catch all - receives serialized messages (dict)
def printmsg(msg):
    print(msg)  # dict


bus.on("message", printmsg)

sleep(3)

mycroft_msg = Message("recognizer_loop:utterance",
                      {"utterances": ["tell me a joke"]})
bus.emit_mycroft(mycroft_msg)

sleep(50)

bus.close()
sleep(5)
