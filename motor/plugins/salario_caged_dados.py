"""
Salário da profissão a partir do Salario.com.br, que publica os dados do Novo Caged
(Ministério do Trabalho) por CBO. Os números do vídeo vêm daqui, nunca da IA.
"""
from __future__ import annotations

import html
import re
import urllib.request

BASE = "https://www.salario.com.br/profissao/{slug}/"


def _reais(txt: str) -> int:
    """'2.582,50' -> 2583 (arredonda para o real mais próximo)."""
    inteiro, _, cent = txt.partition(",")
    valor = int(inteiro.replace(".", "")) + (int(cent[:2] or 0) / 100)
    return int(round(valor))


def salario(slug: str) -> dict:
    url = BASE.format(slug=slug)
    req = urllib.request.Request(url, headers={"user-agent": "Mozilla/5.0 (fabrica-de-canais)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        bruto = r.read().decode("utf-8", errors="replace")
    titulo = re.search(r"<title>([^<]*)</title>", bruto)
    periodo = re.search(r"\((\w{3}/\d{4})\)", titulo.group(1) if titulo else "")
    texto = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", bruto)))
    m = re.search(r"ganha em m[ée]dia R\$ ?([\d.]+,\d{2}).{0,250}?piso salarial de R\$ ?([\d.]+,\d{2})"
                  r" ao teto salarial de R\$ ?([\d.]+,\d{2})", texto)
    if not m:
        raise ValueError(f"Não achei o salário em {url}")
    jornada = re.search(r"jornada de (\d+) horas semanais", texto)
    return {"media": _reais(m.group(1)), "piso": _reais(m.group(2)), "teto": _reais(m.group(3)),
            "jornada": int(jornada.group(1)) if jornada else None,
            "periodo": periodo.group(1) if periodo else "", "url": url,
            "cbo": re.sub(r"\D", "", slug.rsplit("cbo-", 1)[-1])}


def reais(v: int) -> str:
    return f"R$ {v:,}".replace(",", ".")


if __name__ == "__main__":
    import sys
    print(salario(sys.argv[1] if len(sys.argv) > 1 else "bombeiro-civil-cbo-517110"))
