"""
Fábrica de canais: transforma uma ideia em um canal pronto para o motor.

    python motor/ficha.py --canal curiosidades-animais --ideia "curiosidades de animais" \
        --estilo "massinha" --voz feminina
    python motor/ficha.py --canal curiosidades-animais --mais-temas 30

Gera em canais/<id>/: canal.json (pausado até você ativar), temas.txt e ficha.json
(análise do nicho, textos do YouTube e riscos de monetização).
Os agentes da Fábrica são etapas com papéis separados: estrategista, roteirista, diretor de arte e
operador do canal. Cada um recebe o que o anterior decidiu.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from canal import CANAIS, RAIZ, validar
from comum import ErroAPI, pedir_json

VOZES = {"masculina": "pt-BR-Neural2-B", "feminina": "pt-BR-Neural2-C", "": "pt-BR-Neural2-B"}

ESTRATEGISTA = """Você é o estrategista de uma fábrica de canais "dark" (sem rosto) no YouTube, em português do Brasil.
Recebe uma ideia de nicho e avalia com honestidade, pensando em Shorts diários feitos 100% por IA
(roteiro, imagens e narração), com conferência de fatos.

Considere as regras do Programa de Parcerias do YouTube: conteúdo "reutilizado" ou "repetitivo/produzido em massa"
não é monetizado. O canal precisa de valor próprio (informação conferida, roteiro original, formato reconhecível).
Evite nichos que dependem de imagens reais de pessoas, marcas, notícias de última hora, conselhos médicos,
jurídicos ou financeiros personalizados, e de qualquer coisa protegida por direitos autorais.

Devolva SOMENTE um JSON:
{
  "nomes": ["3 opções de nome do canal, curtas e fáceis de lembrar"],
  "nome": "o nome escolhido entre as opções",
  "handles": ["3 opções de @ sem acentos, ex.: @curiosobicho"],
  "slogan": "até 50 caracteres",
  "publico": "quem assiste, em uma frase",
  "promessa": "o que a pessoa ganha em cada vídeo, em uma frase",
  "formato_short": "como é cada Short, em 2 frases",
  "ideias_video_longo": ["3 ideias de vídeo longo para depois"],
  "concorrencia": "como o nicho está no YouTube Brasil e como este canal se diferencia",
  "rpm_estimado": "faixa em reais por mil visualizações de vídeos longos, deixando claro que é estimativa",
  "riscos": ["riscos de monetização ou de conteúdo e como o canal evita cada um"],
  "nota": 0-10 (potencial do nicho para crescer e monetizar),
  "veredito": "1 a 2 frases: vale a pena? com qual cuidado?"
}"""

ROTEIRISTA = """Você é o roteirista-chefe da fábrica. Recebe a estratégia de um canal e desenha o FORMATO fixo dos Shorts.
O motor de vídeo só conhece estes tipos de cena:
- "gancho": título grande + 1 fala curta que prende (sempre a primeira).
- "lista": título curto + até 3 itens curtos na tela + 1 fala.
- "destaque": título curto + 1 frase grande na tela + 1 fala (bom para o fato mais surpreendente).
- "fim": encerramento fixo com chamada para curtir, seguir e comentar (sempre a última).
Use de 5 a 7 cenas no total; o Short deve ter de 35 a 55 segundos.

