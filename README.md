# Hivemind Websocket Client

## Install

```bash
pip install hivemind_bus_client==0.0.1a1
```

## Usage

```python
from hivemind_bus_client import HiveMessageBusClient, HiveMessage, HiveMessageType
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
