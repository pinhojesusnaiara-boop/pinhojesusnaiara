"""Chamada ao Gemini (nível gratuito) com novas tentativas e modelo reserva."""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

MODELO_GEMINI = "gemini-flash-lite-latest"
MODELO_GEMINI_RESERVA = "gemini-flash-latest"


class ErroAPI(Exception):
    pass


def _requisitar(req, extrair, timeout: int = 90, tentativas: int = 4):
    """Envia com novas tentativas em erros passageiros: limite de taxa, servidor ocupado,
    queda de rede e resposta que demora demais."""
    espera = 4
    for tentativa in range(tentativas):
        inicio = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resposta = extrair(json.loads(r.read()))
            print(f"    API respondeu em {time.monotonic() - inicio:.0f} s", flush=True)
            return resposta
        except urllib.error.HTTPError as e:
            corpo = e.read().decode(errors="replace")[:400]
            if e.code in (429, 500, 502, 503, 504, 529) and tentativa < tentativas - 1:
                print(f"    API: erro {e.code}, nova tentativa em {espera} s", flush=True)
                time.sleep(espera)
                espera *= 2
                continue
            raise ErroAPI(f"Erro {e.code} da API: {corpo}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            motivo = getattr(e, "reason", e)
            if tentativa < tentativas - 1:
                print(f"    API: {motivo} após {time.monotonic() - inicio:.0f} s, "
                      f"nova tentativa em {espera} s", flush=True)
                time.sleep(espera)
                espera *= 2
                continue
            raise ErroAPI(f"A API não respondeu: {motivo}") from None
    raise ErroAPI("A API não respondeu.")


def chamar_gemini(mensagens: list, sistema: str, max_tokens: int) -> str:
    """Nível gratuito do Gemini (chave do Google AI Studio, sem cartão).

    Pensamento no nível baixo: para escrever e conferir perguntas de quiz ele não ajuda,
    só deixa a resposta lenta e gasta o limite de tokens. Se o modelo principal falhar,
    tenta o Flash-Lite, que é mais rápido e tem cota gratuita maior.
    """
    chave = os.environ.get("GEMINI_API_KEY")
    if not chave:
        raise ErroAPI("Defina GEMINI_API_KEY no ambiente.")
    modelos = [os.environ.get("GEMINI_MODEL", MODELO_GEMINI), MODELO_GEMINI_RESERVA]
    conteudo = {
        "system_instruction": {"parts": [{"text": sistema}]},
        "contents": [{"role": "user" if m["role"] == "user" else "model",
                      "parts": [{"text": m["content"]}]} for m in mensagens],
    }

    def extrair(dados):
        partes = (dados.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in partes if not p.get("thought"))

    ultimo = None
    for modelo in dict.fromkeys(modelos):
        for com_pensamento_baixo in (True, False):
            config = {"maxOutputTokens": max(max_tokens, 8192), "responseMimeType": "application/json"}
            if com_pensamento_baixo:
                config["thinkingConfig"] = {"thinkingLevel": "low"}
            corpo = json.dumps({**conteudo, "generationConfig": config}).encode()
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                data=corpo, headers={"content-type": "application/json", "x-goog-api-key": chave})
            print(f"    Gemini ({modelo})", flush=True)
            try:
                # Duas tentativas por modelo: se travar, o reserva entra logo em vez de esperar minutos.
                texto = _requisitar(req, extrair, timeout=90, tentativas=2)
                if texto.strip():
                    return texto
                ultimo = ErroAPI(f"{modelo} devolveu resposta vazia")
                break
            except ErroAPI as e:
                ultimo = e
                # 400 por causa do thinkingConfig: tenta o mesmo modelo sem ele.
                if com_pensamento_baixo and "400" in str(e) and "think" in str(e).lower():
                    continue
                break
        print(f"    {modelo} falhou: {ultimo}", flush=True)
    raise ultimo or ErroAPI("Gemini não respondeu.")


def extrair_json(texto: str):
    """O modelo às vezes embrulha a resposta em ``` ou escreve um preâmbulo."""
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    for a, b in ("{}", "[]"):
        i, f = texto.find(a), texto.rfind(b)
        if i != -1 and f > i:
            try:
                return json.loads(texto[i:f + 1])
            except json.JSONDecodeError:
                pass
    return None


# ----------------------------------------------------------------- validação


def pedir_json(sistema: str, pedido: str, max_tokens: int = 8192):
    """Pede ao Gemini e devolve o JSON já interpretado (ou levanta ErroAPI)."""
    texto = chamar_gemini([{"role": "user", "content": pedido}], sistema, max_tokens)
    dados = extrair_json(texto)
    if dados is None:
        raise ErroAPI("O Gemini não devolveu um JSON válido.")
    return dados
