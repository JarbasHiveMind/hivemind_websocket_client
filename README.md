# Hivemind Websocket Client

## Install

```bash
pip install hivemind_bus_client
```

## Usage

```python
from time import sleep
from mycroft_bus_client import Message
from hivemind_bus_client import HiveMessageBusClient
from hivemind_bus_client.decorators import on_escalate, \
    on_shared_bus, on_ping, on_broadcast, on_propagate, on_mycroft_message, \
    on_registry_opcode, on_third_party, on_cascade, on_handshake, on_hello, \
    on_rendezvous, on_hive_message, on_third_party, on_payload

key = "super_secret_access_key"
crypto_key = "ivf1NQSkQNogWYyr"

bus = HiveMessageBusClient(key, crypto_key=crypto_key, ssl=False)

bus.run_in_thread()


@on_mycroft_message(payload_type="speak", bus=bus)
def on_speak(msg):
    print(msg.data["utterance"])


mycroft_msg = Message("recognizer_loop:utterance",
                      {"utterances": ["tell me a joke"]})
bus.emit_mycroft(mycroft_msg)


sleep(50)

bus.close()
```
