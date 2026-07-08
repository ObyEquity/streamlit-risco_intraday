# -*- coding: utf-8 -*-
"""
momentum_score_widget.py
========================
Componente Streamlit para exibir o score de momentum do Ibovespa
no dashboard de risco intraday.

Uso no seu dashboard principal:
    from momentum_score_widget import render_momentum_score
    render_momentum_score(supabase_client)

Ou standalone:
    streamlit run momentum_score_widget.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ── Cores do modelo ────────────────────────────────────────────────────────────
SCORE_COLORS = {
    3:  '#1a7a4a',   # verde escuro
    2:  '#3a9a6a',   # verde
    1:  '#88ccaa',   # verde claro
    0:  '#aaaaaa',   # cinza
    -1: '#e8a060',   # laranja
    -3: '#b83232',   # vermelho
}

SCORE_LABELS = {
    3:  'Score +3',
    2:  'Score +2',
    1:  'Score +1',
    0:  'Neutro',
    -1: 'Score −1',
    -3: 'Score −3',
}

# Estados de momentum (linhas da tabela de quadrantes)
MOMENTUM_STATES = [
    'Score 2 · 4w↑ 8w↑ (tendência)',
    'Score 1b · 4w↓ 8w↑ (pullback)',
    'Score 1a · 4w↑ 8w↓ (impulso)',
    'Score 0 · 4w↓ 8w↓ (mom. neg.)',
]

# Faixas de breadth (colunas da tabela)
BREADTH_BUCKETS = [
    '<5%\nColapso',
    '5-20%↓\nCap. caindo',
    '5-20%↑\nCap. virando',
    '20-40%\nStress',
    '40-60%\nNeutro',
    '>60%\nSaudável',
]

# Tabela de quadrantes do modelo C3b — valores fixos (regras de negócio do
# modelo, replicadas de calcula_score() em ibov_momentum_score.py).
# ATENÇÃO: se a lógica de calcula_score() mudar, atualize esta tabela também —
# ela é uma cópia estática para não criar dependência entre os dois arquivos.
# linhas = MOMENTUM_STATES, colunas = BREADTH_BUCKETS
QUADRANTE_SCORES = [
    #  <5%   5-20%↓  5-20%↑  20-40%  40-60%  >60%
    [    0,     0,      2,      1,      0,     1],   # Score 2 (4w+ 8w+)
    [    0,     0,      2,      3,      2,     2],   # Score 1b (4w- 8w+)
    [    0,     0,      2,      2,      2,     2],   # Score 1a (4w+ 8w-)
    [    0,     0,      2,     -3,     -1,     0],   # Score 0 (4w- 8w-)
]


def score_color(s: int) -> str:
    return SCORE_COLORS.get(s, '#aaa')


def _breadth_bucket_index(breadth: float, br_delta2: float) -> int:
    """Identifica em qual coluna da tabela de quadrantes o breadth atual cai."""
    if breadth < 5:
        return 0
    if 5 <= breadth < 20:
        return 2 if br_delta2 > 0 else 1
    if 20 <= breadth < 40:
        return 3
    if 40 <= breadth < 60:
        return 4
    return 5


def _momentum_state_index(mom4: float, mom8: float) -> int:
    """Identifica em qual linha da tabela de quadrantes o momentum atual cai."""
    s4, s8 = mom4 > 0, mom8 > 0
    if s4 and s8:
        return 0
    if not s4 and s8:
        return 1
    if s4 and not s8:
        return 2
    return 3


def render_momentum_score(supabase_client=None, dados: pd.DataFrame = None):
    """
    Renderiza o painel de momentum score.

    Parâmetros
    ----------
    supabase_client : cliente Supabase (opcional se passar dados diretamente)
    dados           : DataFrame com os dados já carregados (para testes)
    """

    # ── Carrega dados ──────────────────────────────────────────────────────────
    if dados is None and supabase_client is not None:
        try:
            resp = (supabase_client
                    .schema('risco_intraday')
                    .table('db_momentum_score')
                    .select('*')
                    .order('timestamp', desc=True)
                    .limit(1)
                    .execute())
            if resp.data:
                dados = pd.DataFrame(resp.data)
            else:
                st.warning('Sem dados de momentum disponíveis.')
                return
        except Exception as e:
            st.error(f'Erro ao carregar dados: {e}')
            return

    if dados is None or dados.empty:
        st.info('Aguardando dados do script de coleta...')
        return

    d = dados.iloc[0]

    score_atual = int(d['score_atual'])
    score_proj  = int(d['score_projetado'])
    score_mudou = bool(d.get('score_mudou', score_atual != score_proj))
    timestamp   = d.get('timestamp', '—')
    estado_atual_desc = d.get('estado_descricao', '—')
    estado_proj_desc  = d.get('estado_proj_desc', '—')

    # ── Layout ─────────────────────────────────────────────────────────────────
    st.markdown('### 📊 Score de Momentum — Ibovespa')
    st.caption(f'Atualizado em {timestamp} · Score fixo toda sexta-feira')

    # Alerta se score projetado diverge
    if score_mudou:
        st.warning(
            f'⚠️ Score projetado ({score_proj}) difere do score vigente ({score_atual}) '
            f'— se o mercado fechar como está, o score muda no rebalanceamento de sexta.'
        )

    # ── Linha 1: métricas principais ───────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(label='Score vigente (sexta)', value=SCORE_LABELS[score_atual])
        st.caption(estado_atual_desc)

    with c2:
        delta_score = score_proj - score_atual
        st.metric(
            label='Score projetado (hoje)',
            value=SCORE_LABELS[score_proj],
            delta=f'{delta_score:+d}' if delta_score != 0 else 'Estável',
            delta_color='normal' if delta_score >= 0 else 'inverse'
        )
        st.caption(estado_proj_desc)

    with c3:
        st.metric(
            label='Ibov atual',
            value=f'{d["ibov_pts_atual"]:,.0f}',
            delta=f'{d["variacao_semana_pct"]:+.2f}% na semana',
            delta_color='normal' if d['variacao_semana_pct'] >= 0 else 'inverse'
        )

    with c4:
        st.metric(
            label='Breadth 100d',
            value=f'{d["breadth_100d"]:.1f}%',
            delta=f'Δ2w {d["breadth_delta2w"]:+.1f}pp',
            delta_color='normal' if d['breadth_delta2w'] >= 0 else 'inverse'
        )

    # ── Distância até mudança de score (custom, sem depender da seta automática
    #    do st.metric — que causava setas incoerentes com o sinal do valor) ─────
    dist_a = d.get('dist_alta_pct')
    dist_b = d.get('dist_baixa_pct')
    dist_a = None if pd.isna(dist_a) else dist_a
    dist_b = None if pd.isna(dist_b) else dist_b

    st.markdown('**Distância até mudança de score**')
    if dist_a is None and dist_b is None:
        st.info(
            '🔒 Nenhuma variação de preço muda o score no momento — o breadth atual está '
            'em regime de governança (colapso <5% ou capitulação caindo 5–20%↓), que trava '
            'o score em neutro independente do momentum.'
        )
    else:
        cda, cdb = st.columns(2)
        with cda:
            texto = f'↑ +{dist_a:.1f}%' if dist_a is not None else '↑ sem gatilho em ±20%'
            st.markdown(
                f'<div style="background:#f0faf5;border:1px solid #cdeedd;border-radius:8px;'
                f'padding:.6rem .9rem;font-size:14px;color:#1a7a4a;font-weight:600">{texto}</div>',
                unsafe_allow_html=True
            )
        with cdb:
            texto = f'↓ −{abs(dist_b):.1f}%' if dist_b is not None else '↓ sem gatilho em ±20%'
            st.markdown(
                f'<div style="background:#fce8e8;border:1px solid #f3c9c9;border-radius:8px;'
                f'padding:.6rem .9rem;font-size:14px;color:#b83232;font-weight:600">{texto}</div>',
                unsafe_allow_html=True
            )

    st.divider()

    # ── Linha 2: gauge do score + tabela de sinais ─────────────────────────────
    col_gauge, col_sinais = st.columns([1, 1])

    with col_gauge:
        fig_gauge = go.Figure(go.Indicator(
            mode='gauge+number',
            value=score_atual,
            title={'text': 'Score vigente', 'font': {'size': 14}},
            number={'font': {'size': 36, 'color': score_color(score_atual)}},
            gauge={
                'axis': {'range': [-3, 3], 'tickvals': [-3, -1, 0, 1, 2, 3],
                         'ticktext': ['-3', '-1', '0', '+1', '+2', '+3'],
                         'tickfont': {'size': 11}},
                'bar': {'color': score_color(score_atual), 'thickness': 0.25},
                'bgcolor': '#f5f4f0',
                'borderwidth': 1,
                'bordercolor': '#e0ddd5',
                'steps': [
                    {'range': [-3, -1], 'color': '#fce8e8'},
                    {'range': [-1,  0], 'color': '#fff5f0'},
                    {'range': [ 0,  1], 'color': '#f5f4f0'},
                    {'range': [ 1,  2], 'color': '#f0faf5'},
                    {'range': [ 2,  3], 'color': '#e6f5ed'},
                ],
                'threshold': {
                    'line': {'color': score_color(score_proj), 'width': 3},
                    'thickness': 0.75,
                    'value': score_proj
                }
            }
        ))
        fig_gauge.update_layout(
            height=220, margin=dict(t=30, b=10, l=20, r=20),
            font={'family': 'system-ui'}
        )
        st.plotly_chart(fig_gauge, use_container_width=True)
        st.caption(f'Linha tracejada = score projetado ({score_proj})')

    with col_sinais:
        st.markdown('**Sinais de momentum**')

        sinais_df = pd.DataFrame([
            {
                'Sinal': 'MOM 4 semanas (sexta)',
                'Valor': f'{d["mom4w_sexta"]:+.2f}%',
                'Estado': '↑ Positivo' if d['mom4w_sexta'] > 0 else '↓ Negativo',
                'Cor': 'green' if d['mom4w_sexta'] > 0 else 'red'
            },
            {
                'Sinal': 'MOM 8 semanas (sexta)',
                'Valor': f'{d["mom8w_sexta"]:+.2f}%',
                'Estado': '↑ Positivo' if d['mom8w_sexta'] > 0 else '↓ Negativo',
                'Cor': 'green' if d['mom8w_sexta'] > 0 else 'red'
            },
            {
                'Sinal': 'MOM 4 semanas (proj.)',
                'Valor': f'{d["mom4w_proj"]:+.2f}%',
                'Estado': '↑ Positivo' if d['mom4w_proj'] > 0 else '↓ Negativo',
                'Cor': 'green' if d['mom4w_proj'] > 0 else 'red'
            },
            {
                'Sinal': 'MOM 8 semanas (proj.)',
                'Valor': f'{d["mom8w_proj"]:+.2f}%',
                'Estado': '↑ Positivo' if d['mom8w_proj'] > 0 else '↓ Negativo',
                'Cor': 'green' if d['mom8w_proj'] > 0 else 'red'
            },
            {
                'Sinal': 'Breadth 100d',
                'Valor': f'{d["breadth_100d"]:.1f}%',
                'Estado': (
                    '🔴 Colapso (<5%)' if d['breadth_100d'] < 5
                    else '🟡 Capitulação (5–20%)' if d['breadth_100d'] < 20
                    else '🟠 Stress (20–40%)' if d['breadth_100d'] < 40
                    else '⚪ Zona morta (40–60%)' if d['breadth_100d'] < 60
                    else '🟢 Saudável (>60%)'
                ),
                'Cor': 'gray'
            },
            {
                'Sinal': 'Direção breadth (Δ2w)',
                'Valor': f'{d["breadth_delta2w"]:+.1f}pp',
                'Estado': '↑ Melhorando' if d['breadth_delta2w'] > 0 else '↓ Deteriorando',
                'Cor': 'green' if d['breadth_delta2w'] > 0 else 'red'
            },
        ])

        # Exibe como tabela simples com cores
        for _, row in sinais_df.iterrows():
            icon = '🟢' if row['Cor'] == 'green' else '🔴' if row['Cor'] == 'red' else '⚪'
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:4px 0;border-bottom:1px solid #f0ede6;font-size:13px">'
                f'<span style="color:#6b6b65">{row["Sinal"]}</span>'
                f'<span>{icon} <b>{row["Valor"]}</b> &nbsp; <span style="color:#9b9b95;font-size:11px">{row["Estado"]}</span></span>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.divider()

    # ── Linha 3: tabela de quadrantes momentum × breadth ───────────────────────
    st.markdown('**Mapa de quadrantes — Momentum × Breadth (modelo C3b)**')
    st.caption('A célula destacada é o estado momentum×breadth projetado (hoje).')

    linha_atual = _momentum_state_index(d['mom4w_proj'], d['mom8w_proj'])
    coluna_atual = _breadth_bucket_index(d['breadth_100d'], d['breadth_delta2w'])

    header_cells = ''.join(
        f'<th style="padding:8px 6px;font-size:10px;text-align:center;'
        f'white-space:pre-line;color:#64748B;border-bottom:2px solid #e0ddd5">{label}</th>'
        for label in BREADTH_BUCKETS
    )
    linhas_html = ''
    for i, row_label in enumerate(MOMENTUM_STATES):
        celulas = ''
        for j in range(len(BREADTH_BUCKETS)):
            score_cel = QUADRANTE_SCORES[i][j]
            is_atual = (i == linha_atual and j == coluna_atual)
            bg = score_color(score_cel) if is_atual else '#fafaf8'
            fg = '#fff' if is_atual else score_color(score_cel)
            borda = '3px solid #1E5FAD' if is_atual else '1px solid #eceae4'
            celulas += (
                f'<td style="padding:8px 4px;text-align:center;background:{bg};'
                f'border:{borda};font-weight:700;font-size:13px;color:{fg}">{score_cel:+d}</td>'
            )
        linhas_html += (
            f'<tr><td style="padding:6px 8px;font-size:11px;color:#475569;'
            f'white-space:nowrap">{row_label}</td>{celulas}</tr>'
        )

    st.markdown(
        f'<table style="width:100%;border-collapse:collapse;margin-top:6px">'
        f'<thead><tr><th></th>{header_cells}</tr></thead>'
        f'<tbody>{linhas_html}</tbody></table>',
        unsafe_allow_html=True
    )
    st.caption('Quadro em destaque = combinação momentum×breadth vigente agora (usando dados projetados).')

    st.divider()


# ── Standalone (para teste sem dashboard principal) ────────────────────────────
if __name__ == '__main__':
    st.set_page_config(page_title='Score Momentum Ibov', layout='wide')

    # Dados de exemplo para visualizar sem Bloomberg/Supabase
    dados_exemplo = pd.DataFrame([{
        'timestamp':            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_referencia':      datetime.now().strftime('%Y-%m-%d'),
        'score_atual':          0,
        'estado_descricao':     'Neutro — sem convicção direcional',
        'score_projetado':      0,
        'estado_proj_desc':     'Neutro — sem convicção direcional',
        'score_mudou':          False,
        'ibov_pts_sexta':       171000.0,
        'ibov_pts_atual':       170488.0,
        'variacao_semana_pct':  -0.89,
        'mom4w_sexta':          0.52,
        'mom8w_sexta':          -2.97,
        'mom4w_proj':           1.28,
        'mom8w_proj':           -3.25,
        'breadth_100d':         19.2,
        'breadth_delta2w':      -7.7,
        'dist_alta_pct':        None,
        'dist_baixa_pct':       None,
    }])

    render_momentum_score(dados=dados_exemplo)
