"""Roda o monitor de ponta a ponta: dados → modelos → gráfico → relatório.

Uso:
    python src/atualizar.py            # baixa os dados do BCB
    python src/atualizar.py --offline  # usa data/processado/base_mensal.csv
"""
from __future__ import annotations

import argparse

import pandas as pd

import dados
import graficos
import modelos
import relatorio

RAIZ = dados.RAIZ
BASE_CSV = RAIZ / "data" / "processado" / "base_mensal.csv"
# Juro real neutro de referência (% a.a.), próximo das estimativas recentes do BCB
R_NEUTRO = 5.0


def rodar(base: pd.DataFrame) -> pd.DataFrame:
    base = base.copy()
    base["hiato"] = modelos.hiato_hp(base["ibcbr"], unilateral=True)
    taylor = modelos.estimar_taylor(base)
    phillips = modelos.estimar_phillips(base)
    base["taylor_calibrada"] = modelos.taylor_calibrada(base, r_neutro=R_NEUTRO)
    base["taylor_estimada"] = modelos.taylor_estimada(base, taylor)

    (RAIZ / "figures").mkdir(exist_ok=True)
    graficos.painel(base, R_NEUTRO, RAIZ / "figures" / "painel.png")
    relatorio.gerar(base, taylor, phillips, RAIZ / "relatorio.md")
    base.to_csv(RAIZ / "data" / "processado" / "resultados_mensais.csv", float_format="%.4f")
    print(taylor.modelo.summary())
    print(phillips.modelo.summary())
    return base


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--offline", action="store_true", help="não baixa, usa o CSV salvo")
    args = p.parse_args()
    if args.offline:
        base = pd.read_csv(BASE_CSV, index_col="data", parse_dates=True)
    else:
        try:
            base = dados.montar_base()
            BASE_CSV.parent.mkdir(parents=True, exist_ok=True)
            base.to_csv(BASE_CSV, float_format="%.4f")
        except Exception as erro:  # noqa: BLE001
            if not BASE_CSV.exists():
                raise
            print(f"AVISO: coleta falhou ({erro}); usando a última base salva.", flush=True)
            base = pd.read_csv(BASE_CSV, index_col="data", parse_dates=True)
    rodar(base)


if __name__ == "__main__":
    main()
