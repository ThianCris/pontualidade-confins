# Medidas DAX — Pontualidade em Confins

Todas as medidas ficam na tabela `voos_confins`.
Ordem de criação importa: as medidas base vêm antes das que as referenciam.

---

## Tabela de calendário

```dax
Calendario =
ADDCOLUMNS(
    CALENDAR(DATE(2026,1,1), DATE(2026,8,31)),
    "Ano",    YEAR([Date]),
    "MesNum", MONTH([Date]),
    "Mes",    FORMAT([Date], "mmm", "pt-BR"),
    "AnoMes", FORMAT([Date], "yyyy-mm")
)
```

Depois de criar:
1. **Marcar como tabela de data** usando a coluna `Date`.
2. Relacionar `Calendario[Date]` (1) → `voos_confins[Data]` (*), direção única.
3. Em `Mes`, usar **Classificar por coluna** → `MesNum`.

---

## Coluna calculada

```dax
Faixa Ordem =
SWITCH(TRUE(),
    voos_confins[Hora_Prevista] < 6,  1,
    voos_confins[Hora_Prevista] < 12, 2,
    voos_confins[Hora_Prevista] < 18, 3,
    4
)
```

Usar em `Faixa_Horario` → **Classificar por coluna** → `Faixa Ordem`.

---

## 1. Medidas base

```dax
Total Voos = COUNTROWS(voos_confins)
```
Formato: número inteiro, separador de milhar. **Valor esperado: 74.732**

```dax
Voos Medidos =
CALCULATE(
    [Total Voos],
    voos_confins[Cancelado] = FALSE(),
    voos_confins[Sem_Horario_Previsto] = FALSE()
)
```
Denominador de toda a pontualidade. **Valor esperado: 71.901**

```dax
Voos Pontuais = CALCULATE([Total Voos], voos_confins[Pontual] = TRUE())
```
**Valor esperado: 65.955**

```dax
Voos Pontuais 15min = CALCULATE([Total Voos], voos_confins[Pontual_15min] = TRUE())
```

```dax
Voos Cancelados = CALCULATE([Total Voos], voos_confins[Cancelado] = TRUE())
```
**Valor esperado: 1.256**

---

## 2. Indicadores

```dax
% Pontualidade = DIVIDE([Voos Pontuais], [Voos Medidos])
```
Formato: porcentagem, 1 casa decimal. **Valor esperado: 91,7%**

```dax
% Pontualidade 15min = DIVIDE([Voos Pontuais 15min], [Voos Medidos])
```
Formato: porcentagem, 1 casa decimal. **Valor esperado: 85,2%**

```dax
% Cancelamento = DIVIDE([Voos Cancelados], [Total Voos])
```
Formato: porcentagem, 1 casa decimal. **Valor esperado: 1,7%**

> Denominador é `Total Voos`, não `Voos Medidos`: cancelamento é proporção sobre
> tudo o que foi programado.

```dax
Atraso Medio (min) = AVERAGE(voos_confins[Atraso_Min])
```
Formato: número decimal, 1 casa. **Valor esperado: 3,8**

> Não é porcentagem. Se o Power BI herdar o formato de outra medida, corrigir em
> Ferramentas de medida → Formato.

---

## 3. Comparação com o mês anterior

```dax
% Pontualidade Mes Anterior =
CALCULATE([% Pontualidade], DATEADD(Calendario[Date], -1, MONTH))
```
Formato: porcentagem, 1 casa decimal.

```dax
Variacao Pontualidade (p.p.) =
VAR atual    = [% Pontualidade]
VAR anterior = [% Pontualidade Mes Anterior]
RETURN IF(ISBLANK(anterior), BLANK(), (atual - anterior) * 100)
```
Formato personalizado: `+0,0;-0,0;0,0`

Resultado em **pontos percentuais**. Valores esperados por mês:

| Mês | fev | mar | abr | mai | jun | jul | ago |
|---|---|---|---|---|---|---|---|
| Variação | −1,1 | +1,4 | −0,4 | +3,3 | −2,4 | +2,3 | −1,1 |

```dax
% Cancelamento Mes Anterior =
CALCULATE([% Cancelamento], DATEADD(Calendario[Date], -1, MONTH))
```

---

## 4. Benchmark por companhia

```dax
Pontualidade Geral (todas as cias) =
CALCULATE([% Pontualidade], ALL(voos_confins[Companhia]))
```
**Valor esperado: 91,7%**

> `ALL` remove só o filtro de companhia. Os filtros de mês, movimento e tipo de voo
> continuam valendo, então o benchmark acompanha o contexto da página.

```dax
Diferenca vs Geral (p.p.) =
([% Pontualidade] - [Pontualidade Geral (todas as cias)]) * 100
```
Formato personalizado: `+0,0;-0,0;0,0`

| Companhia | Diferença |
|---|---|
| Copa | +5,3 |
| Gol | +1,7 |
| Azul | +0,2 |
| LATAM | −1,7 |
| Azul Conecta | −4,0 |
| TAP | −6,6 |

```dax
Amostra Suficiente = IF([Voos Medidos] >= 150, 1, 0)
```

Usar como **filtro de visual** (`é maior ou igual a 1`) no gráfico por companhia,
para não publicar percentual apoiado em amostra pequena.

---

## 5. Medidas de texto para cartões

Só são necessárias se o visual de cartão abreviar os números ("75 mil" em vez de
"74.732") e a opção de unidade de exibição não estiver disponível na versão
instalada.

```dax
Total Voos (cartao)     = FORMAT([Total Voos],     "#,0", "pt-BR")
Voos Medidos (cartao)   = FORMAT([Voos Medidos],   "#,0", "pt-BR")
Voos Pontuais (cartao)  = FORMAT([Voos Pontuais],  "#,0", "pt-BR")
Voos Cancelados (cartao)= FORMAT([Voos Cancelados],"#,0", "pt-BR")
```

> Retornam **texto**, não número: não servem para gráficos nem para cálculos, só
> para exibição em cartão. No visual, renomear o campo para "Total de voos" para
> que o rótulo interno não apareça na tela.

---

## Conferência rápida

Com nenhum filtro aplicado, a página deve mostrar:

| Medida | Valor |
|---|---|
| Total Voos | 74.732 |
| Voos Medidos | 71.901 |
| Voos Cancelados | 1.256 |
| Voos Pontuais | 65.955 |
| % Pontualidade | 91,7% |
| % Pontualidade 15min | 85,2% |
| % Cancelamento | 1,7% |
| Atraso Medio (min) | 3,8 |

Se algum valor divergir, conferir primeiro o relacionamento `Calendario[Date]` →
`voos_confins[Data]` e o tipo da coluna `Atraso_Min` (deve ser número inteiro).
