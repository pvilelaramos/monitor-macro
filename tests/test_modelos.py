"""Testes com dados simulados: os estimadores recuperam parâmetros conhecidos?

Rodar com:  python -m pytest tests/
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import modelos  # noqa: E402


def base_simulada(n: int = 300, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2001-01-01", periods=n, freq="MS")
    meta = np.where(idx.year < 2019, 4.5, 3.5)
    hiato = np.zeros(n)
    expect = np.zeros(n)
    for t in range(1, n):
        hiato[t] = 0.9 * hiato[t - 1] + rng.normal(0, 0.6)
        expect[t] = meta[t] + 0.85 * (expect[t - 1] - meta[t - 1]) + rng.normal(0, 0.3)
    # Regra verdadeira: rho=0.9, r*=5, phi_pi=2, phi_y=0.5
    i = np.zeros(n)
    i[0] = 10
    for t in range(1, n):
        alvo = 5 + meta[t] + 2.0 * (expect[t] - meta[t]) + 0.5 * hiato[t]
        i[t] = 0.9 * i[t - 1] + 0.1 * alvo + rng.normal(0, 0.15)
    ibc = 100 * np.exp(np.cumsum(np.full(n, 0.002)) + hiato / 100)
    ipca_m = 0.35 + 0.1 * np.sin(np.arange(n)) + rng.normal(0, 0.15, n)
    return pd.DataFrame(
        {
            "selic": i,
            "ipca_mensal": ipca_m,
            "ipca_12m": pd.Series(ipca_m).rolling(12).sum().to_numpy(),
            "ibcbr": ibc,
            "cambio": 3 * np.exp(np.cumsum(rng.normal(0, 0.02, n))),
            "focus_12m": expect,
            "meta": meta,
            "tolerancia": 1.5,
            "hiato": hiato,
        },
        index=pd.DatetimeIndex(idx, name="data"),
    )


def test_taylor_recupera_parametros():
    base = base_simulada(n=600)
    res = modelos.estimar_taylor(base, inicio="2001-02")
    assert abs(res.rho - 0.9) < 0.05
    assert abs(res.phi_pi - 2.0) < 0.6
    assert abs(res.phi_y - 0.5) < 0.3


def test_hiato_unilateral_so_usa_passado():
    base = base_simulada()
    h_total = modelos.hiato_hp(base["ibcbr"])
    h_cortado = modelos.hiato_hp(base["ibcbr"].iloc[:200])
    # O hiato até o mês 200 não pode mudar quando chegam dados novos
    pd.testing.assert_series_equal(h_total.iloc[: len(h_cortado)], h_cortado)


def test_phillips_roda():
    res = modelos.estimar_phillips(base_simulada())
    assert "expectativa" in res.modelo.params
