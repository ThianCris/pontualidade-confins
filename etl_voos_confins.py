"""
ETL - Pontualidade de voos no Aeroporto de Confins (SBCF)
Fonte: ANAC - Dados Abertos - Voo Regular Ativo (VRA)

Uso:
    python etl_voos_confins.py <pasta_com_VRA_csv> <saida.csv>
Exemplo:
    python etl_voos_confins.py dados_brutos dados_tratados/voos_confins.csv

O script le todos os arquivos VRA_*.csv da pasta, filtra os voos que saem
ou chegam em Confins e gera uma base limpa, uma linha por voo, pronta para o Power BI.
"""
import sys
import glob
import os
import pandas as pd

AEROPORTO = "SBCF"
LIMITE_PONTUAL_MIN = 30  # criterio da ANAC: "Pontual" = atraso de ate 30 min (conferido contra a coluna Situacao Partida/Chegada)
LIMITE_PONTUAL_15 = 15   # criterio internacional mais rigoroso, guardado em coluna extra

pasta = sys.argv[1] if len(sys.argv) > 1 else "dados_brutos"
saida = sys.argv[2] if len(sys.argv) > 2 else "voos_confins.csv"

DIAS = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}
TIPO_LINHA = {"N": "Nacional", "I": "Internacional", "G": "Regional/Geral", "C": "Cargueiro"}


def companhia(nome):
    """Agrupa os nomes oficiais em nomes curtos para o painel."""
    n = str(nome).upper()
    if "AZUL CONECTA" in n:
        return "Azul Conecta"
    if "AZUL" in n:
        return "Azul"
    if "GOL" in n:
        return "Gol"
    if "TAM " in n or "LATAM" in n or "LAN " in n:
        return "LATAM"
    if "TAP" in n:
        return "TAP"
    if "COPA" in n:
        return "Copa"
    return "Outras"


def faixa_horario(h):
    if h < 6:
        return "Madrugada (0h-6h)"
    if h < 12:
        return "Manhã (6h-12h)"
    if h < 18:
        return "Tarde (12h-18h)"
    return "Noite (18h-24h)"


def faixa_atraso(m):
    if pd.isna(m):
        return None
    if m < 0:
        return "Antecipado"
    if m <= 30:
        return "Pontual (até 30 min)"
    if m <= 60:
        return "Atraso 30-60 min"
    if m <= 120:
        return "Atraso 60-120 min"
    if m <= 240:
        return "Atraso 120-240 min"
    return "Atraso > 240 min"


# 1) Leitura e empilhamento -------------------------------------------------
arquivos = sorted(glob.glob(os.path.join(pasta, "VRA_*.csv")))
if not arquivos:
    sys.exit(f"Nenhum arquivo VRA_*.csv encontrado em: {pasta}")

partes = []
for f in arquivos:
    d = pd.read_csv(f, sep=";", encoding="utf-8-sig", dtype=str)
    d = d[(d["Sigla ICAO Aeroporto Origem"] == AEROPORTO) | (d["Sigla ICAO Aeroporto Destino"] == AEROPORTO)]
    d["Arquivo_Origem"] = os.path.basename(f)
    partes.append(d)
    print(f"{os.path.basename(f)}: {len(d)} voos em {AEROPORTO}")
df = pd.concat(partes, ignore_index=True)
total_lido = len(df)

# 2) Duplicatas exatas (mesma linha repetida) ---------------------------------
df = df.drop_duplicates(subset=[c for c in df.columns if c != "Arquivo_Origem"])
duplicadas = total_lido - len(df)

# 3) Datas ------------------------------------------------------------------
for c in ["Partida Prevista", "Partida Real", "Chegada Prevista", "Chegada Real"]:
    df[c] = pd.to_datetime(df[c], format="%d/%m/%Y %H:%M", errors="coerce")
# "Referencia" = data operacional do voo segundo a ANAC (sempre preenchida e dentro do mes do arquivo)
df["Referência"] = pd.to_datetime(df["Referência"], format="%d/%m/%Y %H:%M:%S", errors="coerce")

# 4) Movimento em Confins: decolagem (origem SBCF) ou pouso (destino SBCF) ---
# Voos entre SBCF e SBCF nao existem; origem tem prioridade por seguranca.
decola = df["Sigla ICAO Aeroporto Origem"] == AEROPORTO
df["Movimento"] = decola.map({True: "Decolagem", False: "Pouso"})
df["Horario_Previsto"] = df["Partida Prevista"].where(decola, df["Chegada Prevista"])
df["Horario_Real"] = df["Partida Real"].where(decola, df["Chegada Real"])
df["Outro_Aeroporto_ICAO"] = df["Sigla ICAO Aeroporto Destino"].where(decola, df["Sigla ICAO Aeroporto Origem"])
df["Outro_Aeroporto"] = df["Descrição Aeroporto Destino"].where(decola, df["Descrição Aeroporto Origem"])
df["Situacao_ANAC"] = df["Situação Partida"].where(decola, df["Situação Chegada"])

