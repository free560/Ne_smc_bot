from cryptography.fernet import Fernet
from decouple import config

_fernet = Fernet(config('FIELD_ENCRYPTION_KEY').encode())


def encrypt_value(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    return _fernet.decrypt(encrypted_value.encode()).decode()