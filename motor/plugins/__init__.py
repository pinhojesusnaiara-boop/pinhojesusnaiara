"""Plugins de canal: dados oficiais e cenas especiais (ex.: salário do Novo Caged)."""
from __future__ import annotations

import importlib


def carregar(canal) -> list:
    out = []
    for nome in canal.get("plugins", []):
        mod = importlib.import_module(f"plugins.{nome}")
        out.append(mod.Plugin(canal))
    return out


def por_tipo(plugins: list) -> dict:
    return {importlib.import_module(type(p).__module__).TIPO: p for p in plugins}
