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
        return df
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        return pd.DataFrame()

df = carregar_dados()

#st.set_page_config(layout="wide")
st.title("Análise das Métricas dos Fundos")


min_date = df['data_referencia'].min().date()  # converte para datetime.date
max_date = df['data_referencia'].max().date()

data_selecao = st.slider(
    "Selecione o intervalo de datas",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date)
)

# Depois, no filtro do DataFrame, converta a coluna para date também para comparar:
df_filtrado = df[
    (df['data_referencia'].dt.date >= data_selecao[0]) & 
    (df['data_referencia'].dt.date <= data_selecao[1])
]
df_filtrado = df_filtrado.sort_values('data_referencia')

# Filtro de fundo (multiselect)
fundos = df_filtrado['fundo'].unique()
fundos_selecionados = st.multiselect("Selecione os fundos", options=fundos, default=fundos.tolist())

df_filtrado = df_filtrado[df_filtrado['fundo'].isin(fundos_selecionados)]

# Gráfico interativo de net
fig_net = px.line(df_filtrado, x='data_referencia', y='net', color='fundo', 
                  title="Net ao longo do tempo", labels={'net': 'Net', 'data_referencia': 'Data'})
fig_net.update_yaxes(tickformat='.0%')
st.plotly_chart(fig_net, use_container_width=True)

# Gráfico interativo de gross
fig_gross = px.line(df_filtrado, x='data_referencia', y='gross', color='fundo', 
                    title="Gross ao longo do tempo", labels={'gross': 'Gross', 'data_referencia': 'Data'})
fig_gross.update_yaxes(tickformat='.0%')
st.plotly_chart(fig_gross, use_container_width=True)

# Gráfico interativo de TE
fig_te = px.line(df_filtrado, x='data_referencia', y='te_ex_ante', color='fundo', 
                  title="TE / Vol ex-ante ao longo do tempo", labels={'te_ex_ante': 'Tracking Error / Vol ex-ante', 'data_referencia': 'Data'})
fig_te.update_yaxes(tickformat='.2%')
st.plotly_chart(fig_te, use_container_width=True)

# Gráfico interativo de beta ajustado
fig_beta = px.line(df_filtrado, x='data_referencia', y='beta_ajustado', color='fundo', 
                  title="Beta Ajustado ao longo do tempo", labels={'beta_ajustado': 'Beta', 'data_referencia': 'Data'})
fig_beta.update_yaxes(tickformat='.0%')
st.plotly_chart(fig_beta, use_container_width=True)

# Gráfico interativo de BVaR
fig_var = px.line(df_filtrado, x='data_referencia', y='bvar', color='fundo', 
                  title="BVaR ao longo do tempo", labels={'bvar': 'BVaR', 'data_referencia': 'Data'})
fig_var.update_yaxes(tickformat='.2%')
st.plotly_chart(fig_var, use_container_width=True)

# Gráfico interativo de Exp Índice
fig_ind = px.line(df_filtrado, x='data_referencia', y='exp_ind', color='fundo', 
                  title="Exposição à Índice Futuro ao longo do tempo", labels={'exp_ind': 'Exposição a Índice', 'data_referencia': 'Data'})
fig_ind.update_yaxes(tickformat='.2%')
st.plotly_chart(fig_ind, use_container_width=True)