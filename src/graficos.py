"""Painel de gráficos do monitor."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# Paleta categórica validada (ordem fixa) e tokens de texto/superfície
AZUL, LARANJA, VERDE_AGUA = "#2a78d6", "#eb6834", "#1baf7a"
TEXTO, TEXTO_2, GRADE, SUPERFICIE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
FAIXA = "#dcdad3"

plt.rcParams.update(
    {
        "figure.facecolor": SUPERFICIE,
        "axes.facecolor": SUPERFICIE,
        "axes.edgecolor": GRADE,
        "axes.labelcolor": TEXTO_2,
        "axes.titlecolor": TEXTO,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": GRADE,
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "xtick.color": TEXTO_2,
        "ytick.color": TEXTO_2,
        "font.size": 10,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "lines.linewidth": 2,
    }
)


def _rotulo_final(ax, serie: pd.Series, cor: str, fmt: str = "{:.1f}") -> None:
    """Marca e rótulo no último ponto (rótulo seletivo, em tinta de texto)."""
    s = serie.dropna()
    if s.empty:
        return
    ax.plot(s.index[-1], s.iloc[-1], "o", color=cor, ms=6, mec=SUPERFICIE, mew=2, zorder=5)
    ax.annotate(
        fmt.format(s.iloc[-1]),
        (s.index[-1], s.iloc[-1]),
        xytext=(6, 0),
        textcoords="offset points",
        va="center",
        fontsize=9,
        color=TEXTO,
    )


def painel(base: pd.DataFrame, r_neutro: float, destino: Path, inicio: str = "2005-01") -> None:
    b = base.loc[inicio:]
    fig, eixos = plt.subplots(2, 2, figsize=(13, 8.5), constrained_layout=True)
    ultimo = b["selic"].dropna().index[-1].strftime("%m/%Y")
    fig.suptitle(
        f"Monitor macro Brasil · dados até {ultimo}",
        x=0.01, ha="left", fontsize=15, fontweight="bold", color=TEXTO,
    )

    # 1. Selic x regras de Taylor
    ax = eixos[0, 0]
    ax.plot(b.index, b["selic"], color=AZUL, label="Selic efetiva")
    ax.plot(b.index, b["taylor_calibrada"], color=LARANJA, label="Taylor (1993) calibrada")
    ax.plot(b.index, b["taylor_estimada"], color=VERDE_AGUA, label="Regra estimada (alvo)")
    _rotulo_final(ax, b["selic"], AZUL)
    ax.set_title("Selic e regras de Taylor (% a.a.)")
    ax.legend(loc="best")

    # 2. Inflação x meta
    ax = eixos[0, 1]
    ax.fill_between(
        b.index, b["meta"] - b["tolerancia"], b["meta"] + b["tolerancia"],
        color=FAIXA, step="post", lw=0, label="Intervalo de tolerância",
    )
    ax.step(b.index, b["meta"], where="post", color=TEXTO_2, lw=1.2, ls="--", label="Meta (CMN)")
    ax.plot(b.index, b["ipca_12m"], color=AZUL, label="IPCA 12 meses")
    ax.plot(b.index, b["focus_12m"], color=LARANJA, label="Expectativa Focus 12m")
    _rotulo_final(ax, b["ipca_12m"], AZUL)
    ax.set_title("Inflação, expectativas e meta (%)")
    ax.legend(loc="best")

    # 3. Hiato do produto
    ax = eixos[1, 0]
    h = b["hiato"]
    ax.axhline(0, color=TEXTO_2, lw=1)
    ax.fill_between(h.index, 0, h, where=h >= 0, color=AZUL, alpha=0.25, lw=0, interpolate=True)
    ax.fill_between(h.index, 0, h, where=h < 0, color=LARANJA, alpha=0.25, lw=0, interpolate=True)
    ax.plot(h.index, h, color=TEXTO_2, lw=1.5)
    _rotulo_final(ax, h, TEXTO_2)
    ax.set_title("Hiato do produto · IBC-Br, filtro HP unilateral (%)")
    ax.text(0.01, 0.97, "acima do potencial", transform=ax.transAxes, va="top",
            fontsize=9, color=TEXTO_2)
    ax.text(0.01, 0.03, "abaixo do potencial", transform=ax.transAxes, va="bottom",
            fontsize=9, color=TEXTO_2)

    # 4. Juro real ex-ante
    ax = eixos[1, 1]
    real = ((1 + b["selic"] / 100) / (1 + b["focus_12m"] / 100) - 1) * 100
    ax.plot(real.index, real, color=AZUL, label="Selic real ex-ante")
    ax.axhline(r_neutro, color=LARANJA, lw=2, ls="--", label=f"Juro neutro estimado ({r_neutro:.1f}%)")
    _rotulo_final(ax, real, AZUL)
    ax.set_title("Juro real ex-ante: Selic deflacionada pelo Focus (% a.a.)")
    ax.legend(loc="best")

    fig.text(
        0.01, -0.01,
        "Fontes: BCB (SGS e Focus), CMN. Elaboração: Pedro Vilela Ramos.",
        fontsize=8, color=TEXTO_2,
    )
    fig.savefig(destino, dpi=150, bbox_inches="tight")
    plt.close(fig)
