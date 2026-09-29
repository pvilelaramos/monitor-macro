"""Coleta de dados: SGS e Focus (Olinda), ambos do Banco Central do Brasil.

Todas as séries saem em frequência mensal, indexadas pelo primeiro dia do mês.
"""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path

from urllib.parse import quote

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]

# Códigos do SGS (https://www3.bcb.gov.br/sgspub)
SERIES_SGS = {
    "selic": 4189,     # Selic acumulada no mês, anualizada base 252 (% a.a.)
    "ipca_mensal": 433,  # IPCA, variação mensal (%)
    "ipca_12m": 13522,   # IPCA acumulado em 12 meses (%)
    "ibcbr": 24364,      # IBC-Br com ajuste sazonal (índice)
    "cambio": 1,         # R$/US$ PTAX venda, diária (vira média do mês)
}

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
URL_FOCUS = (
    "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
    "ExpectativasMercadoInflacao12Meses"
)
INICIO = date(2000, 1, 1)
# Algumas APIs do governo recusam requisições sem User-Agent de navegador
CABECALHOS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
}


def _get(url: str, params: dict, tentativas: int = 6):
    """GET que devolve o JSON já lido, com novas tentativas.

    A API do BCB às vezes responde 5xx ou uma página de erro com status 200;
    nos dois casos esperamos e tentamos de novo.
    """
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params or None, headers=CABECALHOS, timeout=60)
            r.raise_for_status()
            return r.json() if r.text.strip() else []
        except (requests.RequestException, ValueError) as erro:
            print(f"  tentativa {i + 1}/{tentativas} falhou: {str(erro)[:150]}", flush=True)
            if i == tentativas - 1:
                raise
            time.sleep(10 * (i + 1))
    raise RuntimeError("inalcançável")


def baixar_sgs(codigo: int, inicio: date = INICIO, fim: date | None = None) -> pd.Series:
    """Baixa uma série do SGS em janelas de até 10 anos (limite atual da API)."""
    fim = fim or date.today()
    partes = []
    ini = inicio
    while ini <= fim:
        fim_janela = min(date(ini.year + 9, 12, 31), fim)
        dados = _get(
            URL_SGS.format(codigo=codigo),
            {
                "formato": "json",
                "dataInicial": ini.strftime("%d/%m/%Y"),
                "dataFinal": fim_janela.strftime("%d/%m/%Y"),
            },
        )
        if dados:
            partes.append(pd.DataFrame(dados))
        ini = date(fim_janela.year + 1, 1, 1)
    df = pd.concat(partes, ignore_index=True)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    s = df.drop_duplicates("data").set_index("data")["valor"].sort_index()
    return s.resample("MS").mean()


def baixar_focus_12m() -> pd.Series:
    """Mediana da expectativa de IPCA 12 meses à frente (suavizada), média mensal."""
    # OData exige espaços como %20 (o requests usaria "+"), então a URL é montada aqui
    filtro = quote("Indicador eq 'IPCA' and Suavizada eq 'S'")
    url = f"{URL_FOCUS}?$filter={filtro}&$format=json&$top=100000"
    df = pd.DataFrame(_get(url, {})["value"])
    if "baseCalculo" in df.columns:
        df = df[df["baseCalculo"] == 0]
    df["Data"] = pd.to_datetime(df["Data"])
    return df.groupby("Data")["Mediana"].mean().sort_index().resample("MS").mean()


def metas_mensais(indice: pd.DatetimeIndex) -> pd.DataFrame:
    """Meta de inflação do CMN e limites de tolerância, repetidos em cada mês do ano."""
    metas = pd.read_csv(RAIZ / "data" / "metas_inflacao.csv", comment="#")
    metas = metas.set_index("ano")
    anos = indice.year
    ultimo = metas.index.max()
    anos_ok = [min(a, ultimo) for a in anos]  # anos futuros herdam a última meta
    out = pd.DataFrame(index=indice)
    out["meta"] = metas.loc[anos_ok, "meta"].to_numpy()
    out["tolerancia"] = metas.loc[anos_ok, "tolerancia"].to_numpy()
    return out


def montar_base() -> pd.DataFrame:
    """Baixa tudo e devolve a base mensal usada pelos modelos."""
    series = {}
    for nome, cod in SERIES_SGS.items():
        print(f"SGS {cod} ({nome})...", flush=True)
        series[nome] = baixar_sgs(cod)
    print("Focus (expectativa IPCA 12m)...", flush=True)
    series["focus_12m"] = baixar_focus_12m()
    base = pd.DataFrame(series)
    base = base.join(metas_mensais(base.index))
    base.index.name = "data"
    return base


if __name__ == "__main__":
    base = montar_base()
    destino = RAIZ / "data" / "processado" / "base_mensal.csv"
    base.to_csv(destino, float_format="%.4f")
    print(f"{len(base)} meses salvos em {destino}")
