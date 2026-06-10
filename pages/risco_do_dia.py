import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
from supabase_client import supabase  # seu cliente supabase configurado

@st.cache_data(ttl=60)
def carregar_dados():
    try:
        response = supabase.table("risco_db_net_gross_fundos").select("*").execute()
        df = pd.DataFrame(response.data)
        df['data_referencia'] = pd.to_datetime(df['data_referencia'])
        df = df.sort_values('data_referencia', ascending=False)
        return df
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        return pd.DataFrame()

dados_filtro = carregar_dados()


def carregar_dados_filtro(nome_tabela, data, fundo):
    try:
        response = supabase.table(nome_tabela).select("*")\
        .eq("data_referencia", data).eq("fundo", fundo).execute()
        df = pd.DataFrame(response.data)
        df['data_referencia'] = pd.to_datetime(df['data_referencia'])
        return df
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        return pd.DataFrame()

st.title("Risco do dia por fundo")

fundos_disponiveis =  dados_filtro['fundo'].unique()
datas_disponiveis =  sorted(dados_filtro['data_referencia'].unique(), reverse=True)

data_selecionada = st.selectbox("Selecione a data de referência", datas_disponiveis)
fundo_selecionado = st.selectbox("Selecione o fundo", fundos_disponiveis)

# Tabelas e colunas que queremos mostrar (exemplo)
tabelas_e_colunas = {
    "risco_db_exposicao_ativos": ["ativo_par", "subsetor", "exposure_net", "exposure_cash", "exposure_opcao", "beta_ajustado"],
    "risco_db_exposicao_setorial": ["subsetor", "exposure_net", "exposure_cash_net", "exposure_opcao", "beta_ajustado"],
    "risco_db_pa_master": ["ativo_par", "subsetor", "contrib_dia", "contrib_dia_opcao"],
    "risco_db_table_options": ["tipo_opcao", "codigo_ativo", "ativo_objeto", "data_expire", 
                               "spot", "strike", "preco_hoje", "vol", "delta", "quantidade_hoje", "exposure", "exposure_bps"],
    "risco_db_net_gross_fundos": ["net", "gross", "beta_ajustado", "te_ex_ante", "bvar", "cvar", "exp_ind"],
}

st.header("Métricas de risco do dia")
df = carregar_dados_filtro("risco_db_net_gross_fundos", data_selecionada, fundo_selecionado)
if df.empty:
    st.write("Sem dados para essa combinação.")
else:
    # Filtrar as colunas que queremos mostrar, caso existam no df
    colunas = tabelas_e_colunas["risco_db_net_gross_fundos"]
    colunas_disponiveis = [c for c in colunas if c in df.columns]
    colunas_percentuais = df.select_dtypes(include=['float', 'int']).columns
    df[colunas_percentuais] = df[colunas_percentuais] * 100
    st.dataframe(df[colunas_disponiveis].reset_index(drop=True).style.format({col: "{:.2f}%" for col in colunas_percentuais}))
    
st.header("Exposição Setorial")
df = carregar_dados_filtro("risco_db_exposicao_setorial", data_selecionada, fundo_selecionado)
if df.empty:
    st.write("Sem dados para essa combinação.")
else:
    # Filtrar as colunas que queremos mostrar, caso existam no df
    colunas = tabelas_e_colunas["risco_db_exposicao_setorial"]
    colunas_disponiveis = [c for c in colunas if c in df.columns]
    colunas_percentuais = df.select_dtypes(include=['float', 'int']).columns
    df[colunas_percentuais] = df[colunas_percentuais] * 100
    df = df.sort_values(by="exposure_net", ascending=False).reset_index(drop=True)
    st.dataframe(df[colunas_disponiveis].reset_index(drop=True).style.format({col: "{:.1f}%" for col in colunas_percentuais}))  
    
