"""
Monta o Short (1080x1920): cada cena dura o tempo da sua narração; cenário com zoom lento e o
personagem recortado e animado por cima, transições, títulos e itens no ritmo da fala.
Cores e textos vêm do canal.json; cenas especiais vêm dos plugins.
"""
from __future__ import annotations

import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from canal import cor

W, H, FPS, SR = 1080, 1920, 30, 44100
AMARELO, PRETO, BRANCO, VERMELHO = (255, 210, 31), (20, 16, 18), (255, 255, 255), (217, 54, 43)
FONTES = Path(__file__).parent / "fonts"
FADE, PRE, POS = 0.4, 0.25, 0.5
MINIMO = {"gancho": 3.0, "destaque": 3.5, "fim": 3.5}


def fonte(n, t):
    return ImageFont.truetype(str(FONTES / f"BarlowCondensed-{n}.ttf"), int(t))


def suave(x):
    x = min(1, max(0, x)); return x * x * (3 - 2 * x)


# ------------------------------------------------------------------ linha do tempo
def linha_do_tempo(rot: dict, narr: dict, plugins: dict | None = None) -> list:
    t, cenas = 0.0, []
    for c in rot["cenas"]:
        fala = narr.get(c["id"])
        p = (plugins or {}).get(c["tipo"])
        minimo = p.duracao_minima() if p else MINIMO.get(c["tipo"], 3.0)
        dur = max(minimo, PRE + (fala["duracao"] if fala else 0) + POS)
        cenas.append({**c, "ini": t, "fim": t + dur, "dur": dur,
                      "fala_dur": fala["duracao"] if fala else dur * 0.7})
        t += dur
    return cenas


