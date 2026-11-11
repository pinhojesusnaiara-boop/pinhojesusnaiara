"""Lista os canais para a matriz do GitHub Actions: python motor/listar.py [id]  ->  canais=[...]"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
pedido = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
saida = []
for arq in sorted((RAIZ / "canais").glob("*/canal.json")):
    cfg = json.loads(arq.read_text(encoding="utf-8"))
    ident = arq.parent.name
    if (pedido and ident != pedido) or (not pedido and not cfg.get("ativo")):
        continue
    tg = (cfg.get("telegram") or ident).upper().replace("-", "_")
    cf = cfg.get("cloudflare") or ""
    saida.append({"id": ident, "tg": tg, "cf": f"_{cf}" if cf else ""})
print("canais=" + json.dumps(saida))