# 5) Metricas -----------------------------------------------------------------
df["Cancelado"] = df["Situação Voo"].str.upper().eq("CANCELADO")
df["Atraso_Min"] = (df["Horario_Real"] - df["Horario_Previsto"]).dt.total_seconds() / 60
df.loc[df["Cancelado"], "Atraso_Min"] = pd.NA  # cancelado nao tem atraso
df["Faixa_Atraso"] = df["Atraso_Min"].map(faixa_atraso)
df["Pontual"] = (df["Atraso_Min"] <= LIMITE_PONTUAL_MIN).where(df["Atraso_Min"].notna())
df["Atrasado"] = (df["Atraso_Min"] > LIMITE_PONTUAL_MIN).where(df["Atraso_Min"].notna())
df["Pontual_15min"] = (df["Atraso_Min"] <= LIMITE_PONTUAL_15).where(df["Atraso_Min"].notna())

# 6) Colunas de calendario e categorias ----------------------------------------
# Voos extras (sem horario previsto): nao ha como medir atraso; ficam na base e marcados.
df["Sem_Horario_Previsto"] = df["Horario_Previsto"].isna() & ~df["Cancelado"]
ref = df["Referência"].fillna(df["Horario_Previsto"]).fillna(df["Horario_Real"])
df["Data"] = ref.dt.normalize()
df["Ano"], df["Mes"] = ref.dt.year, ref.dt.month
df["AnoMes"] = ref.dt.strftime("%Y-%m")
df["Dia_Semana_Num"] = ref.dt.dayofweek
df["Dia_Semana"] = df["Dia_Semana_Num"].map(DIAS)
hora = df["Horario_Previsto"].fillna(df["Horario_Real"])
df["Hora_Prevista"] = hora.dt.hour
df["Faixa_Horario"] = df["Hora_Prevista"].map(lambda h: faixa_horario(h) if pd.notna(h) else None)
df["Companhia"] = df["Empresa Aérea"].map(companhia)
df["Tipo_Voo"] = df["Código Tipo Linha"].map(TIPO_LINHA).fillna("Outro")

# 7) Saida enxuta --------------------------------------------------------------
saida_cols = {
    "Arquivo_Origem": "Arquivo_Origem",
    "Sigla ICAO Empresa Aérea": "Cia_ICAO",
    "Companhia": "Companhia",
    "Empresa Aérea": "Empresa_Aerea",
    "Número Voo": "Numero_Voo",
    "Tipo_Voo": "Tipo_Voo",
    "Modelo Equipamento": "Modelo_Aeronave",
    "Número de Assentos": "Assentos",
    "Movimento": "Movimento",
    "Outro_Aeroporto_ICAO": "Outro_Aeroporto_ICAO",
    "Outro_Aeroporto": "Outro_Aeroporto",
    "Horario_Previsto": "Horario_Previsto",
    "Horario_Real": "Horario_Real",
    "Data": "Data",
    "Ano": "Ano",
    "Mes": "Mes",
    "AnoMes": "AnoMes",
    "Dia_Semana_Num": "Dia_Semana_Num",
    "Dia_Semana": "Dia_Semana",
    "Hora_Prevista": "Hora_Prevista",
    "Faixa_Horario": "Faixa_Horario",
    "Situação Voo": "Situacao_Voo",
    "Cancelado": "Cancelado",
    "Sem_Horario_Previsto": "Sem_Horario_Previsto",
    "Atraso_Min": "Atraso_Min",
    "Faixa_Atraso": "Faixa_Atraso",
    "Pontual": "Pontual",
    "Atrasado": "Atrasado",
    "Pontual_15min": "Pontual_15min",
    "Situacao_ANAC": "Situacao_ANAC",
}
out = df[list(saida_cols)].rename(columns=saida_cols)
out["Assentos"] = pd.to_numeric(out["Assentos"], errors="coerce")
out["Numero_Voo"] = out["Numero_Voo"].astype(str)
out = out.sort_values("Horario_Previsto").reset_index(drop=True)

# Colunas numericas que so tem valores inteiros (ex.: Atraso_Min, Assentos) sao gravadas como inteiro.
# Assim o CSV nao tem ponto decimal ("-6.0"), que o Power BI em portugues leria como "-60".
for c in out.select_dtypes(include="float").columns:
    v = out[c].dropna()
    if (v == v.round()).all():
        out[c] = v.round().reindex(out.index).astype("Int64")

os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
out.to_csv(saida, index=False, sep=";", encoding="utf-8-sig", date_format="%Y-%m-%d %H:%M")

# 8) Resumo no terminal ---------------------------------------------------------
oper = out[~out["Cancelado"]]
print("-" * 60)
print(f"Voos lidos: {total_lido} | duplicatas removidas: {duplicadas} | voos na base: {len(out)}")
print(f"Periodo: {out['Data'].min():%d/%m/%Y} a {out['Data'].max():%d/%m/%Y}")
print(f"Cancelados: {int(out['Cancelado'].sum())} ({out['Cancelado'].mean():.1%}) | voos extras sem horario previsto (fora da pontualidade): {int(out['Sem_Horario_Previsto'].sum())}")
print(f"Pontualidade ANAC (<= {LIMITE_PONTUAL_MIN} min): {oper['Pontual'].mean():.1%} | <= 15 min: {oper['Pontual_15min'].mean():.1%} | atraso medio: {oper['Atraso_Min'].mean():.1f} min")
print(f"Arquivo gerado: {saida}")
