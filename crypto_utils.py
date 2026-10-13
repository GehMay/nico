"""Criptografia em repouso para dados pessoais (fatos, conversas, lembretes).

A chave simétrica (Fernet/AES) é gerada uma vez e guardada fora da pasta do
projeto (que fica dentro do OneDrive e sincroniza na nuvem), protegida pela
DPAPI do Windows (win32crypt) - ou seja, só é legível pela mesma conta do
Windows neste mesmo computador, sem precisar de nenhuma senha digitada pelo
usuário. Isso cobre o cenário real deste projeto: se o .env ou o banco de
dados sincronizarem para a nuvem do OneDrive, ou se o HD for lido por fora
do Windows, o conteúdo sensível continua ilegível.

Linhas já gravadas antes desta mudança continuam em texto puro - são
reconhecidas pela ausência do prefixo ENC_PREFIX e devolvidas sem decifrar,
então nada do que já foi lembrado se perde.
"""
import os
from functools import lru_cache

import win32crypt
from cryptography.fernet import Fernet, InvalidToken

ENC_PREFIX = "enc1:"

_KEY_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Nico")
_KEY_PATH = os.path.join(_KEY_DIR, "secret.key")

# CRYPTPROTECT_UI_FORBIDDEN - nunca mostra um prompt do Windows, falha em vez disso.
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


def _generate_and_store_key():
    raw_key = Fernet.generate_key()
    protected = win32crypt.CryptProtectData(
        raw_key, "Nico - chave de criptografia local", None, None, None,
        _CRYPTPROTECT_UI_FORBIDDEN,
    )
    os.makedirs(_KEY_DIR, exist_ok=True)
    with open(_KEY_PATH, "wb") as handle:
        handle.write(protected)
    return raw_key


@lru_cache(maxsize=1)
def _load_key():
    if os.path.isfile(_KEY_PATH):
        with open(_KEY_PATH, "rb") as handle:
            protected = handle.read()
        _description, raw_key = win32crypt.CryptUnprotectData(
            protected, None, None, None, _CRYPTPROTECT_UI_FORBIDDEN,
        )
        return raw_key
    return _generate_and_store_key()


@lru_cache(maxsize=1)
def _fernet():
    return Fernet(_load_key())


def encrypt_text(plain_text):
    if plain_text is None:
        return plain_text
    token = _fernet().encrypt(plain_text.encode("utf-8")).decode("ascii")
    return ENC_PREFIX + token


def decrypt_text(stored_text):
    if stored_text is None or not stored_text.startswith(ENC_PREFIX):
        return stored_text
    token = stored_text[len(ENC_PREFIX):]
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        # Chave diferente (ex.: outra conta do Windows) - não dá pra ler,
        # mas não deve travar o app; melhor mostrar isso do que quebrar.
        return "[não foi possível decifrar - chave local diferente]"
