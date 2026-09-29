# Monitor macro Brasil

Painel mensal da política monetária brasileira: **Selic, inflação, expectativas,
hiato do produto e regra de Taylor**, com dados públicos do Banco Central e
atualização automática todo mês.

![Painel](figures/painel.png)

➡️ **Últimos números e estimações: [`relatorio.md`](relatorio.md)**

## Perguntas

1. A Selic está acima ou abaixo do que uma regra de Taylor recomendaria?
2. Como o BCB reagiu, historicamente, às expectativas de inflação e ao hiato?
3. Qual juro real neutro está implícito nessa reação?
4. Quanto da inflação corrente vem de inércia, de expectativas, do hiato e do câmbio?

## Metodologia

| Bloco | Especificação |
|---|---|
| **Hiato do produto** | Log do IBC-Br dessazonalizado, filtro HP (λ = 129.600). Versão **unilateral**: em cada mês, o filtro só usa dados até aquele mês, como um analista em tempo real. |
| **Taylor calibrada** | Taylor (1993) com expectativas: $i = r^* + E\pi + 0{,}5(E\pi - \pi^*) + 0{,}5\,\tilde y$, com $r^* = 5\%$. |
| **Taylor estimada** | $i_t = \rho\, i_{t-1} + (1-\rho)[r^* + \pi^*_t + \phi_\pi(E_t\pi - \pi^*_t) + \phi_y\tilde y_t]$, estimada na forma linear em $(i - \pi^*)$ por MQO com erros HAC (Newey-West). Recupera a suavização ρ, as respostas de longo prazo φπ e φy e o r* implícito. |
| **Curva de Phillips** | Trimestral, híbrida: $\pi_t = c + \beta_f E_t\pi + \beta_b\pi_{t-1} + \gamma\tilde y_{t-1} + \delta\Delta e_{t-1}$ + dummies sazonais. Inspirada nos modelos semiestruturais do BCB. |

### Dados

| Série | Fonte | Código |
|---|---|---|
| Selic acumulada no mês, anualizada | BCB/SGS | 4189 |
| IPCA, variação mensal | BCB/SGS | 433 |
| IPCA, acumulado em 12 meses | BCB/SGS | 13522 |
| IBC-Br dessazonalizado | BCB/SGS | 24364 |
| Câmbio R$/US$ (PTAX venda, média mensal da diária) | BCB/SGS | 1 |
| Expectativa de IPCA 12 meses (mediana, suavizada) | BCB/Focus (Olinda) | – |
| Meta de inflação e tolerância | CMN | [`data/metas_inflacao.csv`](data/metas_inflacao.csv) |

## Como rodar

```bash
pip install -r requirements.txt
python src/atualizar.py            # baixa os dados e atualiza tudo
python src/atualizar.py --offline  # reusa data/processado/base_mensal.csv
python -m pytest tests/            # testes com dados simulados
```

A atualização também roda sozinha: o GitHub Actions
([`.github/workflows/atualizar.yml`](.github/workflows/atualizar.yml)) executa o
pipeline no dia 15 de cada mês e salva os novos resultados no repositório.

## Estrutura

```
├── src/
│   ├── dados.py        # coleta (SGS e Focus)
│   ├── modelos.py      # hiato, Taylor, Phillips
│   ├── graficos.py     # painel
│   ├── relatorio.py    # relatorio.md
│   └── atualizar.py    # roda tudo
├── tests/              # testes com dados simulados
├── data/
│   ├── metas_inflacao.csv
│   └── processado/     # base mensal e resultados
└── figures/
```

## Limitações e próximos passos

- O hiato por filtro HP é uma medida estatística, e o hiato do BCB usa também
  informação de mercado de trabalho e de utilização da capacidade.
- A Selic é usada como taxa de política; uma extensão natural é usar o swap
  DI 360 dias para medir o juro real ex-ante com o prazo casado ao Focus.
- Próximos passos: regra de Taylor com coeficientes variando no tempo
  (janelas móveis), e uma curva de Phillips para preços livres.

## Referências

- Taylor, J. (1993). *Discretion versus policy rules in practice*. Carnegie-Rochester Conference Series.
- Clarida, R., Galí, J. & Gertler, M. (2000). *Monetary policy rules and macroeconomic stability*. QJE.
- Minella, A., de Freitas, P., Goldfajn, I. & Muinhos, M. (2003). *Inflation targeting in Brazil: constructing credibility under exchange rate volatility*. JIMF.
- Ravn, M. & Uhlig, H. (2002). *On adjusting the Hodrick-Prescott filter for the frequency of observations*. REStat.

---

Pedro Vilela Ramos · Economia (IE/UFRJ)
