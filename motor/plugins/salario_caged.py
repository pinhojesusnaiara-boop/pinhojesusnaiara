"""
Plugin para canais de profissões: salário oficial do Novo Caged (via Salario.com.br).
Acrescenta a cena "salario" e completa o gancho e a legenda com os números — nunca vindos da IA.
Fila: "Nome | slug do Salario.com.br | um/uma" (campos_fila: ["nome", "slug", "artigo"]).
"""
from __future__ import annotations

from plugins.salario_caged_dados import reais, salario

TIPO = "salario"


class Plugin:
    def __init__(self, canal):
        self.canal = canal
        self.dados = None

    def antes(self, item: dict) -> str:
        """Busca os dados e devolve texto extra para o pedido do roteiro."""
        self.dados = salario(item["slug"])
        print(f"  salário médio {reais(self.dados['media'])} ({self.dados['periodo']})", flush=True)
        return f"Jornada típica informada pelo Novo Caged: {self.dados.get('jornada') or '?'} horas semanais.\n"

    def completar(self, rot: dict, item: dict):
        sal, nome = self.dados, item.get("nome", item["tema"])
        artigo = item.get("artigo", "um").lower()
        for c in rot["cenas"]:
            if c["tipo"] == "gancho":
                c["titulo"] = f"QUANTO GANHA {artigo.upper()} {nome.upper()}?"
            elif c["tipo"] == TIPO:
                c["titulo"] = "QUANTO GANHA?"
                c["fala"] = (f"Segundo o Novo Caged, {artigo} {nome.lower()} ganha em média "
                             f"{sal['media']:,} reais por mês.".replace(",", ".") + " Você acha justo? Comenta aí.")
        rot["salario"] = sal
        yt = rot["youtube"]
        yt["fontes"] = f"Salário: Novo Caged ({sal.get('periodo')}), CBO {sal.get('cbo')}, via Salario.com.br."
        yt["faixa"] = f"De {reais(sal['piso'])} a {reais(sal['teto'])} (média {reais(sal['media'])})."

    def legenda(self, rot: dict) -> str:
        return f"{rot['youtube']['faixa']}\n{rot['youtube']['fontes']}"

    def duracao_minima(self) -> float:
        return 6.0

    def desenhar(self, m, img, c: dict, tl: float):
        """Contador do salário, faixa piso-teto, chamada para comentar e a fonte."""
        from PIL import ImageDraw
        from montar import fonte
        sal = m.rot["salario"]
        d = ImageDraw.Draw(img)
        m.titulo(d, c["titulo"], 200)
        val = int(sal["media"] * m.suave((tl - 0.4) / 2.2))
        m.cartao(img, (90, 1180, 990, 1540))
        d = ImageDraw.Draw(img)
        d.text((540, 1250), "salário médio mensal", font=fonte("SemiBold", 50), fill=m.PRETO, anchor="mm")
        d.text((540, 1380), reais(val), font=fonte("ExtraBold", 170), fill=m.VALOR, anchor="mm")
        if tl > 2.9:
            d.text((540, 1495), f"de {reais(sal['piso'])} a {reais(sal['teto'])}", font=fonte("SemiBold", 48),
                   fill=m.PRETO, anchor="mm")
        if tl > 3.6:
            m.cartao(img, (90, 1580, 990, 1710), cor=m.DESTAQUE + (245,))
            d = ImageDraw.Draw(img)
            d.text((540, 1645), "Você acha justo? Comenta!", font=fonte("ExtraBold", 62), fill=m.PRETO, anchor="mm")
        cbo = sal.get("cbo", "")
        m.rodape(d, f"Fonte: Novo Caged ({sal.get('periodo')}), CBO {cbo[:4]}-{cbo[4:]}")
