from hivemind_bus_client import HiveMessageBusClient, HiveMessage, \
    HiveMessageType
from mycroft_bus_client import Message
from ovos_utils import create_daemon
from time import sleep

key = "ivf1NQSkQNogWYyr"
crypto_key = "ivf1NQSkQNogWYyr"

bus = HiveMessageBusClient(key, crypto_key=crypto_key, ssl=False)

create_daemon(bus.run_forever)


def printmsg(msg):
    print(msg)


bus.on("message", printmsg)

sleep(3)

mycroft_msg = Message("recognizer_loop:utterance",
                      {"utterances": ["tell me a joke"]},
                      {"source": bus.useragent,
                       "destination": "HiveMind",
                       "platform": bus.useragent
                       })

bus.emit(HiveMessage(HiveMessageType.BUS, mycroft_msg))

sleep(50)

bus.close()
sleep(5)
