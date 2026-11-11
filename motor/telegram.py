"""
Cliente mínimo do Telegram, só com o que a rotina usa.

Variáveis de ambiente:
    TELEGRAM_TOKEN    token do bot (BotFather)
    TELEGRAM_CHAT_ID  código do grupo (número negativo que começa com -100)
    TELEGRAM_FALSO    se definido, nada sai para a rede: tudo é gravado nessa pasta (testes)
"""
from __future__ import annotations

import json
import mimetypes
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

LIMITE_ARQUIVO = 49 * 1024 * 1024   # bots enviam no máximo 50 MB
LIMITE_TEXTO = 4000                 # mensagens têm no máximo 4096 caracteres


def _falso() -> Path | None:
    pasta = os.environ.get("TELEGRAM_FALSO")
    if not pasta:
        return None
    p = Path(pasta)
    p.mkdir(parents=True, exist_ok=True)
    return p


def configurado() -> bool:
    return bool(_falso() or (os.environ.get("TELEGRAM_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")))


def chat_id() -> str:
    return os.environ.get("TELEGRAM_CHAT_ID", "")


def _url(metodo: str) -> str:
    token = os.environ.get("TELEGRAM_TOKEN") or sys.exit("Defina TELEGRAM_TOKEN.")
    return f"https://api.telegram.org/bot{token}/{metodo}"


def _enviar(req) -> dict:
    espera = 3
    for tentativa in range(4):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            corpo = e.read().decode(errors="replace")
            if e.code == 429 and tentativa < 3:
                try:
                    espera = json.loads(corpo)["parameters"]["retry_after"] + 1
                except (KeyError, ValueError):
                    pass
                time.sleep(espera)
                continue
            if e.code >= 500 and tentativa < 3:
                time.sleep(espera)
                espera *= 2
                continue
            # Nunca imprime a URL: ela contém o token.
            raise RuntimeError(f"Telegram respondeu {e.code}: {corpo[:300]}") from None
        except urllib.error.URLError as e:
            if tentativa < 3:
                time.sleep(espera)
                espera *= 2
                continue
            raise RuntimeError(f"Falha de rede ao falar com o Telegram: {e.reason}") from None
    raise RuntimeError("O Telegram não respondeu.")


def _json(metodo: str, dados: dict) -> dict:
    req = urllib.request.Request(_url(metodo), data=json.dumps(dados).encode(),
                                 headers={"content-type": "application/json"})
    return _enviar(req)


def _multipart(metodo: str, campos: dict, nome_arquivo: str, caminho: Path) -> dict:
    fronteira = uuid.uuid4().hex
    partes = []
    for k, v in campos.items():
        partes.append(f'--{fronteira}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    tipo = mimetypes.guess_type(caminho.name)[0] or "application/octet-stream"
    partes.append((f'--{fronteira}\r\nContent-Disposition: form-data; name="{nome_arquivo}"; '
                   f'filename="{caminho.name}"\r\nContent-Type: {tipo}\r\n\r\n').encode())
    partes.append(caminho.read_bytes())
    partes.append(f"\r\n--{fronteira}--\r\n".encode())
    req = urllib.request.Request(_url(metodo), data=b"".join(partes),
                                 headers={"content-type": f"multipart/form-data; boundary={fronteira}"})
    return _enviar(req)


# ------------------------------------------------------------------- envio
def mensagem(texto: str, html: bool = True):
    """Manda texto, quebrando em várias mensagens se passar do limite."""
    blocos, atual = [], ""
    for linha in texto.split("\n"):
        if len(atual) + len(linha) + 1 > LIMITE_TEXTO:
            blocos.append(atual)
            atual = ""
        atual += linha + "\n"
    if atual.strip():
        blocos.append(atual)

    falso = _falso()
    for bloco in blocos:
        if falso:
            with open(falso / "mensagens.txt", "a", encoding="utf-8") as f:
                f.write(bloco + "\n-----\n")
            continue
        dados = {"chat_id": chat_id(), "text": bloco, "disable_web_page_preview": True}
        if html:
            dados["parse_mode"] = "HTML"
        _json("sendMessage", dados)


def video(caminho: Path, legenda: str = "", largura: int = 0, altura: int = 0, duracao: int = 0):
    if caminho.stat().st_size > LIMITE_ARQUIVO:
        mensagem(f"O vídeo {caminho.name} passou de 50 MB e não pode ser enviado pelo bot. "
                 "Ele está nos artefatos da execução no GitHub.", html=False)
        return
    falso = _falso()
    if falso:
        shutil.copy(caminho, falso / caminho.name)
        mensagem(f"[vídeo {caminho.name}] {legenda}", html=False)
        return
    campos = {"chat_id": chat_id(), "caption": legenda[:1000], "parse_mode": "HTML",
              "supports_streaming": "true"}
    if largura and altura:
        campos.update(width=largura, height=altura)
    if duracao:
        campos["duration"] = duracao
    _multipart("sendVideo", campos, "video", caminho)


def foto(caminho: Path, legenda: str = ""):
    falso = _falso()
    if falso:
        shutil.copy(caminho, falso / caminho.name)
        mensagem(f"[foto {caminho.name}] {legenda}", html=False)
        return
    # sendDocument manda o arquivo original, sem a compressão do sendPhoto:
    # é o que serve para subir como capa no YouTube.
    _multipart("sendDocument", {"chat_id": chat_id(), "caption": legenda[:1000], "parse_mode": "HTML"},
               "document", caminho)


# ---------------------------------------------------------------- comandos
def comandos(offset: int) -> tuple[list[tuple[str, str]], int]:
    """
    Lê o que chegou desde a última execução. Devolve ([(comando, argumento)], novo_offset).
    Só aceita mensagens do grupo configurado: qualquer outra conversa é ignorada.
    """
    falso = _falso()
    if falso:
        arq = falso / "comandos.json"
        lidos = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
        if arq.exists():
            arq.unlink()
        return [(c, a) for c, a in lidos], offset

    resp = _json("getUpdates", {"offset": offset, "timeout": 0,
                                "allowed_updates": ["message"]})
    saida, maior = [], offset - 1
    for u in resp.get("result", []):
        maior = max(maior, u["update_id"])
        msg = u.get("message") or {}
        if str(msg.get("chat", {}).get("id")) != chat_id():
            continue
        texto = (msg.get("text") or "").strip()
        if not texto.startswith("/"):
            continue
        cabeca, _, resto = texto.partition(" ")
        comando = cabeca[1:].split("@")[0].lower()   # /tema@vitral_quiz_bot -> tema
        saida.append((comando, resto.strip()))
    return saida, maior + 1


def esc(texto: str) -> str:
    """Escapa texto para o modo HTML do Telegram."""
    return str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
