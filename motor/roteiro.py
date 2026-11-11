"""
Roteiro de um Short, montado a partir do canal.json: a IA escreve, três conferências independentes
checam cada informação e só fica o que a maioria aprovou. Cenas de plugin (ex.: salário) são
preenchidas pelo código com dados oficiais, nunca pela IA.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from comum import ErroAPI, pedir_json

COM_ITENS = ("lista",)
ANGULOS = ["Confira primeiro leis, normas e fontes oficiais.",
           "Confira pensando na realidade prática do dia a dia.",
           "Seja cético: procure exageros, generalizações e números inventados."]


def _molde_cena(c: dict, i: int) -> dict:
    t = c["tipo"]
    if t == "gancho":
        return {"tipo": "gancho", "titulo": "ATÉ 40 CARACTERES, EM MAIÚSCULAS", "fala": "...", "imagem": "cena em inglês"}
    if t == "lista":
        return {"tipo": "lista", "titulo": c.get("titulo", "TÍTULO"), "itens": ["...", "...", "...", "..."],
                "fala": "...", "imagem": "..."}
    if t == "destaque":
        return {"tipo": "destaque", "titulo": c.get("titulo", "TÍTULO"), "texto": "frase de até 60 caracteres",
                "fala": "...", "imagem": "..."}
    if t == "fim":
        return {"tipo": "fim", "imagem": "..."}
    return {"tipo": t, "imagem": "..."}   # cena de plugin: só a imagem vem da IA


def sistema(cfg: dict) -> str:
    cenas = [_molde_cena(c, i) for i, c in enumerate(cfg["cenas"])]
    pedidos = "\n".join(f"- cena {i + 1} ({c['tipo']}{': ' + c['titulo'] if c.get('titulo') else ''}): {c['pede']}"
                        for i, c in enumerate(cfg["cenas"]) if c.get("pede"))
    pers = cfg["personagem"]
    if pers.get("modo") == "por_video":
        campo_pers = f'  "personagem": "{pers.get("pedido", "descrição EM INGLÊS do personagem principal deste vídeo")}",\n'
        regra_img = ("Cada \"imagem\" descreve, em inglês, o MESMO personagem em uma situação diferente: ação, lugar, "
                     "objetos e enquadramento vertical. Varie poses e mãos.")
    elif pers.get("modo") == "fixo":
        campo_pers = ""
        regra_img = (f"O personagem fixo do canal é: {pers.get('descricao', '')}. Cada \"imagem\" descreve, em inglês, "
                     "esse personagem em uma situação diferente ligada ao tema, com enquadramento vertical.")
    else:
        campo_pers = ""
        regra_img = "Cada \"imagem\" descreve, em inglês, uma cena vertical diferente e marcante ligada ao que a fala diz."
    return f"""{cfg['contexto']}
Público: {cfg.get('publico', 'jovens e adultos brasileiros')}. Tom: {cfg.get('tom', 'direto e envolvente')}.
Português do Brasil, sem gírias forçadas.

Regras de conteúdo:
- Só afirme o que é verdade e pode ser conferido. Na dúvida, não afirme.
- Não invente leis, números, estatísticas, datas, nomes ou citações.
- Itens de tela: no máximo 30 caracteres cada, sem ponto final. Escreva 4 itens por lista, do mais
  importante para o menos importante; prefira fatos amplamente aceitos.
- Falas de narração: frases curtas, no máximo 24 palavras por fala (o gancho no máximo 12).
- Não use nomes de marcas, empresas ou pessoas reais.
{cfg.get('regras_extra', '')}

O que cada cena deve dizer:
{pedidos}