Devolva SOMENTE um JSON:
{
  "rotulo_tema": "como se chama cada assunto do canal (ex.: Animal, Profissão, Personagem)",
  "contexto": "1 a 2 frases que apresentam o canal ao roteirista de cada vídeo (nome, assunto, missão)",
  "tom": "tom da narração",
  "regras_extra": "regras específicas deste nicho para o roteirista (comece cada linha com '- ')",
  "cenas": [{"tipo": "gancho", "pede": "o que a cena diz"}, {"tipo": "lista", "titulo": "ATÉ 18 CARACTERES", "pede": "..."}, ..., {"tipo": "fim"}],
  "conferencia": "1 frase: quem confere os fatos deste nicho e o que mais cuida (ex.: 'Você confere fatos de biologia...')",
  "fim": {"titulo": "NOME DO CANAL EM MAIÚSCULAS (até 22 caracteres)",
          "fala": "encerramento de até 25 palavras pedindo like, para seguir o canal e comentar qual tema vem depois",
          "chamada_tela": "CURTA  •  SIGA  •  COMENTE",
          "pergunta_tela": "pergunta de até 28 caracteres puxando comentário"},
  "temas": ["30 temas diferentes para os primeiros Shorts, do mais chamativo para o menos; cada um em até 40 caracteres"],
  "tags_base": ["5 tags que valem para todos os vídeos"],
  "rodape": "frase fixa para o fim da descrição dos vídeos"
}"""

DIRETOR = """Você é o diretor de arte da fábrica. Recebe a estratégia e o formato de um canal e define a identidade visual.
As imagens são feitas pelo FLUX (texto em inglês) em formato vertical, sem nenhum texto escrito nelas.

