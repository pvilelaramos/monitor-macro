"""Coleta de dados: SGS e Focus (Olinda), ambos do Banco Central do Brasil.

Todas as séries saem em frequência mensal, indexadas pelo primeiro dia do mês.
"""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]

# Códigos do SGS (https://www3.bcb.gov.br/sgspub)
SERIES_SGS = {
    "selic": 4189,     # Selic acumulada no mês, anualizada base 252 (% a.a.)
    "ipca_mensal": 433,  # IPCA, variação mensal (%)
    "ipca_12m": 13522,   # IPCA acumulado em 12 meses (%)
    "ibcbr": 24364,      # IBC-Br com ajuste sazonal (índice)
    "cambio": 3698,      # R$/US$ PTAX venda, média do mês
}

URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
URL_FOCUS = (
    "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
    "ExpectativasMercadoInflacao12Meses"
)
INICIO = date(2000, 1, 1)


def _get(url: str, params: dict, tentativas: int = 4) -> requests.Response:
    """GET com novas tentativas: a API do BCB às vezes devolve erro passageiro."""
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == tentativas - 1:
                raise
            time.sleep(5 * (i + 1))
    raise RuntimeError("inalcançável")


def baixar_sgs(codigo: int, inicio: date = INICIO, fim: date | None = None) -> pd.Series:
    """Baixa uma série do SGS em janelas de até 10 anos (limite atual da API)."""
    fim = fim or date.today()
    partes = []
    ini = inicio
    while ini <= fim:
        fim_janela = min(date(ini.year + 9, 12, 31), fim)
        r = _get(
            URL_SGS.format(codigo=codigo),
            {
                "formato": "json",
                "dataInicial": ini.strftime("%d/%m/%Y"),
                "dataFinal": fim_janela.strftime("%d/%m/%Y"),
            },
        )
        dados = r.json()
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
    r = _get(
        URL_FOCUS,
        {
            "$filter": "Indicador eq 'IPCA' and Suavizada eq 'S' and baseCalculo eq 0",
            "$select": "Data,Mediana",
            "$format": "json",
            "$top": 100000,
        },
    )
    df = pd.DataFrame(r.json()["value"])
    df["Data"] = pd.to_datetime(df["Data"])
    return df.set_index("Data")["Mediana"].sort_index().resample("MS").mean()


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
    series = {nome: baixar_sgs(cod) for nome, cod in SERIES_SGS.items()}
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
