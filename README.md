# Hivemind Websocket Client

## Install

```bash
pip install hivemind_bus_client==0.0.1a1
```

## Usage

### Mycroft API

```python
from hivemind_bus_client import HiveMessageBusClient, HiveMessage, HiveMessageType
from mycroft_bus_client import Message

# these should never be equal! one travels down the wire and is an access token
key = "my_access_key"
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
```

output

```
User: tell me a joke
Mycroft: There are II types of people: Those who understand Roman Numerals and those who don't.
```

### HiveMind API

```python
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

# lets send something so we receive something back
mycroft_msg = Message("recognizer_loop:utterance",
                      {"utterances": ["tell me a joke"]})
msg = HiveMessage(HiveMessageType.BUS, mycroft_msg)

bus.emit(msg)

sleep(50)

bus.close()
sleep(5)
```

output
```
2021-04-22 19:02:29.328 - OVOS - hivemind_bus_client.client:on_open:101 - INFO - Connected
{'msg_type': 'bus', 'payload': {'type': 'skill.converse.request', 'data': {'skill_id': 'mycroft-joke.mycroftai', 'utterances': ['tell me a joke'], 'lang': 'en-us'}, 'context': {'source': 'HiveMind', 'destination': 'tcp4:127.0.0.1:52772', 'platform': 'HiveMessageBusClientV0.0.1', 'peer': 'tcp4:127.0.0.1:52772', 'client_name': 'HiveMindV0.7'}}, 'route': [], 'node': None, 'source_peer': 'tcp4:0.0.0.0:5678'}
{'msg_type': 'bus', 'payload': {'type': 'mycroft-joke.mycroftai:JokingIntent', 'data': {'intent_type': 'mycroft-joke.mycroftai:JokingIntent', 'mycroft_joke_mycroftaiJoke': 'joke', 'target': None, 'confidence': 0.3333333333333333, '__tags__': [{'match': 'joke', 'key': 'joke', 'start_token': 3, 'entities': [{'key': 'joke', 'match': 'joke', 'data': [['joke', 'mycroft_joke_mycroftaiJoke']], 'confidence': 1.0}], 'end_token': 3, 'from_context': False}], 'utterance': 'tell me a joke'}, 'context': {'source': 'HiveMind', 'destination': 'tcp4:127.0.0.1:52772', 'platform': 'HiveMessageBusClientV0.0.1', 'peer': 'tcp4:127.0.0.1:52772', 'client_name': 'HiveMindV0.7'}}, 'route': [], 'node': None, 'source_peer': 'tcp4:0.0.0.0:5678'}
{'msg_type': 'bus', 'payload': {'type': 'mycroft.skill.handler.start', 'data': {'name': 'JokingSkill.handle_general_joke'}, 'context': {'source': 'HiveMind', 'destination': 'tcp4:127.0.0.1:52772', 'platform': 'HiveMessageBusClientV0.0.1', 'peer': 'tcp4:127.0.0.1:52772', 'client_name': 'HiveMindV0.7'}}, 'route': [], 'node': None, 'source_peer': 'tcp4:0.0.0.0:5678'}
{'msg_type': 'bus', 'payload': {'type': 'speak', 'data': {'utterance': "When Chuck Norris breaks the build, you can't fix it, because there is not a single line of code left.", 'expect_response': False, 'meta': {'skill': 'JokingSkill'}}, 'context': {'source': 'HiveMind', 'destination': 'tcp4:127.0.0.1:52772', 'platform': 'HiveMessageBusClientV0.0.1', 'peer': 'tcp4:127.0.0.1:52772', 'client_name': 'HiveMindV0.7'}}, 'route': [], 'node': None, 'source_peer': 'tcp4:0.0.0.0:5678'}
{'msg_type': 'bus', 'payload': {'type': 'mycroft.skill.handler.complete', 'data': {'name': 'JokingSkill.handle_general_joke'}, 'context': {'source': 'HiveMind', 'destination': 'tcp4:127.0.0.1:52772', 'platform': 'HiveMessageBusClientV0.0.1', 'peer': 'tcp4:127.0.0.1:52772', 'client_name': 'HiveMindV0.7'}}, 'route': [], 'node': None, 'source_peer': 'tcp4:0.0.0.0:5678'}
```
