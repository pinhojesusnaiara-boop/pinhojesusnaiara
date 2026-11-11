"""
Identidade visual de um canal: 2 fotos de perfil (800x800) e 1 capa (2560x1440) com o nome
dentro da área segura do YouTube (1546x423 no centro). Saída em canais/<id>/marca/.

    python motor/marca.py --canal curiosidades-animais
"""
from __future__ import annotations

import argparse
import io
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from canal import RAIZ, Canal, cor
from imagens import SEM_TEXTO, _gerar

FONTES = RAIZ / "motor" / "fonts"


def fonte(n, t):
    return ImageFont.truetype(str(FONTES / f"BarlowCondensed-{n}.ttf"), int(t))


def _quebrar(d, txt, f, larg):
    linhas, atual = [], ""
    for p in txt.split():
        teste = (atual + " " + p).strip()
        if d.textlength(teste, font=f) > larg and atual:
            linhas.append(atual); atual = p
        else:
            atual = teste
    return linhas + [atual]


def capa(fundo: Image.Image, nome: str, slogan: str, destaque: tuple, destino):
    W, H = 2560, 1440
    esc = max(W / fundo.width, H / fundo.height)
    img = fundo.resize((int(fundo.width * esc), int(fundo.height * esc)), Image.LANCZOS)
    x0, y0 = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((x0, y0, x0 + W, y0 + H)).convert("RGBA")
    d = ImageDraw.Draw(img)
    tam = 170
    while True:
        f = fonte("ExtraBold", tam)
        linhas = _quebrar(d, nome.upper(), f, 1300)
        if len(linhas) <= 2 or tam < 90:
            break
        tam -= 10
    fs = fonte("SemiBold", 54)
    alt = len(linhas) * tam * 0.95 + (90 if slogan else 0)
    larg = max(d.textlength(l, font=f) for l in linhas)
    if slogan:
        larg = max(larg, d.textlength(slogan, font=fs))
    larg = min(1500, larg + 120)
    topo = H / 2 - alt / 2
    faixa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(faixa).rounded_rectangle([W / 2 - larg / 2, topo - 40, W / 2 + larg / 2, topo + alt + 50], 36,
                                            fill=(12, 10, 20, 165))
    img.alpha_composite(faixa.filter(ImageFilter.GaussianBlur(5)))
    d = ImageDraw.Draw(img)
    y = topo + tam * 0.48
    for l in linhas:
        d.text((W / 2, y), l, font=f, fill=destaque, stroke_width=9, stroke_fill=(20, 16, 18), anchor="mm")
        y += tam * 0.95
    if slogan:
        d.text((W / 2, topo + len(linhas) * tam * 0.95 + 55), slogan, font=fs, fill=(255, 255, 255), stroke_width=3,
               stroke_fill=(20, 16, 18), anchor="mm")
    img.convert("RGB").save(destino, quality=90)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canal", required=True)
    a = ap.parse_args()
    canal = Canal(a.canal)
    saida = canal.pasta / "marca"
    saida.mkdir(exist_ok=True)
    m = canal.get("marca") or {}
    estilo = f"{canal['estilo_imagem']}, {SEM_TEXTO}"
    perfil = m.get("perfil") or "the channel mascot, centered, plain bold background"
    for i in (1, 2):
        dados = _gerar(f"{perfil}. {estilo}", None, 1024, 1024)
        Image.open(io.BytesIO(dados)).convert("RGB").resize((800, 800), Image.LANCZOS).save(saida / f"perfil-{i}.png")
        print(f"perfil-{i} ok", flush=True)
    fundo = m.get("capa") or "wide scene about the channel subject, empty horizontal band in the middle"
    dados = _gerar(f"{fundo}. {estilo}", None, 1920, 1080)
    im = Image.open(io.BytesIO(dados)).convert("RGB")
    im.save(saida / "capa-fundo.jpg", quality=90)
    capa(im, canal.nome, canal.get("descricao_curta", ""), cor(canal["cores"].get("destaque", "#FFD21F")),
         saida / "capa.jpg")
    print("capa ok", flush=True)


if __name__ == "__main__":
    os.chdir(RAIZ)
    main()
