# -*- coding: utf-8 -*-
"""
dashboard_perf_att.py

Dashboard Streamlit de Performance Attribution por período.

Permite escolher um fundo e um intervalo de datas e ver a contribuição de
cada ativo_par (ou subsetor) na cota FIC (líquida) do período, já com:
    - suavização de Cariño (soma consistente com o retorno composto real)
    - linha sintética de "Custos e Taxas" (drag FIC vs Master)
    - check de reconciliação (soma das contribuições vs retorno real da cota)

Rodar com: streamlit run dashboard_perf_att.py
"""

import streamlit as st
import pandas as pd
import altair as alt
import plotly.express as px
from datetime import date, timedelta

from funcoesAuxiliaresSt import funcoes_auxiliares
from perf_att_core import (
    monta_perf_att_periodo,
    agrega_perf_att,
    agrega_mapa_calor,
    monta_cota_vs_benchmark,
    diagnostico_diario,
    diagnostico_acumulado,
    FUNDOS_VALIDOS,
    LINHA_CUSTOS,
)

st.set_page_config(page_title="Performance Attribution", layout="wide")

# --------------------------------------------------------------------------- #
# Conexão (cacheada) e carga de dados (cacheada por 3 minutos, convenção do projeto)
# --------------------------------------------------------------------------- #

@st.cache_resource
def get_fa():
    return funcoes_auxiliares(delta_dias=0)