Devolva SOMENTE um JSON:
{
  "estilo_imagem": "EM INGLÊS: estilo visual fixo de todas as imagens, 30 a 60 palavras (material, iluminação, câmera, acabamento)",
  "personagem": {"modo": "por_video" | "fixo" | "nenhum",
                 "descricao": "se fixo: EM INGLÊS, o mascote do canal (aparência completa)",
                 "pedido": "se por_video: o que o roteirista deve descrever do personagem de cada vídeo, em português"},
  "cores": {"destaque": "#RRGGBB para títulos (bem legível com contorno preto)", "valor": "#RRGGBB para números e ênfases"},
  "perfil": "EM INGLÊS: imagem da foto de perfil (1 elemento central, fundo liso de cor forte, legível em círculo pequeno)",
  "capa": "EM INGLÊS: imagem da capa 16:9, com uma faixa horizontal vazia no meio para o nome do canal; elementos nas laterais",
  "justificativa": "1 frase: por que esse visual combina com o público"
}"""

OPERADOR = """Você é o operador de canais da fábrica. Recebe tudo o que foi decidido e escreve os textos do YouTube.
Devolva SOMENTE um JSON:
{
  "descricao_canal": "descrição do canal com 3 parágrafos curtos, em português, terminando com um convite para comentar",
  "palavras_chave": ["10 palavras-chave do canal"],
  "categoria": "categoria do YouTube (ex.: Educação, Entretenimento, Ciência e tecnologia)"
}"""


def _pedir(papel: str, sistema: str, pedido: str) -> dict:
    print(f"\n[{papel}]", flush=True)
    for tentativa in range(2):
        r = pedir_json(sistema, pedido + ("\nResponda só com o JSON pedido." if tentativa else ""))
        if isinstance(r, dict):
            return r
    raise ErroAPI(f"O {papel} não devolveu um JSON.")


def criar(ident: str, ideia: str, estilo: str = "", voz: str = "", publico: str = ""):
    pasta = CANAIS / ident
    pasta.mkdir(parents=True, exist_ok=True)
    base = f"Ideia do canal: {ideia}\n"
    if publico:
        base += f"Público desejado: {publico}\n"
    if estilo:
        base += f"Estilo visual desejado: {estilo}\n"

    estrategia = _pedir("estrategista", ESTRATEGISTA, base)
    contexto = base + "\nEstratégia aprovada:\n" + json.dumps(estrategia, ensure_ascii=False)

    erro = ""
    for _ in range(3):
        formato = _pedir("roteirista", ROTEIRISTA, contexto + (f"\n\nCorrija: {erro}" if erro else ""))
        arte = _pedir("diretor de arte", DIRETOR, contexto + "\n\nFormato:\n" +
                      json.dumps({k: formato.get(k) for k in ("cenas", "tom", "rotulo_tema")}, ensure_ascii=False))
        cfg = montar_cfg(estrategia, formato, arte, voz)
        erro = validar(cfg)
        if not erro:
            break
        print(f"  formato recusado: {erro}", flush=True)
    if erro:
        raise ErroAPI(f"O formato do canal não passou: {erro}")

    operador = _pedir("operador", OPERADOR, contexto + "\n\nNome: " + cfg["nome"])
    temas = [t.strip().replace("|", "-") for t in formato.get("temas", []) if t and t.strip()]
    (pasta / "canal.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (pasta / "temas.txt").write_text(
        f"# Fila do {cfg['nome']}. Um tema por linha; a primeira linha é a próxima.\n" + "\n".join(temas) + "\n",
        encoding="utf-8")
    ficha = {"ideia": ideia, "estrategia": estrategia, "arte": arte, "youtube": operador,
             "cenas": formato.get("cenas"), "estilo_pedido": estilo, "voz": cfg["voz"]}
    (pasta / "ficha.json").write_text(json.dumps(ficha, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nCanal '{cfg['nome']}' criado em {pasta} com {len(temas)} temas.")


def montar_cfg(estrategia: dict, formato: dict, arte: dict, voz: str) -> dict:
    nome = estrategia.get("nome") or (estrategia.get("nomes") or ["Canal"])[0]
    pers = arte.get("personagem") or {"modo": "nenhum"}
    if pers.get("modo") not in ("por_video", "fixo", "nenhum"):
        pers["modo"] = "nenhum"
    cenas = []
    for c in formato.get("cenas", []):
        c = {k: v for k, v in c.items() if k in ("tipo", "titulo", "pede")}
        if c.get("titulo"):
            c["titulo"] = c["titulo"].upper()[:18]
        cenas.append(c)
    fim = formato.get("fim") or {}
    fim.setdefault("chamada_tela", "CURTA  •  SIGA  •  COMENTE")
    return {
        "nome": nome, "ativo": False, "handle": (estrategia.get("handles") or [""])[0],
        "descricao_curta": estrategia.get("slogan", ""),
        "rotulo_tema": formato.get("rotulo_tema", "Tema"),
        "contexto": formato.get("contexto", ""), "publico": estrategia.get("publico", ""),
        "tom": formato.get("tom", ""), "regras_extra": formato.get("regras_extra", ""),
        "estilo_imagem": arte.get("estilo_imagem", ""), "personagem": pers,
        "cenas": cenas,
        "conferencia": {"passadas": 3, "contexto": formato.get("conferencia", "")},
        "fim": fim, "plugins": [], "campos_fila": ["tema"],
        "voz": VOZES.get(voz, voz or VOZES[""]), "provedor_voz": "google", "shorts_por_dia": 1,
        "cloudflare": "", "cores": arte.get("cores") or {},
        "marca": {"perfil": arte.get("perfil", ""), "capa": arte.get("capa", "")},
        "youtube": {"tags_base": formato.get("tags_base", [])[:5], "rodape": formato.get("rodape", "")},
        "telegram": "",
    }


def mais_temas(ident: str, n: int):
    from canal import Canal
    canal = Canal(ident)
    cab, fila = canal.ler_fila()
    feitos = [f.get("tema", "") for f in canal.ler_estado().get("feitas", [])]
    r = pedir_json("Você sugere temas de Shorts. Devolva SOMENTE um JSON: {\"temas\": [\"...\"]}",
                   f"Canal: {canal.nome}\n{canal['contexto']}\nJá feitos ou na fila (não repita):\n"
                   + "\n".join(feitos + fila) + f"\n\nSugira {n} temas novos, até 40 caracteres cada.")
    novos = [t.strip().replace("|", "-") for t in (r or {}).get("temas", []) if t.strip()]
    canal.salvar_fila(cab, fila + novos)
    print(f"{len(novos)} temas novos na fila de {canal.nome}.")


def main():
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("--canal", required=True)
    ap.add_argument("--ideia", default="")
    ap.add_argument("--estilo", default="")
    ap.add_argument("--voz", default="")
    ap.add_argument("--publico", default="")
    ap.add_argument("--mais-temas", type=int, default=0)
    a = ap.parse_args()
    if a.mais_temas:
        mais_temas(a.canal, a.mais_temas)
    else:
        criar(a.canal, a.ideia, a.estilo, a.voz, a.publico)


if __name__ == "__main__":
    os.chdir(RAIZ)
    main()
