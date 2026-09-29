"""Gera o relatório em Markdown com os últimos números e as estimações."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from modelos import ResultadoPhillips, ResultadoTaylor

NOMES = {
    "const": "Constante",
    "i_lag": "Selic defasada − meta (ρ)",
    "meta": "Meta de inflação",
    "desvio_expect": "Expectativa − meta",
    "hiato": "Hiato",
    "expectativa": "Expectativa (βf)",
    "inflacao_lag": "Inflação defasada (βb)",
    "hiato_lag": "Hiato defasado (γ)",
    "cambio_lag": "Δ câmbio defasado (δ)",
}


def _tabela_coef(modelo) -> str:
    linhas = ["| Variável | Coeficiente | Erro-padrão (HAC) | p-valor |", "|---|---:|---:|---:|"]
    for nome in modelo.params.index:
        if nome.startswith("T_"):
            continue
        linhas.append(
            f"| {NOMES.get(nome, nome)} | {modelo.params[nome]:.3f} | "
            f"{modelo.bse[nome]:.3f} | {modelo.pvalues[nome]:.3f} |"
        )
    linhas.append(f"\nR² = {modelo.rsquared:.3f} · N = {int(modelo.nobs)}")
    return "\n".join(linhas)


def _ultimo(s: pd.Series) -> tuple[str, str]:
    s = s.dropna()
    return (f"{s.iloc[-1]:.2f}", s.index[-1].strftime("%m/%Y")) if len(s) else ("–", "–")


def gerar(base: pd.DataFrame, taylor: ResultadoTaylor, phillips: ResultadoPhillips,
          destino: Path) -> None:
    real = ((1 + base["selic"] / 100) / (1 + base["focus_12m"] / 100) - 1) * 100
    indicadores = [
        ("Selic efetiva (% a.a.)", base["selic"]),
        ("IPCA 12 meses (%)", base["ipca_12m"]),
        ("Expectativa Focus 12m (%)", base["focus_12m"]),
        ("Meta de inflação (%)", base["meta"]),
        ("Hiato do produto (%)", base["hiato"]),
        ("Juro real ex-ante (% a.a.)", real),
        ("Regra de Taylor, r* = 5% (% a.a.)", base["taylor_calibrada"]),
        ("Regra estimada, alvo (% a.a.)", base["taylor_estimada"]),
        ("Selic − regra de Taylor (p.p.)", base["selic"] - base["taylor_calibrada"]),
    ]
    tab = ["| Indicador | Valor | Referência |", "|---|---:|---:|"]
    for nome, s in indicadores:
        v, d = _ultimo(s)
        tab.append(f"| {nome} | {v} | {d} |")

    texto = f"""# Relatório do monitor macro

*Gerado automaticamente em {date.today():%d/%m/%Y}.*

![Painel](figures/painel.png)

## Últimos números

{chr(10).join(tab)}

## Regra de Taylor estimada

Amostra mensal {taylor.amostra[0]} a {taylor.amostra[1]}.
$i_t - \\pi^*_t = c + \\rho\\,(i_{{t-1}} - \\pi^*_t) + b\\,(E_t\\pi_{{t+12}} - \\pi^*_t) + d\\,\\tilde y_t + \\varepsilon_t$

(forma linear de $i_t = \\rho\\, i_{{t-1}} + (1-\\rho)[r^* + \\pi^* + \\phi_\\pi(E\\pi - \\pi^*) + \\phi_y \\tilde y]$, com a meta passando 1 para 1 ao juro no longo prazo)

{_tabela_coef(taylor.modelo)}

**Coeficientes de longo prazo**

| Parâmetro | Valor |
|---|---:|
| Suavização ρ | {taylor.rho:.3f} |
| Resposta às expectativas φπ | {taylor.phi_pi:.2f} |
| Resposta ao hiato φy | {taylor.phi_y:.2f} |
| Juro real implícito com Eπ = meta e hiato zero, r* (% a.a.) | {taylor.juro_real_neutro:.2f} |

Leitura: o juro real ex-ante implícito na regra é
$r_t = i_t - E_t\\pi = r^* + (\\phi_\\pi - 1)(E_t\\pi - \\pi^*) + \\phi_y \\tilde y_t$.
O **princípio de Taylor** pede φπ > 1: quando as expectativas sobem, o BC tem de
subir o juro nominal mais que 1 para 1, de modo que o juro **real** também suba.
Estimado aqui: φπ = {taylor.phi_pi:.2f} ({'satisfaz' if taylor.phi_pi > 1 else 'não satisfaz'} o princípio no longo prazo).

Cuidado na leitura: como as expectativas ficaram acima da meta na maior parte
da amostra, φπ e r* são difíceis de separar. Um φπ alto combinado com um r*
baixo descreve o mesmo juro real médio que um φπ menor com um r* mais alto.
Por isso o painel usa a regra calibrada, com r* = 5%, e a regra estimada fica
só neste relatório.

## Curva de Phillips (trimestral)

Amostra {phillips.amostra[0]} a {phillips.amostra[1]}, com dummies sazonais.
$\\pi_t = c + \\beta_f E_t\\pi_{{t+1}} + \\beta_b\\,\\pi_{{t-1}} + \\gamma\\,\\tilde y_{{t-1}} + \\delta\\,\\Delta e_{{t-1}} + \\varepsilon_t$

{_tabela_coef(phillips.modelo)}

Soma βf + βb = {phillips.modelo.params['expectativa'] + phillips.modelo.params['inflacao_lag']:.2f}
(próximo de 1 indica curva vertical no longo prazo).
"""
    destino.write_text(texto, encoding="utf-8")
