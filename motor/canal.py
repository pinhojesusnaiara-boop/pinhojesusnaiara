"""
Configuração de um canal: canais/<id>/canal.json, fila de temas e estado.
O motor é o mesmo para todos os canais; tudo que muda de um canal para outro mora aqui.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CANAIS = RAIZ / "canais"

TIPOS_CENA = {"gancho", "lista", "destaque", "fim"}   # mais os tipos que os plugins acrescentam

PADRAO = {
    "ativo": False,
    "shorts_por_dia": 1,
    "voz": "pt-BR-Neural2-B",
    "provedor_voz": "google",
    "assinatura": "",
    "cloudflare": "",              # sufixo da conta: "" usa CLOUDFLARE_*, "2" usa CLOUDFLARE_*_2
    "plugins": [],
    "campos_fila": ["tema"],
    "personagem": {"modo": "por_video"},
    "cores": {"destaque": "#FFD21F", "valor": "#D9362B", "texto": "#141012"},
    "conferencia": {"passadas": 3},
    "youtube": {"tags_base": [], "rodape": ""},
}


def slug(txt: str) -> str:
    s = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def cor(hexa: str) -> tuple:
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4))


class Canal:
    def __init__(self, ident: str):
        self.id = ident
        self.pasta = CANAIS / ident
        arq = self.pasta / "canal.json"
        if not arq.exists():
            raise FileNotFoundError(f"Canal '{ident}' não tem {arq}")
        dados = json.loads(arq.read_text(encoding="utf-8"))
        self.cfg = {**PADRAO, **dados}
        for k in ("cores", "conferencia", "youtube", "personagem"):
            self.cfg[k] = {**PADRAO[k], **dados.get(k, {})}
        erro = validar(self.cfg)
        if erro:
            raise ValueError(f"canal.json de '{ident}' inválido: {erro}")

    def __getitem__(self, k):
        return self.cfg[k]

    def get(self, k, padrao=None):
        return self.cfg.get(k, padrao)

    @property
    def nome(self) -> str:
        return self.cfg["nome"]

    # ---------------------------------------------------------- fila e estado
    @property
    def arq_fila(self) -> Path:
        return self.pasta / "temas.txt"

    @property
    def arq_estado(self) -> Path:
        return self.pasta / "estado.json"

    def ler_fila(self) -> tuple[list[str], list[str]]:
        linhas = self.arq_fila.read_text(encoding="utf-8").splitlines() if self.arq_fila.exists() else []
        cab = [l for l in linhas if l.strip().startswith("#") or not l.strip()]
        itens = [l for l in linhas if l.strip() and not l.strip().startswith("#")]
        return cab, itens

    def salvar_fila(self, cab, itens):
        self.arq_fila.write_text("\n".join(cab + itens) + "\n", encoding="utf-8")

    def interpretar(self, linha: str) -> dict:
        partes = [p.strip() for p in linha.split("|")]
        campos = self.cfg["campos_fila"]
        item = {campos[i]: partes[i] for i in range(min(len(campos), len(partes)))}
        item.setdefault("tema", partes[0])
        if "nome" in item and "tema" not in campos:
            item["tema"] = item["nome"]
        return item

    def ler_estado(self) -> dict:
        if self.arq_estado.exists():
            return json.loads(self.arq_estado.read_text(encoding="utf-8"))
        return {"execucoes": [], "feitas": []}

    def salvar_estado(self, estado: dict):
        self.arq_estado.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validar(cfg: dict) -> str:
    for k in ("nome", "contexto", "estilo_imagem", "cenas", "fim"):
        if not cfg.get(k):
            return f"falta '{k}'"
    tipos = [c.get("tipo") for c in cfg["cenas"]]
    if not tipos or tipos[0] != "gancho" or tipos[-1] != "fim":
        return "as cenas precisam começar com 'gancho' e terminar com 'fim'"
    extras = set()
    for p in cfg.get("plugins", []):
        extras |= {"salario"} if p == "salario_caged" else set()
    for c in cfg["cenas"]:
        if c.get("tipo") not in TIPOS_CENA | extras:
            return f"tipo de cena desconhecido: {c.get('tipo')}"
    if not 4 <= len(tipos) <= 9:
        return "use de 4 a 9 cenas"
    fim = cfg["fim"]
    for k in ("titulo", "fala", "chamada_tela", "pergunta_tela"):
        if not fim.get(k):
            return f"falta fim.{k}"
    return ""


def listar(apenas_ativos: bool = False) -> list[str]:
    ids = []
    for arq in sorted(CANAIS.glob("*/canal.json")):
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not apenas_ativos or dados.get("ativo"):
            ids.append(arq.parent.name)
    return ids
