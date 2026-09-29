"""Modelos: hiato do produto, regra de Taylor e curva de Phillips."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.filters.hp_filter import hpfilter

LAMBDA_MENSAL = 129_600  # Ravn & Uhlig (2002) para dados mensais


# ---------------------------------------------------------------- hiato
def hiato_hp(ibc: pd.Series, unilateral: bool = True, min_obs: int = 36) -> pd.Series:
    """Hiato do produto (% do potencial) a partir do log do IBC-Br.

    unilateral=True usa, em cada mês, apenas os dados disponíveis até aquele mês
    (filtro HP recursivo). É o que um analista veria em tempo real e evita que a
    regra de Taylor "enxergue o futuro". O filtro bilateral é mais suave, mas
    revisa o passado toda vez que chega um dado novo.
    """
    y = 100 * np.log(ibc.dropna())
    if not unilateral:
        ciclo, _ = hpfilter(y, lamb=LAMBDA_MENSAL)
        return ciclo.rename("hiato")
    valores = {}
    for t in range(min_obs, len(y) + 1):
        ciclo, _ = hpfilter(y.iloc[:t], lamb=LAMBDA_MENSAL)
        valores[y.index[t - 1]] = ciclo.iloc[-1]
    return pd.Series(valores, name="hiato")


# ---------------------------------------------------------------- Taylor
@dataclass
class ResultadoTaylor:
    modelo: sm.regression.linear_model.RegressionResultsWrapper
    rho: float
    phi_pi: float
    phi_y: float
    juro_real_neutro: float
    amostra: tuple[str, str]


def taylor_calibrada(base: pd.DataFrame, r_neutro: float = 5.0) -> pd.Series:
    """Regra de Taylor (1993) com expectativas: i = r* + Eπ + 0,5(Eπ − π*) + 0,5·hiato."""
    e = base["focus_12m"]
    return (r_neutro + e + 0.5 * (e - base["meta"]) + 0.5 * base["hiato"]).rename(
        "taylor_calibrada"
    )


def estimar_taylor(base: pd.DataFrame, inicio: str = "2003-07") -> ResultadoTaylor:
    """Regra com suavização, estimada por MQO com erros HAC (Newey-West).

    i_t = c + ρ·i_{t-1} + a·π*_t + b·(Eπ_t − π*_t) + d·hiato_t + ε_t

    Coeficientes de longo prazo: φπ = b/(1−ρ) (resposta ao desvio das expectativas),
    φy = d/(1−ρ). Com a/(1−ρ) ≈ 1, o juro real neutro implícito é c/(1−ρ).
    """
    df = pd.DataFrame(
        {
            "i": base["selic"],
            "i_lag": base["selic"].shift(1),
            "meta": base["meta"],
            "desvio_expect": base["focus_12m"] - base["meta"],
            "hiato": base["hiato"],
        }
    ).loc[inicio:].dropna()
    X = sm.add_constant(df[["i_lag", "meta", "desvio_expect", "hiato"]])
    mod = sm.OLS(df["i"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 12})
    p = mod.params
    um_menos_rho = 1 - p["i_lag"]
    return ResultadoTaylor(
        modelo=mod,
        rho=p["i_lag"],
        phi_pi=p["desvio_expect"] / um_menos_rho,
        phi_y=p["hiato"] / um_menos_rho,
        juro_real_neutro=p["const"] / um_menos_rho,
        amostra=(df.index[0].strftime("%Y-%m"), df.index[-1].strftime("%Y-%m")),
    )


def taylor_estimada(base: pd.DataFrame, res: ResultadoTaylor) -> pd.Series:
    """Taxa "desejada" pela regra estimada (sem a inércia): o alvo de longo prazo."""
    p = res.modelo.params
    alvo = (
        p["const"]
        + p["meta"] * base["meta"]
        + p["desvio_expect"] * (base["focus_12m"] - base["meta"])
        + p["hiato"] * base["hiato"]
    ) / (1 - p["i_lag"])
    return alvo.rename("taylor_estimada")


# ---------------------------------------------------------------- Phillips
def _para_trimestral(base: pd.DataFrame) -> pd.DataFrame:
    """Agrega a base mensal em trimestres."""
    fator = 1 + base["ipca_mensal"] / 100
    q = pd.DataFrame(
        {
            "inflacao": (fator.resample("QS").prod() - 1) * 100,
            "n_meses": fator.resample("QS").count(),
            "hiato": base["hiato"].resample("QS").mean(),
            "cambio": base["cambio"].resample("QS").mean(),
            # Expectativa formada no último mês do trimestre anterior,
            # convertida de 12 meses para um trimestre.
            "expect": ((1 + base["focus_12m"] / 100) ** 0.25 - 1)
            .mul(100)
            .resample("QS")
            .last()
            .shift(1),
        }
    )
    return q[q["n_meses"] == 3].drop(columns="n_meses")


@dataclass
class ResultadoPhillips:
    modelo: sm.regression.linear_model.RegressionResultsWrapper
    amostra: tuple[str, str]


def estimar_phillips(base: pd.DataFrame, inicio: str = "2003-07") -> ResultadoPhillips:
    """Curva de Phillips híbrida, trimestral, com dummies sazonais:

    π_t = c + βf·Eπ_t + βb·π_{t-1} + γ·hiato_{t-1} + δ·Δcâmbio_{t-1} + sazonais + ε_t

    Inspirada nas curvas dos modelos semiestruturais do BCB (Relatório de Inflação).
    """
    q = _para_trimestral(base)
    df = pd.DataFrame(
        {
            "inflacao": q["inflacao"],
            "expectativa": q["expect"],
            "inflacao_lag": q["inflacao"].shift(1),
            "hiato_lag": q["hiato"].shift(1),
            "cambio_lag": (100 * np.log(q["cambio"])).diff().shift(1),
        }
    ).loc[inicio:]
    sazonais = pd.get_dummies(df.index.quarter, prefix="T", drop_first=True, dtype=float)
    sazonais.index = df.index
    df = df.join(sazonais).dropna()
    X = sm.add_constant(df.drop(columns="inflacao"))
    mod = sm.OLS(df["inflacao"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    return ResultadoPhillips(
        modelo=mod,
        amostra=(str(df.index[0].to_period("Q")), str(df.index[-1].to_period("Q"))),
    )
