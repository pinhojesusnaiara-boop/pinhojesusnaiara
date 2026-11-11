"""
Narração (Google Cloud TTS) com cache: o mesmo texto com a mesma voz
nunca é gerado duas vezes. Provedor "teste" faz bipes no ritmo da fala, sem gastar cota.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.request
import wave
from pathlib import Path

import numpy as np

CACHE = Path("audio")
SR = 44100


class ErroVoz(Exception):
    pass


def _para_wav(origem: Path, destino: Path):
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(origem), "-ac", "1", "-ar", str(SR),
                        "-c:a", "pcm_s16le", str(destino)])
    if r.returncode != 0:
        raise ErroVoz("O ffmpeg não conseguiu converter o áudio.")


def falar_google(texto: str, voz: str, destino: Path):
    chave = os.environ.get("GOOGLE_TTS_KEY")
    if not chave:
        raise ErroVoz("Defina GOOGLE_TTS_KEY.")
    corpo = {"input": {"text": texto}, "voice": {"languageCode": "pt-BR", "name": voz},
             "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": SR, "speakingRate": 1.08}}
    req = urllib.request.Request("https://texttospeech.googleapis.com/v1/text:synthesize",
                                 data=json.dumps(corpo).encode(),
                                 headers={"content-type": "application/json", "x-goog-api-key": chave})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            bruto = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ErroVoz(f"Erro {e.code} da voz: {e.read().decode(errors='replace')[:300]}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErroVoz(f"A voz não respondeu: {e}") from None
    tmp = destino.with_suffix(".bruto.wav")
    tmp.write_bytes(base64.b64decode(bruto["audioContent"]))
    _para_wav(tmp, destino)
    tmp.unlink()


def falar_teste(texto: str, voz: str, destino: Path):
    partes = []
    for palavra in texto.split():
        dur = 0.055 * len(palavra) + 0.05
        t = np.arange(int(dur * SR)) / SR
        partes.append(0.15 * np.sin(2 * np.pi * 220 * t) * np.minimum(1, np.minimum(t, dur - t) * 60))
        partes.append(np.zeros(int((0.28 if palavra[-1] in ".?!:" else 0.05) * SR)))
    with wave.open(str(destino), "wb") as arq:
        arq.setnchannels(1); arq.setsampwidth(2); arq.setframerate(SR)
        arq.writeframes((np.concatenate(partes) * 32767).astype(np.int16).tobytes())


PROVEDORES = {"google": falar_google, "teste": falar_teste}


def duracao(caminho: Path) -> float:
    with wave.open(str(caminho), "rb") as arq:
        return arq.getnframes() / arq.getframerate()


def narrar(falas: dict, provedor: str, voz: str) -> dict:
    """falas: {nome: texto}. Devolve {nome: {arquivo, duracao}}."""
    CACHE.mkdir(exist_ok=True)
    out = {}
    for nome, texto in falas.items():
        if not texto.strip():
            continue
        marca = hashlib.sha256(f"{provedor}|{voz}|{texto}".encode()).hexdigest()[:16]
        arq = CACHE / f"{marca}.wav"
        if not arq.exists():
            PROVEDORES[provedor](texto, voz, arq)
        out[nome] = {"arquivo": str(arq), "duracao": round(duracao(arq), 3), "texto": texto}
    total = sum(v["duracao"] for v in out.values())
    print(f"  narração: {len(out)} falas, {total:.1f} s", flush=True)
    return out
