# -*- coding: utf-8 -*-
"""
Created on Mon Aug  4 15:48:39 2025

@author: Ivan
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
from supabase_client import supabase  # seu cliente supabase configurado
from datetime import datetime
from funcoesAuxiliaresSt import funcoes_auxiliares

@st.cache_data(ttl=60)
def carregar_dados(tabela):
    try:
        response = supabase.table(tabela).select("*").execute()
        df = pd.DataFrame(response.data)
        df['data_referencia'] = pd.to_datetime(df['data_referencia'])
        df = df.sort_values('data_referencia')
        df['data_referencia'] = pd.to_datetime(df['data_referencia'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        return pd.DataFrame()

#st.set_page_config(layout="wide")
st.title("Cotas dos fundos Oby Equities")

df_fundos = carregar_dados("db_pl_fundos")[['data_referencia', 'fundo', 'valor_cota']]
df_cdi = carregar_dados("db_cota_cdi")[['data_referencia', 'cota_cdi']]
df_ibov = carregar_dados("db_hist_ibovespa")

df_fundos = df_fundos.rename(columns = {'fundo': 'ativo', 'valor_cota': 'cota'})
df_cdi = df_cdi.rename(columns = {'cota_cdi': 'cota'})
df_cdi['ativo'] = 'CDI'
df_ibov = df_ibov.rename(columns = {'valor': 'cota', 'codigo_ativo': 'ativo'})

df_cotas = pd.concat([df_fundos, df_cdi], ignore_index=True)
df_cotas = pd.concat([df_cotas, df_ibov], ignore_index=True)
df_cotas = df_cotas.sort_values('data_referencia').reset_index(drop = True)


# Filtros
ativos_disponiveis = df_cotas['ativo'].unique().tolist()
ativos_default = ['LO1_FIC', 'LSH1_FIC', 'LSH2_FIC', 'CDI', 'IBOV']
data_min = df_cotas['data_referencia'].min().date()
data_max = df_cotas['data_referencia'].max().date()

# Seletor de intervalo de datas no calendário
data_inicio = st.date_input(
    "Data inicial",
    value=data_min,
    min_value=data_min,
    max_value=data_max
)

data_fim = st.date_input(
    "Data final",
    value=data_max,
    min_value=data_min,
    max_value=data_max
)

ativos_selecionados = st.multiselect(
    "Selecione os ativos",
    options=ativos_disponiveis,
    default=ativos_default
)

# Filtrando
data_inicio = pd.to_datetime(data_inicio)
data_fim = pd.to_datetime(data_fim)

df_filtrado = df_cotas[
    (df_cotas['data_referencia'] >= data_inicio) &
    (df_cotas['data_referencia'] <= data_fim) &
    (df_cotas['ativo'].isin(ativos_selecionados))
].copy()

# Calcular retorno percentual acumulado
df_filtrado.sort_values(['ativo', 'data_referencia'], inplace=True)
df_filtrado['cota_inicial'] = df_filtrado.groupby('ativo')['cota'].transform('first')
df_filtrado['retorno_%'] = (df_filtrado['cota'] / df_filtrado['cota_inicial'] - 1) * 100

# Gráfico
fig = px.line(
    df_filtrado,
    x='data_referencia',
    y='retorno_%',
    color='ativo',
    labels={'data_referencia': 'Data', 'retorno_%': 'Retorno (%)'},
    title='Retorno percentual acumulado no período',
    height = 600
)
fig.update_layout(hovermode="x unified")

st.plotly_chart(fig, use_container_width=True)

st.header("Divulgação")

depara = pd.DataFrame({'fundo' : ['LO1_FIC', 'LSH1_FIC', 'LSH2_FIC'],
                       'cnpj' : ['37.830.181/0001-93', '35.844.973/0001-91', '40.830.356/0001-77']})
df_fundos = carregar_dados("db_pl_fundos")
df_fundos = df_fundos.merge(depara, on = 'fundo')
df_fundos = df_fundos.rename(columns ={'fundo': 'ativo', 'valor_cota':'cota'})

# Garantir tipo datetime
df_fundos['data_referencia'] = pd.to_datetime(df_fundos['data_referencia'])
df_cotas['data_referencia'] = pd.to_datetime(df_cotas['data_referencia'])

# Dropdown para escolha da data base
# Define uma data base padrão
data_base = st.date_input(
    label="Data base:",
    value=df_fundos['data_referencia'].max(),
    format="DD/MM/YYYY"  # Exibe no formato brasileiro
)

# Filtrar até a data base
data_base = pd.to_datetime(data_base)

df_filtrado = df_fundos[df_fundos['data_referencia'] <= data_base].copy()
df_filtrado_2 = df_cotas[df_cotas['data_referencia'] <= data_base].copy()
cdi_add = df_filtrado_2[df_filtrado_2['ativo'] == 'CDI']
cdi_add['ativo'] = 'CDI - OBY LONG SHORT'
df_filtrado_2 = pd.concat([df_filtrado_2, cdi_add], ignore_index = True)
cdi_add['ativo'] = 'CDI - OBY LONG SHORT 2X'
df_filtrado_2 = pd.concat([df_filtrado_2, cdi_add], ignore_index = True)
df_filtrado_2 = df_filtrado_2[df_filtrado_2['ativo'] != 'CDI']

# Última cota por ativo até a data_base
df_ult = df_filtrado[df_filtrado['data_referencia'] == data_base]
df_ult_2 = df_filtrado_2[df_filtrado_2['data_referencia'] == data_base]


# Datas de referência auxiliares
data_ontem = df_filtrado[df_filtrado['data_referencia'] <= df_filtrado['data_referencia'].max() - pd.Timedelta(days=1)]['data_referencia'].max()
data_ontem_2 = df_filtrado_2[df_filtrado_2['data_referencia'] <= df_filtrado_2['data_referencia'].max() - pd.Timedelta(days=1)]['data_referencia'].max()
inicio_mes = pd.to_datetime(data_base).replace(day=1)
inicio_ano = pd.to_datetime(data_base).replace(month=1, day=1)

# datas referencia de 12, 24 e 36M

fa = funcoes_auxiliares(-1)
d_12m = fa.pega_data_referencia(data_base - pd.DateOffset(months=12), 1)
d_24m = fa.pega_data_referencia(data_base - pd.DateOffset(months=24), 1)
d_36m = fa.pega_data_referencia(data_base - pd.DateOffset(months=36), 1)


datas_periodos = {
    "dia": data_ontem,
    "mes": df_filtrado[(df_filtrado['data_referencia'] < inicio_mes)]['data_referencia'].max(),
    "ytd": df_filtrado[(df_filtrado['data_referencia'] < inicio_ano)]['data_referencia'].max(),
    "12m": df_filtrado[(df_filtrado['data_referencia'] <= pd.to_datetime(d_12m))]['data_referencia'].max(),
    "24m": df_filtrado[(df_filtrado['data_referencia'] <= pd.to_datetime(d_24m))]['data_referencia'].max(),
    "36m": df_filtrado[(df_filtrado['data_referencia'] <= pd.to_datetime(d_36m))]['data_referencia'].max(),
    "inicio": df_filtrado.groupby('ativo')['data_referencia'].min(),
    "inicio CDI H1": df_filtrado[df_filtrado['ativo'] == 'LSH1_FIC']['data_referencia'].min(),
    "inicio CDI H2": df_filtrado[df_filtrado['ativo'] == 'LSH2_FIC']['data_referencia'].min(),
    "inicio IBOV": df_filtrado[df_filtrado['ativo'] == 'LO1_FIC']['data_referencia'].min(),
}

    # "12m": df_filtrado[(df_filtrado['data_referencia'] <= data_base - pd.DateOffset(months=12))]['data_referencia'].max(),
    # "24m": df_filtrado[(df_filtrado['data_referencia'] <= data_base - pd.DateOffset(months=24))]['data_referencia'].max(),
    # "36m": df_filtrado[(df_filtrado['data_referencia'] <= data_base - pd.DateOffset(months=36))]['data_referencia'].max(),


# Função auxiliar para extrair cota de uma data específica
def get_cota_em_data(df, data_ref_dict):
    cotas = []
    df_2 = df.sort_values('data_referencia')
    for ativo, data_ref in data_ref_dict.items():
        df_ativo = df_2[df_2['ativo'] == ativo]
        df_ativo = df_ativo[df_ativo['data_referencia'] <= data_ref].tail(1)
        data_ref_2 = df_ativo.reset_index()['data_referencia'][0]
        linha = df[(df['ativo'] == ativo) & (df['data_referencia'] == data_ref_2)]
        if not linha.empty:
            cotas.append((ativo, linha['cota'].values[0]))
        else:
            cotas.append((ativo, None))
    return dict(cotas)

# Cotas passadas
cotas_dict = {}
for nome, datas in datas_periodos.items():
    if isinstance(datas, pd.Series):  # mes, ytd, inicio
        cotas_dict[nome] = get_cota_em_data(df_filtrado, datas.to_dict())
    else:
        df_temp = df_filtrado[df_filtrado['data_referencia'] == datas]
        cotas_dict[nome] = df_temp.set_index('ativo')['cota'].to_dict()
        
cotas_dict = {}
for nome, datas in datas_periodos.items():
    if isinstance(datas, pd.Series):  # mes, ytd, inicio
        cotas_dict[nome] = get_cota_em_data(df_filtrado_2, datas.to_dict())
    else:
        df_temp = df_filtrado_2[df_filtrado_2['data_referencia'] == datas]
        cotas_dict[nome] = df_temp.set_index('ativo')['cota'].to_dict()        

# Calculando retornos
def calcula_retorno(cota_atual, cota_passada):
    if pd.notnull(cota_atual) and pd.notnull(cota_passada) and cota_passada != 0:
        return cota_atual / cota_passada - 1
    return None

df_ult['rent_dia'] = df_ult.apply(lambda row: calcula_retorno(row['cota'], cotas_dict['dia'].get(row['ativo'])), axis=1)
df_ult['rent_mes'] = df_ult.apply(lambda row: calcula_retorno(row['cota'], cotas_dict['mes'].get(row['ativo'])), axis=1)
df_ult['rent_ytd'] = df_ult.apply(lambda row: calcula_retorno(row['cota'], cotas_dict['ytd'].get(row['ativo'])), axis=1)
df_ult['rent_12m'] = df_ult.apply(lambda row: calcula_retorno(row['cota'], cotas_dict['12m'].get(row['ativo'])), axis=1)
df_ult['rent_24m'] = df_ult.apply(lambda row: calcula_retorno(row['cota'], cotas_dict['24m'].get(row['ativo'])), axis=1)
df_ult['rent_36m'] = df_ult.apply(lambda row: calcula_retorno(row['cota'], cotas_dict['36m'].get(row['ativo'])), axis=1)
df_ult['rent_total'] = df_ult.apply(lambda row: calcula_retorno(row['cota'], cotas_dict['inicio'].get(row['ativo'])), axis=1)


df_ult_2['rent_dia'] = df_ult_2.apply(lambda row: calcula_retorno(row['cota'], cotas_dict['dia'].get(row['ativo'])), axis=1)
df_ult_2['rent_mes'] = df_ult_2.apply(lambda row: calcula_retorno(row['cota'], cotas_dict['mes'].get(row['ativo'])), axis=1)
df_ult_2['rent_ytd'] = df_ult_2.apply(lambda row: calcula_retorno(row['cota'], cotas_dict['ytd'].get(row['ativo'])), axis=1)
df_ult_2['rent_12m'] = df_ult_2.apply(lambda row: calcula_retorno(row['cota'], cotas_dict['12m'].get(row['ativo'])), axis=1)
df_ult_2['rent_24m'] = df_ult_2.apply(lambda row: calcula_retorno(row['cota'], cotas_dict['24m'].get(row['ativo'])), axis=1)
df_ult_2['rent_36m'] = df_ult_2.apply(lambda row: calcula_retorno(row['cota'], cotas_dict['36m'].get(row['ativo'])), axis=1)
df_ult_2['rent_total'] = 0
df_ult_2['rent_total'] = df_ult_2['rent_total'].astype(float)
df_ult_2.loc[df_ult_2['ativo'] == 'IBOV', 'rent_total'] = calcula_retorno(df_ult_2.loc[df_ult_2['ativo'] == 'IBOV', 'cota'].values[0],
                                                                          cotas_dict['inicio IBOV']['IBOV'])
df_ult_2.loc[df_ult_2['ativo'] == 'CDI - OBY LONG SHORT', 'rent_total'] = calcula_retorno(df_ult_2.loc[df_ult_2['ativo'] == 'CDI - OBY LONG SHORT', 'cota'].values[0],
                                                                          cotas_dict['inicio CDI H1']['CDI - OBY LONG SHORT'])
df_ult_2.loc[df_ult_2['ativo'] == 'CDI - OBY LONG SHORT 2X', 'rent_total'] = calcula_retorno(df_ult_2.loc[df_ult_2['ativo'] == 'CDI - OBY LONG SHORT 2X', 'cota'].values[0],
                                                                          cotas_dict['inicio CDI H2']['CDI - OBY LONG SHORT 2X'])

# PL atual e PL médio 12M
df_pl_12m = df_filtrado[df_filtrado['data_referencia'] >= (data_base - pd.DateOffset(months=12))]
df_pl_medio = df_pl_12m.groupby('ativo')['pl'].mean().reset_index().rename(columns={'pl': 'pl_medio_12m'})

df_final = df_ult[['ativo', 'cnpj', 'cota', 'rent_dia', 'rent_mes', 'rent_ytd', 'rent_12m', 'rent_24m', 'rent_36m', 'rent_total', 'pl']]
df_final = df_final.merge(df_pl_medio, on='ativo', how='left')
df_final.loc[df_final['ativo'] == 'LSH1_FIC', 'ativo'] = 'OBY LONG SHORT'
df_final.loc[df_final['ativo'] == 'LSH2_FIC', 'ativo'] = 'OBY LONG SHORT 2X'
df_final.loc[df_final['ativo'] == 'LO1_FIC', 'ativo'] = 'OBY IBOVESPA ATIVO'
df_final = df_final.sort_values('ativo')

df_final_2 = df_ult_2[['ativo', 'rent_dia', 'rent_mes', 'rent_ytd', 'rent_12m', 'rent_24m', 'rent_36m', 'rent_total']]

# Renomear e formatar
df_final.rename(columns={
    'ativo': 'Fundo',
    'cnpj': 'CNPJ',
    'cota': 'Cota',
    'rent_dia': 'Dia (%)',
    'rent_mes': 'Mês (%)',
    'rent_ytd': 'Ano (%)',
    'rent_12m': '12M (%)',
    'rent_24m': '24M (%)',
    'rent_36m': '36M (%)',
    'rent_total': 'Início (%)',
    'pl': 'PL Atual',
    'pl_medio_12m': 'PL Médio 12M'
}, inplace=True)

df_final_2.rename(columns={
    'ativo': 'Índice',
    'rent_dia': 'Dia (%)',
    'rent_mes': 'Mês (%)',
    'rent_ytd': 'Ano (%)',
    'rent_12m': '12M (%)',
    'rent_24m': '24M (%)',
    'rent_36m': '36M (%)',
    'rent_total': 'Início (%)',
}, inplace=True)

df_final_2 = df_final_2[(df_final_2['Índice'] == 'IBOV') | (df_final_2['Índice'] == 'CDI - OBY LONG SHORT') | (df_final_2['Índice'] == 'CDI - OBY LONG SHORT 2X')]
df_final_2 = df_final_2.reset_index(drop = True)

# Formatando colunas
df_final_formatada = df_final.copy()
df_final_formatada_2 = df_final_2.copy()
percent_cols = ['Dia (%)', 'Mês (%)', 'Ano (%)', '12M (%)', '24M (%)', '36M (%)', 'Início (%)']
# Percentuais
df_final_formatada[percent_cols] = df_final_formatada[percent_cols].apply(
    lambda col: col.map(lambda x: f"{x:.2%}" if pd.notnull(x) else '-')
)

df_final_formatada_2[percent_cols] = df_final_formatada_2[percent_cols].apply(
    lambda col: col.map(lambda x: f"{x:.2%}" if pd.notnull(x) else '-')
)

# Cota
df_final_formatada['Cota'] = df_final_formatada['Cota'].map(
    lambda x: f"{x:,.6f}" if pd.notnull(x) else '-'
)

# PL
cols_pl = ['PL Atual', 'PL Médio 12M']
df_final_formatada[cols_pl] = df_final_formatada[cols_pl].apply(
    lambda col: col.map(lambda x: f"{x:,.0f}" if pd.notnull(x) else '-')
)


# Exibir
def center_align(val):
    return 'text-align: center'

cols_to_center = df_final_formatada.columns[1:]

styled_df = df_final_formatada.style.set_table_styles(
    [
        {
            'selector': 'th',
            'props': [
                ('background-color', '#003366'),
                ('color', 'white'),
                ('font-weight', 'bold'),
                ('text-align', 'center')
            ]
        },
        {
            'selector': 'th.col0',
            'props': [('width', '200px')]
        }
    ]
).hide(axis='index').map(center_align, subset=cols_to_center)


st.markdown(
    styled_df.to_html(escape=False),
    unsafe_allow_html=True
)

# Segundo dataframe
cols_to_center = df_final_formatada_2.columns[1:]

styled_df = df_final_formatada_2.style.set_table_styles(
    [
        {
            'selector': 'th',
            'props': [
                ('background-color', '#003366'),
                ('color', 'white'),
                ('font-weight', 'bold'),
                ('text-align', 'center')
            ]
        },
        {
            'selector': 'th.col0',
            'props': [('width', '440px')]
        }
    ]
).hide(axis='index').map(center_align, subset=cols_to_center)


st.markdown(
    styled_df.to_html(escape=False),
    unsafe_allow_html=True
)