Devolva SOMENTE um JSON com este formato:
{{
{campo_pers}  "cenas": {json.dumps(cenas, ensure_ascii=False)},
  "youtube": {{"titulo": "até 70 caracteres, curioso, sem clickbait mentiroso", "descricao": "2 a 4 frases",
              "tags": ["...", "..."]}}
}}
As cenas vêm exatamente nessa ordem e com esses tipos. Títulos de lista e destaque podem mudar (até 18
caracteres, em maiúsculas). A cena "fim" só precisa da imagem: o texto final é fixo.
{regra_img}"""


def _afirmacoes(rot: dict) -> list:
    out = []
    for i, c in enumerate(rot["cenas"]):
        if c["tipo"] in COM_ITENS:
            for j, it in enumerate(c.get("itens", [])):
                out.append((i, it, j))
        if c["tipo"] == "destaque" and c.get("texto"):
            out.append((i, c["texto"], "texto"))
        if c["tipo"] in ("lista", "destaque", "gancho") and c.get("fala"):
            out.append((i, c["fala"], None))
    return out


def _uma_conferencia(cfg: dict, tema: str, afirm: list, k: int) -> dict:
    lista = "\n".join(f"{n + 1}. {t}" for n, (_, t, _) in enumerate(afirm))
    contexto = cfg["conferencia"].get("contexto") or f"Você confere fatos de roteiros do canal {cfg['nome']}."
    sis = (contexto + "\nPara cada afirmação numerada, responda se ela é VERDADEIRA e precisa para o tema indicado.\n"
           "Marque false se: estiver errada, exagerada, depender de lugar sem dizer isso, citar lei, número ou data "
           "de que você não tem certeza, ou for vaga a ponto de não informar nada.\n"
           'Devolva SOMENTE um JSON: [{"n": 1, "ok": true, "motivo": "curto"}, ...] com uma entrada por afirmação.\n'
           + ANGULOS[k % len(ANGULOS)])
    try:
        res = pedir_json(sis, f"Tema: {tema}\n\nAfirmações:\n{lista}", 4000)
    except Exception as e:   # noqa: BLE001 - uma conferência que falha não derruba as outras
        print(f"    conferência {k + 1} falhou ({e}); seguindo com as outras", flush=True)
        return {}
    votos = {}
    for r in res if isinstance(res, list) else []:
        try:
            votos[int(r["n"]) - 1] = (bool(r["ok"]), str(r.get("motivo", "")))
        except (KeyError, TypeError, ValueError):
            continue
    return votos


def conferir(cfg: dict, tema: str, rot: dict) -> tuple[dict, list]:
    passadas = cfg["conferencia"].get("passadas", 3)
    afirm = _afirmacoes(rot)
    if not afirm:
        return rot, []
    with ThreadPoolExecutor(max_workers=passadas) as pool:
        resultados = list(pool.map(lambda k: _uma_conferencia(cfg, tema, afirm, k), range(passadas)))
    if not any(resultados):
        raise ErroAPI("Nenhuma conferência respondeu.")
    reprovadas, remover = [], {}
    for n, (ci, txt, item) in enumerate(afirm):
        contra = [r[n][1] for r in resultados if n in r and not r[n][0]]
        respostas = sum(1 for r in resultados if n in r)
        if respostas == 0 or len(contra) >= 2 or (contra and respostas < 3):
            reprovadas.append(f"{txt}  ->  {contra[0] if contra else 'sem resposta'}")
            remover.setdefault(ci, set()).add(item)
    for ci, itens in remover.items():
        c = rot["cenas"][ci]
        if None in itens:
            c["fala"] = ""
        if "texto" in itens:
            c["texto"] = ""
        c["itens"] = [it for j, it in enumerate(c.get("itens", [])) if j not in itens]
        if not c.get("fala") and c["itens"][:3]:
            its = c["itens"][:3]   # a fala caiu: a narração lê os itens aprovados
            c["fala"] = (", ".join(its[:-1]) + " e " + its[-1] if len(its) > 1 else its[0]) + "."
    return rot, reprovadas


def validar(cfg: dict, rot: dict) -> str:
    esperado = [c["tipo"] for c in cfg["cenas"]]
    tipos = [c.get("tipo") for c in rot.get("cenas", [])]
    if tipos != esperado:
        return f"cenas fora de ordem: {tipos}"
    if cfg["personagem"].get("modo") == "por_video" and not rot.get("personagem"):
        return "sem personagem"
    for c in rot["cenas"]:
        if not c.get("imagem"):
            return f"cena {c['tipo']} sem imagem"
        if c["tipo"] == "lista" and not c.get("itens"):
            return "uma lista ficou sem itens"
        if c["tipo"] == "destaque" and not c.get("texto"):
            return "um destaque ficou sem texto"
        if c["tipo"] in ("gancho", "lista", "destaque") and not c.get("fala"):
            return f"cena {c['tipo']} sem fala"
    return ""


def gerar(canal, item: dict, plugins: list, extra: str = "", tentativas: int = 2) -> tuple[dict, list]:
    cfg = canal.cfg
    tema = item["tema"]
    sis = sistema(cfg)
    erro, todas = "", []
    for _ in range(tentativas):
        pedido = f"{cfg.get('rotulo_tema', 'Tema')}: {tema}\n"
        for k, v in item.items():
            if k not in ("tema", "slug"):
                pedido += f"{k}: {v}\n"
        pedido += extra
        if erro:
            pedido += f"\nA versão anterior foi recusada: {erro}. Corrija."
        rot = pedir_json(sis, pedido)
        erro = validar(cfg, rot) if isinstance(rot, dict) else "não é um objeto"
        if erro:
            print(f"  roteiro recusado ({erro})", flush=True)
            continue
        rot, reprovadas = conferir(cfg, tema, rot)
        todas += reprovadas
        for r in reprovadas:
            print(f"    cortado: {r}", flush=True)
        erro = validar(cfg, rot)
        if erro:
            print(f"  depois da conferência: {erro}", flush=True)
            continue
        completar(cfg, rot, item)
        for p in plugins:
            p.completar(rot, item)
        return rot, todas
    raise ErroAPI(f"Roteiro não passou: {erro}")


def completar(cfg: dict, rot: dict, item: dict):
    """Ids das cenas, textos fixos do fim e limites de tela."""
    fim = cfg["fim"]
    for i, c in enumerate(rot["cenas"]):
        c["id"] = f"c{i}-{c['tipo']}"
        if c["tipo"] == "fim":
            c["titulo"], c["fala"] = fim["titulo"], fim["fala"]
        elif c["tipo"] in ("lista", "destaque"):
            c["titulo"] = (c.get("titulo") or c["tipo"]).upper()[:18]
            c["itens"] = c.get("itens", [])[:3]
        elif c["tipo"] == "gancho":
            c["titulo"] = (c.get("titulo") or item["tema"]).upper()[:48]
    rot["item"] = item
    yt = rot.setdefault("youtube", {})
    tags = list(dict.fromkeys(yt.get("tags", []) + cfg["youtube"].get("tags_base", [])))
    yt["tags"] = tags[:15]
