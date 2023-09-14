import json

import click
from ovos_bus_client import Message
from ovos_utils.log import LOG
from ovos_utils.messagebus import FakeBus

from hivemind_bus_client.client import HiveMessageBusClient
from hivemind_bus_client.message import HiveMessage, HiveMessageType
from hivemind_bus_client.identity import NodeIdentity
LOG.set_level("DEBUG")


@click.group()
def hmclient_cmds():
    pass


@hmclient_cmds.command(help="persist node identity / credentials", name="set-identity")
@click.option("--key", help="HiveMind access key", type=str, default="")
@click.option("--password", help="HiveMind password", type=str, default="")
@click.option("--siteid", help="location identifier for message.context", type=str, default="")
def identity_set(key: str, password: str, siteid: str):
    identity = NodeIdentity()
    identity.password = password or identity.password
    identity.access_key = key or identity.access_key
    identity.site_id = siteid or identity.site_id
    identity.save()
    print(f"identity saved: {identity.IDENTITY_FILE.path}")


@hmclient_cmds.command(help="simple cli interface to inject utterances and print speech", name="terminal")
@click.option("--key", help="HiveMind access key", type=str, default="")
@click.option("--password", help="HiveMind password", type=str, default="")
@click.option("--host", help="HiveMind host", type=str, default="0.0.0.0")
@click.option("--port", help="HiveMind port number", type=int, default=5678)
@click.option("--siteid", help="location identifier for message.context", type=str, default="")
def terminal(key: str, password: str, host: str, port: int, siteid: str):
    if not password or not key or not siteid:
        identity = NodeIdentity()
        password = password or identity.password
        key = key or identity.access_key
        siteid = siteid or identity.site_id or "unknown"

    if not key or not password:
        raise RuntimeError("NodeIdentity not set, please pass key and password or "
                           "call 'hivemind-client set-identity'")

    node = HiveMessageBusClient(key, host=host, port=port, password=password)
    node.connect(FakeBus(), site_id=siteid)

    # node.connected_event.wait()
    print("== connected to HiveMind")

    def handle_speak(message: Message):
        utt = message.data["utterance"]
        print("> ", utt)

    node.on_mycroft("speak", handle_speak)

    while True:
        try:
            utt = input("Utterance:")
            node.emit_mycroft(
                Message("recognizer_loop:utterance",
                        {"utterances": [utt]},
                        {"destination": "skills"})
            )
        except KeyboardInterrupt:
            break
        except Exception:
            LOG.exception("error")
            break

    node.close()


@hmclient_cmds.command(help="send a single mycroft message",
                       name="send-mycroft")
@click.option("--key", help="HiveMind access key", type=str)
@click.option("--host", help="HiveMind host", type=str, default="0.0.0.0")
@click.option("--port", help="HiveMind port number", type=int, default=5678)
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
@click.option("--host", help="HiveMind host", type=str, default="0.0.0.0")
@click.option("--port", help="HiveMind port number", type=int, default=5678)
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
@click.option("--host", help="HiveMind host", type=str, default="0.0.0.0")
@click.option("--port", help="HiveMind port number", type=int, default=5678)
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
