"""
Imagens do vídeo no Cloudflare Workers AI (FLUX.2 klein, nível gratuito).
1) cria o personagem; 2) gera cada cena usando o personagem como referência,
para o mesmo rosto e uniforme aparecerem em todas.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from PIL import Image

MODELO = "@cf/black-forest-labs/flux-2-klein-4b"
SEM_TEXTO = "no text, no letters, no logo"
MESMO = "Keep exactly the same character from image 0: same face, hair, skin tone and uniform. "


class ErroImagem(Exception):
    pass


class CotaEsgotada(ErroImagem):
    """A cota gratuita diária acabou (renova 00:00 UTC = 21:00 em Brasília)."""


def _gerar(prompt: str, ref: bytes | None, w: int, h: int) -> bytes:
    conta = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    token = os.environ["CLOUDFLARE_API_TOKEN"]
    b = uuid.uuid4().hex
    partes = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
              for k, v in {"prompt": prompt, "width": str(w), "height": str(h)}.items()]
    if ref:
        partes.append(f'--{b}\r\nContent-Disposition: form-data; name="input_image_0"; filename="ref.jpg"\r\n'
                      f'Content-Type: image/jpeg\r\n\r\n'.encode() + ref + b"\r\n")
    partes.append(f"--{b}--\r\n".encode())
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{conta}/ai/run/{MODELO}", data=b"".join(partes),
        headers={"Authorization": f"Bearer {token}", "content-type": f"multipart/form-data; boundary={b}"})
    espera = 5
    for tentativa in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                j = json.loads(r.read())
            img = (j.get("result") or {}).get("image") or j.get("image")
            if img:
                return base64.b64decode(img)
            raise ErroImagem(str(j)[:300])
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code == 429 and "neurons" in msg:
                raise CotaEsgotada("A cota diária de imagens do Cloudflare acabou; renova às 21h (Brasília).")
            if e.code in (429, 500, 502, 503, 504) and tentativa < 3:
                print(f"    imagem: erro {e.code}, nova tentativa em {espera} s", flush=True)
                time.sleep(espera); espera *= 2
                continue
            raise ErroImagem(f"Cloudflare respondeu {e.code}: {msg}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if tentativa < 3:
                time.sleep(espera); espera *= 2
                continue
            raise ErroImagem(f"Cloudflare não respondeu: {e}") from None
    raise ErroImagem("Cloudflare não respondeu.")


def _miniatura(dados: bytes) -> bytes:
    im = Image.open(io.BytesIO(dados)).convert("RGB")
    im.thumbnail((500, 500))   # referências precisam ser menores que 512x512
    b = io.BytesIO(); im.save(b, "JPEG", quality=92)
    return b.getvalue()


def gerar(rot: dict, pasta: Path, cfg: dict) -> dict:
    """Gera as imagens de cada cena em `pasta`. Devolve {id da cena: caminho}."""
    pasta.mkdir(parents=True, exist_ok=True)
    estilo = f"{cfg['estilo_imagem']}, {SEM_TEXTO}"
    falso = os.environ.get("IMAGENS_FALSAS")
    pers = cfg["personagem"]
    descricao = rot.get("personagem") if pers.get("modo") == "por_video" else pers.get("descricao")
    ref = None
    if descricao:
        ref_arq = pasta / "personagem.jpg"
        if falso:
            _falsa(ref_arq, "personagem")
        elif not ref_arq.exists():
            t = time.time()
            ref_arq.write_bytes(_gerar(f"Full body {descricao}, standing on a simple studio floor. {estilo}",
                                       None, 768, 1344))
            print(f"  personagem pronto em {time.time() - t:.0f} s", flush=True)
        ref = _miniatura(ref_arq.read_bytes())
    saida = {}
    for c in rot["cenas"]:
        arq = pasta / f"{c['id']}.jpg"
        if falso:
            _falsa(arq, c["id"])
        elif not arq.exists():
            t = time.time()
            prompt = f"{MESMO if ref else ''}{c['imagem']}. {estilo}"
            arq.write_bytes(_gerar(prompt, ref, 1080, 1920))
            print(f"  cena {c['id']} pronta em {time.time() - t:.0f} s", flush=True)
        saida[c["id"]] = arq
    return saida


def _falsa(arq: Path, nome: str):
    """Para testes sem gastar cota: fundo colorido com um 'boneco' simples."""
    from PIL import ImageDraw
    cor = (abs(hash(nome)) % 150 + 50, 80, 70)
    im = Image.new("RGB", (1080, 1920), cor)
    d = ImageDraw.Draw(im)
    d.ellipse([340, 560, 740, 960], fill=(240, 200, 170))
    d.rounded_rectangle([400, 940, 680, 1500], 60, fill=(30, 30, 35))
    d.text((40, 40), nome, fill=(255, 255, 255))
    im.save(arq, quality=90)
