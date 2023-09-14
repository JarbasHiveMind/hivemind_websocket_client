# Hivemind Websocket Client

![logo](./logo.png)

## Install

```bash
pip install hivemind_bus_client
```

## Usage

```python
from time import sleep
from ovos_bus_client import Message
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

## Cli Usage

```bash
$ hivemind-client --help
Usage: hivemind-client [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  escalate      escalate a single mycroft message
  propagate     propagate a single mycroft message
  send-mycroft  send a single mycroft message
  terminal      simple cli interface to inject utterances and print speech


$ hivemind-client set-identity --help
Usage: hivemind-client set-identity [OPTIONS]

  persist node identity / credentials

Options:
  --key TEXT       HiveMind access key
  --password TEXT  HiveMind password
  --siteid TEXT    location identifier for message.context
  --help           Show this message and exit.


$ hivemind-client terminal --help
Usage: hivemind-client terminal [OPTIONS]

  simple cli interface to inject utterances and print speech

Options:
  --key TEXT      HiveMind access key
  --host TEXT     HiveMind host
  --port INTEGER  HiveMind port number
  --help          Show this message and exit.


$ hivemind-client send-mycroft --help
Usage: hivemind-client send-mycroft [OPTIONS]

  send a single mycroft message

Options:
  --key TEXT      HiveMind access key
  --host TEXT     HiveMind host
  --port INTEGER  HiveMind port number
  --msg TEXT      ovos message type to inject
  --payload TEXT  ovos message json payload
  --help          Show this message and exit.


$ hivemind-client escalate --help
Usage: hivemind-client escalate [OPTIONS]

  escalate a single mycroft message

Options:
  --key TEXT      HiveMind access key
  --host TEXT     HiveMind host
  --port INTEGER  HiveMind port number
  --msg TEXT      ovos message type to inject
  --payload TEXT  ovos message json payload
  --help          Show this message and exit.


$ hivemind-client propagate --help
Usage: hivemind-client propagate [OPTIONS]

  propagate a single mycroft message

Options:
  --key TEXT      HiveMind access key
  --host TEXT     HiveMind host
  --port INTEGER  HiveMind port number
  --msg TEXT      ovos message type to inject
  --payload TEXT  ovos message json payload
  --help          Show this message and exit.

```