st.header("Exposição por ativo")
df = carregar_dados_filtro("risco_db_exposicao_ativos", data_selecionada, fundo_selecionado)
if df.empty:
    st.write("Sem dados para essa combinação.")
else:
    # Filtrar as colunas que queremos mostrar, caso existam no df
    colunas = tabelas_e_colunas["risco_db_exposicao_ativos"]
    colunas_disponiveis = [c for c in colunas if c in df.columns]
    colunas_percentuais = df.select_dtypes(include=['float', 'int']).columns
    df[colunas_percentuais] = df[colunas_percentuais] * 100
    df = df.sort_values(by="exposure_net", ascending=False).reset_index(drop=True)
    st.dataframe(df[colunas_disponiveis].reset_index(drop=True).style.format({col: "{:.2f}%" for col in colunas_percentuais}), height = 600)  
    
    st.header("Exposição em opções por ativo ponderado ao delta")
    df[colunas_percentuais] = df[colunas_percentuais] /100
    df_options = df[df['exposure_opcao'] != 0]
    colunas = ["ativo_par", "exposure_opcao"]
    colunas_disponiveis = [c for c in colunas if c in df_options.columns]
    df_options = df_options.sort_values(by="exposure_opcao", ascending=False).reset_index(drop=True)
    
    fig = px.bar(
    df_options,
    x='exposure_opcao',
    y='ativo_par',
    orientation='h',
    text='exposure_opcao',
    labels={'exposure_opcao': 'Exposição (%)', 'ativo_par': 'Ativo'},
    title='Exposição Opções'
    )
    # Formata o eixo X como porcentagem
    fig.update_layout(xaxis_tickformat='.1%')
    # Ajusta o texto acima das barras
    fig.update_traces(texttemplate='%{text:.1%}', textposition='outside')
    st.plotly_chart(fig, use_container_width=True)
    
st.header("Tabela de Opções")
df = carregar_dados_filtro("risco_db_table_options", data_selecionada, fundo_selecionado)
if df.empty:
    st.write("Sem dados para essa combinação.")
else:
    # Filtrar as colunas que queremos mostrar, caso existam no df
    colunas = tabelas_e_colunas["risco_db_table_options"]
    colunas_disponiveis = [c for c in colunas if c in df.columns]
    df['exposure'] = df['exposure'] * 100
    df = df.sort_values(by="codigo_ativo", ascending=False).reset_index(drop=True)
    st.dataframe(df[colunas_disponiveis].reset_index(drop=True).style.format({col: "{:.2f}%" for col in ['exposure']}))      

st.header("Performance Attribution do dia (relativo)")
df = carregar_dados_filtro("risco_db_pa_master", data_selecionada, fundo_selecionado)
if df.empty:
    st.write("Sem dados para essa combinação.")
else:
    # Filtrar as colunas que queremos mostrar, caso existam no df
    colunas = tabelas_e_colunas["risco_db_pa_master"]
    colunas_disponiveis = [c for c in colunas if c in df.columns]
    # colunas_float = df.select_dtypes(include=['float', 'int']).columns
    # df[colunas_float] = df[colunas_float]
    df['contrib_dia_cash'] = df['contrib_dia'] - df['contrib_dia_opcao']
    colunas_disponiveis.append('contrib_dia_cash')
    df = df.sort_values(by="contrib_dia", ascending=False).reset_index(drop=True)
    df = df[df['subsetor'] != 'Outros']
    st.dataframe(df[colunas_disponiveis].reset_index(drop=True))  

    st.header("Performance Attribution do dia (relativo) por setor")
    df_setorial = df.groupby('subsetor', as_index=False)[['contrib_dia', 'contrib_dia_opcao', 'contrib_dia_cash']].sum()
    df_setorial = df_setorial.sort_values(by="contrib_dia", ascending=False).reset_index(drop=True)
    colunas_disponiveis.remove('ativo_par')
    st.dataframe(df_setorial[colunas_disponiveis].reset_index(drop=True))  


