"""
Rotina diária de um canal (roda no GitHub Actions, um job por canal).

    python motor/rotina.py --canal meu-canal                  # automático: produz os Shorts do dia uma vez
    python motor/rotina.py --canal meu-canal --formato short  # força um Short agora
    python motor/rotina.py --canal novo --formato previa  # Short de teste da Fábrica (não mexe na fila)

Cada Short pronto vai para o Telegram do canal com título, descrição e tags para colar no YouTube.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import imagens
import montar
import narrar
import plugins as plug
import roteiro
import telegram
from canal import RAIZ, Canal, slug

OUT = RAIZ / "out"
BRT = timezone(timedelta(hours=-3))


def legenda(rot: dict, extras: list[str]) -> str:
    yt = rot["youtube"]
    partes = [f"<b>{telegram.esc(yt['titulo'])}</b>", telegram.esc(yt.get("descricao", ""))]
    partes += [telegram.esc(e) for e in extras if e]
    partes.append(f"<i>Tags:</i> {telegram.esc(', '.join(yt.get('tags', [])))}")
    return "\n\n".join(partes)


def fazer_short(canal: Canal, item: dict, pasta: Path, avisar: bool = True) -> dict:
    tema = item["tema"]
    print(f"\n=== {canal.nome}: {tema} ===", flush=True)
    pls = plug.carregar(canal)
    extra = "".join(p.antes(item) for p in pls)
    rot, reprovadas = roteiro.gerar(canal, item, pls, extra)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "roteiro.json").write_text(json.dumps(rot, ensure_ascii=False, indent=2), encoding="utf-8")
    figs = imagens.gerar(rot, pasta / "cenas", canal.cfg)
    narr = narrar.narrar({c["id"]: c.get("fala", "") for c in rot["cenas"]},
                         canal["provedor_voz"], canal["voz"])
    video = pasta / f"{slug(tema)}-short.mp4"
    cenas = montar.montar(rot, figs, narr, video, canal.cfg, plug.por_tipo(pls))
    dur = int(cenas[-1]["fim"]) + 1
    if avisar and telegram.configurado():
        telegram.video(video, f"Short: <b>{telegram.esc(tema)}</b>", 1080, 1920, dur)
        telegram.mensagem(legenda(rot, [p.legenda(rot) for p in pls] + [canal["youtube"].get("rodape", "")]))
        if reprovadas:
            telegram.mensagem("Conferência cortou do roteiro:\n• " + "\n• ".join(telegram.esc(r) for r in reprovadas))
    return {"tema": tema, "video": str(video), "duracao": dur, "cortadas": reprovadas, "roteiro": rot}


def previa(canal: Canal):
    """Short de teste da Fábrica: primeiro tema da fila, sem tirar da fila. Vai para canais/<id>/previa/."""
    _, fila = canal.ler_fila()
    if not fila:
        raise SystemExit("A fila de temas está vazia.")
    pasta = OUT / canal.id / "previa"
    r = fazer_short(canal, canal.interpretar(fila[0]), pasta, avisar=False)
    destino = canal.pasta / "previa"
    destino.mkdir(exist_ok=True)
    shutil.copy(r["video"], destino / "previa.mp4")
    shutil.copy(pasta / "roteiro.json", destino / "roteiro.json")
    (destino / "resumo.json").write_text(json.dumps(
        {"tema": r["tema"], "duracao": r["duracao"], "cortadas": r["cortadas"],
         "quando": datetime.now(BRT).strftime("%d/%m %H:%M")}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prévia pronta: {destino / 'previa.mp4'}")


def main():
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--canal", required=True)
    ap.add_argument("--formato", default="auto", choices=["auto", "short", "previa"])
    args = ap.parse_args()

    canal = Canal(args.canal)
    if args.formato == "previa":
        return previa(canal)
    if args.formato == "auto" and not canal["ativo"]:
        print(f"{canal.nome} está pausado (ativo: false).")
        return

    estado = canal.ler_estado()
    agora = datetime.now(BRT)
    hoje = agora.strftime("%Y-%m-%d")
    if args.formato == "auto" and estado.get("ultimo_dia_auto") == hoje:
        print(f"Os Shorts de {hoje} já foram produzidos; nada a fazer.")
        return
    quantos = canal["shorts_por_dia"] if args.formato == "auto" else 1

    cab, fila = canal.ler_fila()
    feitos, erros, cota = [], [], False
    for _ in range(quantos):
        if not fila:
            erros.append("A fila de temas está vazia. Adicione temas pela Fábrica ou em temas.txt.")
            break
        linha = fila.pop(0)
        try:
            item = canal.interpretar(linha)
            r = fazer_short(canal, item, OUT / canal.id / f"{hoje}-{slug(item['tema'])}")
            feitos.append(r)
            estado["feitas"] = (estado.get("feitas", []) + [{"quando": agora.strftime("%d/%m %H:%M"),
                                                               "tema": r["tema"]}])[-200:]
        except Exception as e:   # noqa: BLE001 - qualquer falha: avisa, devolve à fila e segue
            traceback.print_exc()
            fila.insert(0, linha) if isinstance(e, imagens.CotaEsgotada) else fila.append(linha)
            cota = cota or isinstance(e, imagens.CotaEsgotada)
            erros.append(f"{linha.split('|')[0].strip()}: {e}")
        canal.salvar_fila(cab, fila)

    if args.formato == "auto" and feitos:
        estado["ultimo_dia_auto"] = hoje
    estado["execucoes"] = (estado.get("execucoes", []) + [{
        "quando": agora.strftime("%d/%m %H:%M"), "formato": args.formato,
        "feitos": [f["tema"] for f in feitos], "erros": [e[:300] for e in erros]}])[-30:]
    canal.salvar_estado(estado)

    if erros:
        fim = ("A cota de imagens volta às 21h; o próximo horário tenta de novo." if cota
               else "O tema voltou para o fim da fila.")
        msg = (f"⚠️ <b>{telegram.esc(canal.nome)}</b>: problema na rotina.\n\n"
               + "\n".join("• " + telegram.esc(e[:400]) for e in erros) + f"\n\n{fim}")
        if telegram.configurado():
            try:
                telegram.mensagem(msg)
                (OUT / f".falha-avisada-{canal.id}").write_text("1")
            except Exception:   # noqa: BLE001
                pass
        print("\n".join(erros), file=sys.stderr)
        sys.exit(1)
    print(f"\nPronto: {len(feitos)} Short(s).")


if __name__ == "__main__":
    os.chdir(RAIZ)
    main()
