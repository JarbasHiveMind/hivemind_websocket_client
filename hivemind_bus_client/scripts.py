import json

import click
from ovos_bus_client import Message
from ovos_config import Configuration
from ovos_utils.messagebus import FakeBus

from hivemind_bus_client.client import HiveNodeClient, HiveMessageBusClient
from hivemind_bus_client.message import HiveMessage, HiveMessageType


@click.group()
def hmclient_cmds():
    pass


@hmclient_cmds.command(help="simple cli interface to inject utterances and print speech", name="terminal")
@click.option("--key", help="HiveMind access key", type=str)
@click.option("--host", help="HiveMind host", type=str,
              default=Configuration().get('websocket', {}).get("host", "0.0.0.0"))
@click.option("--port", help="HiveMind port number", type=int,
              default=Configuration().get('websocket', {}).get("port", 5678))
def terminal(key: str, host: str, port: int):
    node = HiveNodeClient(key, bus=FakeBus(), host=host, port=port)

    node.run_in_thread()
    node.connected_event.wait()
    print("== connected to HiveMind")

    def handle_speak(message: Message):
        utt = message.data["utterance"]
        print("> ", utt)

    node.on_mycroft("speak", handle_speak)

    while True:
        try:
            utt = input("Utterance:")
            node.emit_mycroft(
                Message("recognizer_loop:utterance", {"utterance": utt})
            )
        except KeyboardInterrupt:
            break

    node.close()


@hmclient_cmds.command(help="send a single mycroft message",
                       name="send-mycroft")
@click.option("--key", help="HiveMind access key", type=str)
@click.option("--host", help="HiveMind host", type=str,
              default=Configuration().get('websocket', {}).get("host", "0.0.0.0"))
@click.option("--port", help="HiveMind port number", type=int,
              default=Configuration().get('websocket', {}).get("port", 5678))
@click.option("--msg", help="ovos message type to inject", type=str)
@click.option("--payload", help="ovos message json payload", type=str)
def send_mycroft(key: str, host: str, port: int, msg: str, payload: str):
    node = HiveMessageBusClient(key, host=host, port=port)

    node.run_in_thread()
    node.connected_event.wait()
    print("== connected to HiveMind")

    node.emit_mycroft(Message(msg, json.loads(payload)))

    node.close()


@hmclient_cmds.command(help="escalate a single mycroft message",
                       name="escalate")
@click.option("--key", help="HiveMind access key", type=str)
@click.option("--host", help="HiveMind host", type=str,
              default=Configuration().get('websocket', {}).get("host", "0.0.0.0"))
@click.option("--port", help="HiveMind port number", type=int,
              default=Configuration().get('websocket', {}).get("port", 5678))
@click.option("--msg", help="ovos message type to inject", type=str)
@click.option("--payload", help="ovos message json payload", type=str)
def escalate(key: str, host: str, port: int, msg: str, payload: str):
    node = HiveMessageBusClient(key, host=host, port=port)

    node.run_in_thread()
    node.connected_event.wait()
    print("== connected to HiveMind")

    hm = HiveMessage(HiveMessageType.ESCALATE,
                     Message(msg, json.loads(payload)))
    node.emit(hm)

    node.close()


@hmclient_cmds.command(help="propagate a single mycroft message",
                       name="propagate")
@click.option("--key", help="HiveMind access key", type=str)
@click.option("--host", help="HiveMind host", type=str,
              default=Configuration().get('websocket', {}).get("host", "0.0.0.0"))
@click.option("--port", help="HiveMind port number", type=int,
              default=Configuration().get('websocket', {}).get("port", 5678))
@click.option("--msg", help="ovos message type to inject", type=str)
@click.option("--payload", help="ovos message json payload", type=str)
def propagate(key: str, host: str, port: int, msg: str, payload: str):
    node = HiveMessageBusClient(key, host=host, port=port)

    node.run_in_thread()
    node.connected_event.wait()
    print("== connected to HiveMind")

    hm = HiveMessage(HiveMessageType.PROPAGATE,
                     Message(msg, json.loads(payload)))
    node.emit(hm)

    node.close()


if __name__ == "__main__":
    hmclient_cmds()