def trilha(cenas: list, narr: dict, destino: Path) -> float:
    total = cenas[-1]["fim"]
    pcm = np.zeros(int(total * SR) + SR, dtype=np.float32)
    for c in cenas:
        f = narr.get(c["id"])
        if not f:
            continue
        with wave.open(f["arquivo"], "rb") as a:
            x = np.frombuffer(a.readframes(a.getnframes()), dtype=np.int16).astype(np.float32) / 32767
        i = int((c["ini"] + PRE) * SR)
        pcm[i:i + len(x)] += x[: len(pcm) - i]
    with wave.open(str(destino), "wb") as a:
        a.setnchannels(1); a.setsampwidth(2); a.setframerate(SR)
        a.writeframes((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())
    return total


# ------------------------------------------------------------------ personagem vivo
_SESSAO = None


def separar(im):
    """Recorta o personagem (rembg) e preenche o buraco no cenário (inpaint).
    Devolve (frente RGBA, fundo RGB) ou None se as bibliotecas não estiverem disponíveis."""
    global _SESSAO
    try:
        import cv2
        from rembg import new_session, remove
    except ImportError:
        return None
    try:
        if _SESSAO is None:
            _SESSAO = new_session("u2net")
        frente = remove(im, session=_SESSAO)
        # partes semitransparentes (ex.: cabeça do machado) ficam sólidas, para não sumirem
        alfa = np.clip(np.array(frente.split()[-1]).astype(np.float32) * 2.2, 0, 255).astype(np.uint8)
        frente.putalpha(Image.fromarray(alfa))
        if (alfa > 128).mean() < 0.03:      # não achou personagem: segue sem animar
            return None
        buraco = cv2.dilate((alfa > 30).astype(np.uint8) * 255, np.ones((25, 25), np.uint8))
        pequeno = 0.5   # inpaint em meia resolução: bem mais rápido e o resultado fica atrás do boneco
        rgb = np.array(im)
        r = cv2.resize(rgb, None, fx=pequeno, fy=pequeno)
        b = cv2.resize(buraco, (r.shape[1], r.shape[0]))
        cheio = cv2.inpaint(r[:, :, ::-1], b, 7, cv2.INPAINT_TELEA)[:, :, ::-1]
        cheio = cv2.resize(cheio, (rgb.shape[1], rgb.shape[0]))
        m = (cv2.GaussianBlur(buraco, (31, 31), 0) / 255.0)[..., None]
        fundo = (rgb * (1 - m) + cheio * m).astype(np.uint8)
        return frente, Image.fromarray(fundo)
    except Exception as e:   # noqa: BLE001 - sem recorte o vídeo sai do jeito antigo
        print(f"  recorte do personagem falhou ({e}); seguindo sem animação", flush=True)
        return None


def _mola(x):
    x = min(1.0, max(0.0, x))
    return 1 - math.exp(-6 * x) * math.cos(9 * x)


def vivo(fr, caixa, tl, k):
    """Entrada com pulinho, respiração e um leve balanço, com o pivô nos pés."""
    px, py = (caixa[0] + caixa[2]) / 2, caixa[3]
    ent = 0.86 + 0.14 * _mola(tl / 0.55) if k > 0 else 1.0
    resp = 1 + 0.012 * math.sin(2 * math.pi * tl / 1.9)
    sx, sy = ent * (1 - 0.004 * math.sin(2 * math.pi * tl / 1.9)), ent * resp
    ang = math.radians(1.3 * math.sin(2 * math.pi * tl / 3.2 + k))
    dy = -10 * max(0.0, math.sin(math.pi * min(1, tl / 0.5))) if k > 0 else 0.0
    ca, sa = math.cos(ang), math.sin(ang)
    # transformação inversa (saída -> origem) para Image.transform
    a, b = ca / sx, sa / sx
    d, e = -sa / sy, ca / sy
    ox, oy = px, py + dy
    c = px - a * ox - b * oy
    f = py - d * ox - e * oy
    return fr.transform((W, H), Image.AFFINE, (a, b, c, d, e, f), resample=Image.BILINEAR)


# ------------------------------------------------------------------ desenho
class Montador:
    suave = staticmethod(suave)
    PRETO, BRANCO = PRETO, BRANCO

    def __init__(self, rot, imagens, cenas, cfg, plugins=None):
        self.rot, self.cenas, self.cfg = rot, cenas, cfg
        self.assinatura = cfg.get("assinatura", "")
        self.plugins = plugins or {}
        self.DESTAQUE = cor(cfg["cores"].get("destaque", "#FFD21F"))
        self.VALOR = cor(cfg["cores"].get("valor", "#D9362B"))
        self.imgs = {}
        self.frentes = {}   # personagem recortado (RGBA), quando o recorte funciona
        for tipo, arq in imagens.items():
            im = Image.open(arq).convert("RGB")
            esc = max(W / im.width, H / im.height) * 1.12
            tam = (int(im.width * esc), int(im.height * esc))
            partes = separar(im)
            if partes:
                frente, fundo_limpo = partes
                self.imgs[tipo] = fundo_limpo.resize(tam, Image.LANCZOS)
                self.frentes[tipo] = frente.resize(tam, Image.LANCZOS)
            else:
                self.imgs[tipo] = im.resize(tam, Image.LANCZOS)
        m = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(m)
        for y in range(H):
            d.line([(0, y), (W, y)], fill=int(min(255, max(0, 1 - y / 620) * 170 + max(0, (y - 1200) / 720) * 190)))
        self.sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.sombra.putalpha(m)

    @staticmethod
    def _janela(im, z, k, p, modo="RGB"):
        cw, ch = im.width / (1.12 * z), im.height / (1.12 * z)
        dx = (im.width - cw) * (0.5 + 0.25 * (1 if k % 2 else -1) * (p - 0.5))
        dy = (im.height - ch) * 0.45
        return im.crop((int(dx), int(dy), int(dx + cw), int(dy + ch))).resize((W, H), Image.BILINEAR)

    def fundo(self, k, tl):
        c = self.cenas[k]
        p = min(1, tl / c["dur"])
        frente = self.frentes.get(c["id"])
        if frente is None:
            return self._janela(self.imgs[c["id"]], 1 + 0.08 * p, k, p)
        # paralaxe: o cenário aproxima devagar, o personagem um pouco mais rápido
        base = self._janela(self.imgs[c["id"]], 1 + 0.035 * p, k, p).convert("RGBA")
        fr = self._janela(frente, 1 + 0.08 * p, k, p)
        caixa = fr.getbbox()
        if caixa:
            fr = vivo(fr, caixa, tl, k)
        base.alpha_composite(fr)
        return base.convert("RGB")

    @staticmethod
    def contornado(d, xy, txt, f, cor=AMARELO, larg=9, ancora="mm"):
        d.text(xy, txt, font=f, fill=cor, stroke_width=larg, stroke_fill=PRETO, anchor=ancora)

    def titulo(self, d, texto, y0, tam=116, cor=None):
        cor = cor or self.DESTAQUE
        while True:
            f = fonte("ExtraBold", tam)
            linhas, atual = [], ""
            for p in texto.split():
                teste = (atual + " " + p).strip()
                if d.textlength(teste, font=f) > W - 110 and atual:
                    linhas.append(atual); atual = p
                else:
                    atual = teste
            linhas.append(atual)
            if len(linhas) <= 2 or tam < 70:
                break
            tam -= 8
        for i, l in enumerate(linhas):
            self.contornado(d, (W / 2, y0 + i * tam * 0.98), l, f, cor=cor)

    @staticmethod
    def cartao(img, box, cor=(255, 255, 255, 238)):
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([box[0] + 8, box[1] + 12, box[2] + 8, box[3] + 12], 34,
                                             fill=(0, 0, 0, 110))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
        c = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(c).rounded_rectangle(box, 34, fill=cor, outline=PRETO + (255,), width=5)
        img.alpha_composite(c)

    def lista(self, img, itens, tl, fala_dur):
        n = len(itens)
        passo = max(0.45, (fala_dur * 0.8) / max(1, n))
        vis = [it for j, it in enumerate(itens) if tl > 0.35 + j * passo]
        if not vis:
            return
        y = 1660 - 96 * len(vis)
        self.cartao(img, (60, y, W - 60, y + 50 + 96 * len(vis)))
        d = ImageDraw.Draw(img)
        for j, txt in enumerate(vis):
            tam = 56
            while d.textlength("• " + txt, font=fonte("SemiBold", tam)) > W - 200 and tam > 36:
                tam -= 2
            d.text((100, y + 72 + 96 * j), "• " + txt, font=fonte("SemiBold", tam), fill=PRETO, anchor="lm")

    @staticmethod
    def ajustado(d, xy, txt, peso, tam, larg, cor):
        while d.textlength(txt, font=fonte(peso, tam)) > larg and tam > 30:
            tam -= 2
        d.text(xy, txt, font=fonte(peso, tam), fill=cor, anchor="mm")

    def texto_grande(self, img, txt, tl):
        """Cartão com uma frase em destaque (até 3 linhas), entrando com um leve crescimento."""
        d = ImageDraw.Draw(img)
        tam = 84
        while True:
            f = fonte("ExtraBold", tam)
            linhas, atual = [], ""
            for p in txt.split():
                teste = (atual + " " + p).strip()
                if d.textlength(teste, font=f) > W - 240 and atual:
                    linhas.append(atual); atual = p
                else:
                    atual = teste
            linhas.append(atual)
            if len(linhas) <= 3 or tam <= 52:
                break
            tam -= 6
        alt = int(len(linhas) * tam * 1.08 + 90)
        y0 = 1640 - alt
        self.cartao(img, (70, y0, W - 70, y0 + alt))
        d = ImageDraw.Draw(img)
        for i, l in enumerate(linhas):
            d.text((W / 2, y0 + 45 + tam * 0.55 + i * tam * 1.08), l, font=f, fill=PRETO, anchor="mm")

    def rodape(self, d, txt):
        d.text((W / 2, 1862), txt, font=fonte("SemiBold", 34), fill=(255, 240, 225), anchor="mm")

    def quadro(self, i):
        t = i / FPS
        k = next((j for j, c in enumerate(self.cenas) if c["ini"] <= t < c["fim"]), len(self.cenas) - 1)
        c = self.cenas[k]
        tl = t - c["ini"]
        base = self.fundo(k, tl)
        if k > 0 and tl < FADE:
            ant = self.fundo(k - 1, self.cenas[k - 1]["dur"] - FADE + tl)
            base = Image.blend(ant, base, suave(tl / FADE))
        img = base.convert("RGBA")
        img.alpha_composite(self.sombra)
        d = ImageDraw.Draw(img)
        tipo = c["tipo"]
        fim = self.cfg["fim"]
        if tipo in self.plugins:
            self.plugins[tipo].desenhar(self, img, c, tl)
        elif tipo == "gancho":
            self.titulo(d, c["titulo"], 200 - (1 - suave(tl / 0.35)) * 50)
        elif tipo == "destaque":
            self.titulo(d, c["titulo"], 200)
            if tl > 0.35:
                self.texto_grande(img, c.get("texto", ""), tl)
        elif tipo == "fim":
            self.titulo(d, fim["titulo"], 200, tam=140)
            self.cartao(img, (90, 1440, W - 90, 1570), cor=self.DESTAQUE + (245,))
            d = ImageDraw.Draw(img)
            self.ajustado(d, (W / 2, 1505), fim["chamada_tela"], "ExtraBold", 66, W - 240, PRETO)
            f = fonte("ExtraBold", 72)
            tam = 72
            while d.textlength(fim["pergunta_tela"], font=f) > W - 120 and tam > 44:
                tam -= 4; f = fonte("ExtraBold", tam)
            self.contornado(d, (W / 2, 1680), fim["pergunta_tela"], f, cor=BRANCO)
        else:
            self.titulo(d, c["titulo"], 200)
            self.lista(img, c.get("itens", []), tl, c["fala_dur"])
        if self.assinatura:
            d = ImageDraw.Draw(img)
            d.text((W - 40, 60), self.assinatura, font=fonte("SemiBold", 36), fill=(255, 255, 255), anchor="rm",
                   stroke_width=3, stroke_fill=PRETO)
        return img.convert("RGB").tobytes()


def montar(rot: dict, imagens: dict, narr: dict, saida: Path, cfg: dict, plugins: dict | None = None,
           so_quadro: float | None = None):
    cenas = linha_do_tempo(rot, narr, plugins)
    m = Montador(rot, imagens, cenas, cfg, plugins)
    if so_quadro is not None:
        Image.frombytes("RGB", (W, H), m.quadro(int(so_quadro * FPS))).save(saida)
        return cenas
    saida.parent.mkdir(parents=True, exist_ok=True)
    audio = saida.with_suffix(".wav")
    total = trilha(cenas, narr, audio)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio), "-shortest",
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(saida)],
                          stdin=subprocess.PIPE)
    n = int(total * FPS)
    for i in range(n):
        ff.stdin.write(m.quadro(i))
        if i % 300 == 0:
            print(f"  montando {i}/{n}", flush=True)
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError("O ffmpeg falhou ao montar o vídeo.")
    audio.unlink(missing_ok=True)
    print(f"  vídeo pronto: {saida} ({total:.1f} s)", flush=True)
    return cenas
