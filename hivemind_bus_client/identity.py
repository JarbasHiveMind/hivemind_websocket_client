from os.path import basename, dirname
from json_database import JsonConfigXDG

IDENTITY_FILE = JsonConfigXDG("_identity", subfolder="hivemind")


class NodeIdentity:
    @property
    def name(self):
        """human readable label, not guaranteed unique
        can describe functionality, brand, capabilities or something else...
        """
        if not IDENTITY_FILE.get("name") and IDENTITY_FILE.get("key"):
            IDENTITY_FILE["name"] = basename(IDENTITY_FILE["key"])
        return IDENTITY_FILE.get("name") or "unnamed-node"

    @name.setter
    def name(self, val):
        IDENTITY_FILE["name"] = val

    @property
    def private_key(self):
        """path to PRIVATE .asc PGP key, this cryptographic key
        uniquely identifies this device across the hive and proves it's identity"""
        return IDENTITY_FILE.get("key") or \
            f"{dirname(IDENTITY_FILE.path)}/{self.name}.asc"

    @private_key.setter
    def private_key(self, val):
        IDENTITY_FILE["key"] = val

    @property
    def password(self):
        """password is used to generate a session aes key on handshake.
        It should be used instead of users manually setting an encryption key.
        This password can be thought as identifying a sub-hive where all devices
        can connect to each other (access keys still need to be valid)"""
        return IDENTITY_FILE.get("password")

    @password.setter
    def password(self, val):
        IDENTITY_FILE["password"] = val

    def save(self):
        IDENTITY_FILE.store()

    def reload(self):
        IDENTITY_FILE.reload()