@st.cache_data(ttl=180)
def carrega_periodo(fundo: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    fa = get_fa()
    return monta_perf_att_periodo(fa, fundo, data_inicio, data_fim)


@st.cache_data(ttl=180)
def carrega_cota_vs_benchmark(fundo: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    fa = get_fa()
    return monta_cota_vs_benchmark(fa, fundo, data_inicio, data_fim)


@st.cache_data(ttl=180)
def carrega_diagnostico(fundo: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    fa = get_fa()
    return diagnostico_diario(fa, fundo, data_inicio, data_fim)


# --------------------------------------------------------------------------- #
# Sidebar: filtros
# --------------------------------------------------------------------------- #

st.sidebar.header("Filtros")

fundo = st.sidebar.selectbox("Fundo", FUNDOS_VALIDOS, index=0)

hoje = date.today()
data_inicio = st.sidebar.date_input("Data início", value=hoje.replace(day=1))
data_fim = st.sidebar.date_input("Data fim", value=hoje)

agrupar_por = st.sidebar.radio(
    "Agrupar contribuição por",
    options=['ativo_par', 'subsetor', 'codigo_ativo'],
    format_func=lambda x: {'ativo_par': 'Ativo / Par', 'subsetor': 'Subsetor', 'codigo_ativo': 'Código do ativo'}[x],
)

tipo_visualizacao = st.sidebar.radio(
    "Visualização do gráfico",
    options=['barras', 'mapa_calor'],
    format_func=lambda x: {'barras': 'Gráfico de barras', 'mapa_calor': 'Mapa de calor (por setor)'}[x],
)

if data_inicio > data_fim:
    st.sidebar.error("Data início não pode ser depois da data fim.")
    st.stop()

# --------------------------------------------------------------------------- #
# Corpo
# --------------------------------------------------------------------------- #

st.title("Performance Attribution por Período")
st.caption(f"Fundo: **{fundo}** | Período: **{data_inicio}** a **{data_fim}**")

try:
    df_periodo = carrega_periodo(fundo, str(data_inicio), str(data_fim))
except ValueError as e:
    st.error(str(e))
    st.stop()

if df_periodo.empty:
    st.warning("Sem dados de perf. attribution para esse fundo/período.")
    st.stop()

tabela, check = agrega_perf_att(df_periodo, agrupar_por=agrupar_por)

dias_bench_ajustados = df_periodo.attrs.get('dias_bench_ajustados', [])
if dias_bench_ajustados:
    st.info(
        f"{len(dias_bench_ajustados)} dia(s) com marcação de cota do fundo mas sem pregão do "
        f"benchmark (feriado local, por exemplo) — o benchmark entrou com retorno 0 nesses dias: "
        + ", ".join(dias_bench_ajustados)
    )

dias_orfaos = df_periodo.attrs.get('dias_orfaos_descartados', [])
if dias_orfaos:
    st.warning(
        f"{len(dias_orfaos)} dia(s) existem em db_perf_att_master mas ainda não têm confirmação "
        f"oficial (Master + FIC) em db_resultados_fundos — provavelmente o custodiante ainda não "
        f"processou. Esses dias foram excluídos do período para não distorcer a reconciliação: "
        + ", ".join(dias_orfaos)
    )

dias_faltantes_pa = df_periodo.attrs.get('dias_faltantes_perf_att', [])
if dias_faltantes_pa:
    st.warning(
        f"{len(dias_faltantes_pa)} dia(s) têm retorno oficial em db_resultados_fundos mas "
        f"NENHUMA linha em db_perf_att_master (buraco total, não erro de valor) — provavelmente "
        f"falha pontual do script de risco naquele dia. Esses dias foram excluídos do período: "
        + ", ".join(dias_faltantes_pa)
    )

# --- Reconciliação (deve fechar, dentro de arredondamento) ---
label_alvo = (
    f"Retorno ativo real vs {check['benchmark']} do período"
    if check['eh_relativo_benchmark'] else "Retorno FIC real do período"
)

col1, col2, col3 = st.columns(3)
col1.metric("Soma das contribuições", f"{check['soma_contribuicoes']*100:.3f}%")
col2.metric(label_alvo, f"{check['retorno_alvo_periodo']*100:.3f}%")
diferenca_bps = check['diferenca'] * 10000 if pd.notna(check['diferenca']) else float('nan')
col3.metric("Diferença (bps)", f"{diferenca_bps:.2f}")

if check['eh_relativo_benchmark']:
    st.caption(
        f"Visão puramente relativa: os ativos e 'Custos e Taxas' somam contra a cota FIC "
        f"menos o retorno do {check['benchmark']} no período — não inclui o retorno absoluto "
        f"do índice como linha da tabela."
    )

if pd.notna(diferenca_bps) and abs(diferenca_bps) > 5:
    st.warning(
        "Diferença de reconciliação acima de 5 bps — vale checar se há dias sem dados "
        "em db_perf_att_master ou db_resultados_fundos dentro do período."
    )

    with st.expander("🔍 Diagnóstico: achar os dias com maior divergência"):
        st.caption(
            "Compara, dia a dia (sem suavização), o que os ativos somam em "
            "db_perf_att_master contra o que deveria ser a partir do rent_dia oficial "
            "em db_resultados_fundos. Em períodos longos, um único dia com erro de "
            "cálculo já pode explicar centenas de bps de divergência total."
        )
        if st.button("Rodar diagnóstico"):
            diag = carrega_diagnostico(fundo, str(data_inicio), str(data_fim))
            if diag.empty:
                st.info("Sem dados suficientes para o diagnóstico nesse período.")
            else:
                n_buracos = int(diag['sem_dados_perf_att'].sum())
                if n_buracos > 0:
                    st.error(
                        f"{n_buracos} dia(s) têm retorno oficial em db_resultados_fundos mas "
                        f"NENHUMA linha em db_perf_att_master (buraco total, não é erro de valor)."
                    )

                soma_delta_bps_total = diag['delta_bps'].sum()
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Dias analisados", f"{len(diag)}")
                col_b.metric("Soma de todos os deltas diários (bps)", f"{soma_delta_bps_total:.2f}")
                col_c.metric("Maior |delta| individual (bps)", f"{diag['delta_bps'].abs().max():.2f}")

                diag_acum = diagnostico_acumulado(diag)
                grafico_acum = (
                    alt.Chart(diag_acum)
                    .mark_line()
                    .encode(
                        x=alt.X('data_referencia:T', title=None),
                        y=alt.Y('delta_bps_acumulado:Q', title='Delta acumulado (bps)'),
                        tooltip=['data_referencia:T', alt.Tooltip('delta_bps_acumulado:Q', format='.2f')],
                    )
                    .properties(height=300)
                )
                st.altair_chart(grafico_acum, use_container_width=True)
                st.caption(
                    "Erro acumulado ao longo do tempo — um SALTO BRUSCO na linha aponta exatamente "
                    "a data em que o problema entrou na base (muito mais rápido que ir testando "
                    "intervalos de data manualmente). Se a linha sobe/desce suavemente sem saltos, "
                    "é ruído distribuído, não um dia específico."
                )

                diag_exibicao = diag.head(20).copy()
                diag_exibicao['soma_contrib_dia'] = diag_exibicao['soma_contrib_dia'] * 100
                diag_exibicao['esperado_dia'] = diag_exibicao['esperado_dia'] * 100
                diag_exibicao['sem_dados_perf_att'] = diag_exibicao['sem_dados_perf_att'].map(
                    {True: '⚠️ Sim', False: ''}
                )
                diag_exibicao = diag_exibicao.rename(columns={
                    'data_referencia': 'Data',
                    'soma_contrib_dia': 'Soma contrib_dia (%)',
                    'esperado_dia': 'Esperado (rent_dia oficial) (%)',
                    'delta_bps': 'Delta (bps)',
                    'sem_dados_perf_att': 'Sem dados em perf_att_master?',
                })
                st.dataframe(
                    diag_exibicao[[
                        'Data', 'Soma contrib_dia (%)', 'Esperado (rent_dia oficial) (%)',
                        'Delta (bps)', 'Sem dados em perf_att_master?',
                    ]],
                    column_config={
                        'Soma contrib_dia (%)': st.column_config.NumberColumn(format="%.3f%%"),
                        'Esperado (rent_dia oficial) (%)': st.column_config.NumberColumn(format="%.3f%%"),
                        'Delta (bps)': st.column_config.NumberColumn(format="%.2f"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(
                    "Ordenado pelo maior |delta| primeiro — os primeiros dias da lista são "
                    "os candidatos mais prováveis a ter um erro de cálculo (ou um buraco total) na base."
                )

st.divider()
st.subheader("Cota do fundo vs. Benchmark (base 100)")

try:
    df_cota_bench = carrega_cota_vs_benchmark(fundo, str(data_inicio), str(data_fim))

    df_plot = df_cota_bench.reset_index().melt(
        id_vars='data_referencia', var_name='Série', value_name='Cota (base 100)'
    )

    y_min = df_plot['Cota (base 100)'].min()
    y_max = df_plot['Cota (base 100)'].max()
    folga = max((y_max - y_min) * 0.1, 0.5)  # folga de 10% pra não colar nas bordas

    grafico_cota = (
        alt.Chart(df_plot)
        .mark_line()
        .encode(
            x=alt.X('data_referencia:T', title=None),
            y=alt.Y(
                'Cota (base 100):Q',
                scale=alt.Scale(domain=[y_min - folga, y_max + folga]),
                title='Base 100',
            ),
            color=alt.Color('Série:N', title=None),
            tooltip=['data_referencia:T', 'Série:N', alt.Tooltip('Cota (base 100):Q', format='.2f')],
        )
        .properties(height=400)
    )

    st.altair_chart(grafico_cota, use_container_width=True)
    st.caption(
        f"Cota FIC (líquida de custos) vs. {df_cota_bench.attrs.get('benchmark', 'benchmark')} "
        f"no período, ambos rebasados a 100 no início do período — a partir de "
        f"resultados.db_resultados_fundos."
    )
except ValueError as e:
    st.warning(f"Não foi possível montar o gráfico de cota vs. benchmark: {e}")

st.divider()

# --- Tabela principal ---
label_col = {'ativo_par': 'Ativo / Par', 'subsetor': 'Subsetor', 'codigo_ativo': 'Ativo'}[agrupar_por]
tabela_exibicao = tabela.rename(columns={
    agrupar_por: label_col,
    'contribuicao_periodo': 'Contribuição no período (%)',
})
tabela_exibicao['Contribuição no período (%)'] = tabela_exibicao['Contribuição no período (%)'] * 100

st.subheader(f"Contribuição por {label_col} no período")
st.dataframe(
    tabela_exibicao,
    column_config={
        'Contribuição no período (%)': st.column_config.NumberColumn(format="%.3f%%"),
    },
    use_container_width=True,
    hide_index=True,
)

# --- Gráfico: barras (top positivos/negativos) ou mapa de calor por setor ---
if tipo_visualizacao == 'barras':
    top_n = 15
    tabela_plot = pd.concat([
        tabela_exibicao.head(top_n),
        tabela_exibicao.tail(top_n),
    ]).drop_duplicates(subset=label_col).sort_values('Contribuição no período (%)', ascending=False)

    ordem_categorias = tabela_plot[label_col].tolist()  # já em ordem decrescente de contribuição

    grafico_barras = (
        alt.Chart(tabela_plot)
        .mark_bar()
        .encode(
            y=alt.Y(
                f'{label_col}:N',
                sort=ordem_categorias,
                title=None,
                axis=alt.Axis(labelOverlap=False, labelLimit=200),
            ),
            x=alt.X('Contribuição no período (%):Q', title='Contribuição no período (%)'),
            color=alt.condition(
                alt.datum['Contribuição no período (%)'] >= 0,
                alt.value('#1f77b4'),
                alt.value('#d62728'),
            ),
            tooltip=[label_col, alt.Tooltip('Contribuição no período (%):Q', format='.3f')],
        )
        .properties(height=max(300, 26 * len(tabela_plot)))
    )

    st.altair_chart(grafico_barras, use_container_width=True)

else:
    tabela_mapa = agrega_mapa_calor(df_periodo)

    if tabela_mapa.empty:
        st.warning("Sem ativos de bolsa para exibir no mapa de calor nesse período (só linhas sintéticas).")
    else:
        soma_mapa = tabela_mapa['contribuicao_periodo'].sum()
        maior_abs = tabela_mapa['contribuicao_periodo'].abs().max()

        fig = px.treemap(
            tabela_mapa,
            path=[px.Constant(f"{fundo} — Contribuição por Subsetor: {soma_mapa*100:.2f}%"), 'subsetor', 'ativo_par'],
            values='contribuicao_abs',
            color='contribuicao_periodo',
            color_continuous_scale='RdYlGn',
            range_color=[-maior_abs, maior_abs],
            color_continuous_midpoint=0,
            custom_data=['contribuicao_periodo'],
        )
        fig.update_traces(
            texttemplate='%{label}<br>%{customdata[0]:.2%}',
            hovertemplate='%{label}<br>Contribuição: %{customdata[0]:.3%}<extra></extra>',
        )
        fig.update_layout(margin=dict(t=40, l=10, r=10, b=10), height=550)
        fig.update_coloraxes(showscale=False)

        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Mapa de calor só com ativos de bolsa (exclui Custos e Taxas, Dif Fut Spot, Outros e "
            "Renda Fixa) — tamanho do bloco = magnitude da contribuição, cor = sinal e intensidade."
        )

# --- Detalhe: evolução diária de item(ns) específico(s) ---
st.divider()
st.subheader("Evolução diária de item(ns) específico(s)")

modo_detalhe = st.radio(
    "Modo de seleção",
    options=['itens', 'setor'],
    format_func=lambda x: {'itens': 'Itens individuais (múltiplos)', 'setor': 'Todos os papéis de um subsetor'}[x],
    horizontal=True,
)

df_item = pd.DataFrame()

if modo_detalhe == 'itens':
    opcoes = tabela_exibicao[label_col].tolist()
    itens_selecionados = st.multiselect(
        f"Selecione um ou mais {label_col.lower()}",
        options=opcoes,
        default=opcoes[:1],
    )
    if itens_selecionados:
        df_item = df_periodo[df_periodo[agrupar_por].isin(itens_selecionados)].copy()
        df_item = df_item.rename(columns={agrupar_por: 'Série'})

else:
    setores_disponiveis = sorted(df_periodo['subsetor'].unique().tolist())
    setor_selecionado = st.selectbox("Selecione um subsetor", options=setores_disponiveis)
    df_item = df_periodo[df_periodo['subsetor'] == setor_selecionado].copy()
    df_item = df_item.rename(columns={'ativo_par': 'Série'})

if not df_item.empty:
    df_item = (
        df_item.groupby(['Série', 'data_referencia'], as_index=False)['contrib_dia_suavizada']
        .sum()
        .sort_values(['Série', 'data_referencia'])
    )
    df_item['Contribuição acumulada (%)'] = (
        df_item.groupby('Série')['contrib_dia_suavizada'].cumsum() * 100
    )

    grafico_evolucao = (
        alt.Chart(df_item)
        .mark_line()
        .encode(
            x=alt.X('data_referencia:T', title=None),
            y=alt.Y('Contribuição acumulada (%):Q'),
            color=alt.Color('Série:N', title=None),
            tooltip=['Série:N', 'data_referencia:T', alt.Tooltip('Contribuição acumulada (%):Q', format='.3f')],
        )
        .properties(height=400)
    )
    st.altair_chart(grafico_evolucao, use_container_width=True)
else:
    st.info("Selecione ao menos um item (ou um subsetor) para ver a evolução diária.")

nota_benchmark = (
    f" Para fundos long-only (ex.: LO1), a contribuição por ativo já é relativa ao "
    f"{check.get('benchmark', 'benchmark')} — não há linha separada de 'Benchmark' na "
    f"tabela de contribuição, a visão é puramente relativa (alpha)."
    if check.get('eh_relativo_benchmark') else ""
)
st.caption(
    "Nota: 'Custos e Taxas' representa o drag entre a cota Master (bruta) e a cota FIC "
    "(líquida de tx_adm/tx_pfee) — não é um ativo da carteira." + nota_benchmark
)