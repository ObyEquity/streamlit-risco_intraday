# -*- coding: utf-8 -*-
"""Dashboard Streamlit — Risco Intraday · OBY Capital"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date
from supabase_client import supabase

st.set_page_config(page_title="Risco Intraday · OBY Capital", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

SCHEMA = "risco_intraday"
REFRESH_MS = 180_000
FUNDOS_ORDEM = ["LO1", "LSH1", "LSH2", "LS Total"]
COR_FUNDO = {"LO1": "#3B82F6", "LSH1": "#10B981", "LSH2": "#8B5CF6", "LS Total": "#F59E0B"}

st.markdown("""<style>
html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0A0E1A; color: #E2E8F0; }
.block-container { padding-top: 1.5rem; max-width: 1600px; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 1px solid #1E293B;
    background: transparent;
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    font-size: .78rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
    color: #64748B; padding: .45rem 1rem; border-radius: 6px 6px 0 0;
    border-bottom: 2px solid transparent; background: transparent;
}
.stTabs [data-baseweb="tab"]:hover { color: #CBD5E1; background: #1E293B; }
.stTabs [aria-selected="true"] {
    color: #F1F5F9 !important;
    background: #1E3A5F !important;
    border-bottom: 2px solid #3B82F6 !important;
    border-radius: 6px 6px 0 0 !important;
}

/* Metric cards */
.mc { background: #111827; border: 1px solid #1E293B; border-radius: 10px; padding: 1rem 1.25rem; min-height: 90px; }
.ml { font-size: .72rem; font-weight: 600; letter-spacing: .07em; text-transform: uppercase; color: #475569; margin-bottom: .35rem; }
.mv { font-size: 1.5rem; font-weight: 300; letter-spacing: -.02em; }
.ms { font-size: .72rem; color: #475569; margin-top: .2rem; }
.pos { color: #10B981; } .neg { color: #F87171; } .neu { color: #94A3B8; }

/* Section titles */
.st { font-size: .72rem; font-weight: 600; letter-spacing: .1em; text-transform: uppercase;
      color: #94A3B8; margin: 1.5rem 0 .75rem 0; padding-bottom: .5rem; border-bottom: 1px solid #1E293B; }

/* Header */
.hdr { display: flex; align-items: center; justify-content: space-between;
       padding: .75rem 0 1.25rem 0; border-bottom: 1px solid #1E3A5F; margin-bottom: 1.5rem; }
.logo { font-size: 1.05rem; font-weight: 800; letter-spacing: .12em; color: #1D4ED8; text-transform: uppercase; }
.ttl { font-size: 1.4rem; font-weight: 300; color: #94A3B8; letter-spacing: -.01em; margin-top: .1rem; }
.hra { font-size: .75rem; color: #64748B; text-align: right; line-height: 2; white-space: nowrap; }
.hra span { display: block; font-size: 1.25rem; font-weight: 700; color: #E2E8F0; letter-spacing: -.01em; }
/* Botão refresh discreto */
div[data-testid="stButton"] button {
    background: transparent;
    border: 1px solid #1E3A5F;
    color: #475569;
    font-size: .72rem;
    font-weight: 500;
    letter-spacing: .05em;
    padding: .25rem .75rem;
    border-radius: 6px;
    transition: all .15s;
}
div[data-testid="stButton"] button:hover {
    border-color: #3B82F6;
    color: #94A3B8;
    background: #0F172A;
}
</style>""", unsafe_allow_html=True)

@st.cache_data(ttl=170)
def load(table, cols="*"):
    try:
        r = supabase.schema(SCHEMA).table(table).select(cols).execute()
        return pd.DataFrame(r.data) if r.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar {table}: {e}")
        return pd.DataFrame()

def filt(df, d):
    if not df.empty and "data_referencia" in df.columns:
        return df[df["data_referencia"] == d]
    return df

def pct(v, dec=2):
    if pd.isna(v): return "—"
    return f"{v*100:.{dec}f}%"

PL = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter,sans-serif", color="#94A3B8", size=11),
    margin=dict(l=0,r=60,t=28,b=0),
    xaxis=dict(gridcolor="#1E293B", zerolinecolor="#1E293B"),
    yaxis=dict(gridcolor="#1E293B", zerolinecolor="#1E293B"),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)))

try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=REFRESH_MS, key="ar")
except: pass

# carrega
df_res    = load("db_resumo")
df_hora   = load("db_hora")
df_ng     = load("db_net_gross_fundos")
df_exp    = load("db_exposicao_ativos")
df_op     = load("db_table_options")
df_pa     = load("db_perf_att_master")
df_vol    = load("db_volume_intraday")
df_mktcap = load("db_exp_mkt_cap")

d_ref     = df_res["data_referencia"].max() if not df_res.empty and "data_referencia" in df_res.columns else str(date.today())
df_res    = filt(df_res, d_ref); df_ng  = filt(df_ng, d_ref);  df_exp    = filt(df_exp, d_ref)
df_op     = filt(df_op, d_ref);  df_pa  = filt(df_pa, d_ref);  df_mktcap = filt(df_mktcap, d_ref)
hora      = df_hora["hora_risco"].iloc[0] if not df_hora.empty else "—"

st.markdown(f'''<div class="hdr"><div><div class="logo">OBY Capital</div><div class="ttl">Risco Intraday</div></div>
<div class="hra">Última atualização<span>{hora}</span>{d_ref}</div></div>''', unsafe_allow_html=True)

_, col_btn = st.columns([6, 1])
with col_btn:
    if st.button("⟳ Refresh", use_container_width=True, type="secondary"):
        st.cache_data.clear()
        st.rerun()

tab1,tab2,tab3,tab4,tab5 = st.tabs(["RESUMO","EXPOSIÇÃO","OPÇÕES","PERFORMANCE","VOLUME"])

# ── RESUMO
with tab1:
    if df_res.empty:
        st.info("Aguardando dados...")
    else:
        # Medidas de risco + Exposição por setor lado a lado
        col_risco, col_setor = st.columns([3, 2])

        with col_risco:
            st.markdown("<div class='st'>Medidas de risco</div>", unsafe_allow_html=True)
            tbl = df_res[df_res["Fundo"].isin(FUNDOS_ORDEM)].copy()
            tbl["_ord"] = tbl["Fundo"].map({f: i for i, f in enumerate(FUNDOS_ORDEM)})
            tbl = tbl.sort_values("_ord").drop(columns="_ord")

            def cor_val(v):
                try:
                    n = float(v.replace("%",""))
                    if n > 0: return "color:#34D399;font-weight:500"
                    if n < 0: return "color:#FB7185;font-weight:500"
                except: pass
                return "color:#E2E8F0;font-weight:400"

            cols_tbl = ["Fundo","Retorno","TE","Net","Gross","Beta","BVaR","CVaR","% Índice"]
            html = '<table style="width:100%;border-collapse:collapse;font-size:.84rem;">'
            html += '<thead><tr style="background:#0F172A">'
            for c in cols_tbl:
                html += f'<th style="text-align:left;padding:8px 12px;border-bottom:2px solid #1E3A5F;color:#94A3B8;font-weight:700;font-size:.7rem;letter-spacing:.07em;text-transform:uppercase">{c}</th>'
            html += "</tr></thead><tbody>"
            for i_row, (_, r) in enumerate(tbl.iterrows()):
                bg = "#111827" if i_row % 2 == 0 else "#0F172A"
                vals = {
                    "Fundo": r["Fundo"], "Retorno": pct(r["Retorno"]), "TE": pct(r["TE"]),
                    "Net": pct(r["Net"]), "Gross": pct(r["Gross"]),
                    "Beta": f"{r['Beta']*100:.1f}%" if pd.notna(r["Beta"]) else "—",
                    "BVaR": pct(r["BVaR"]), "CVaR": pct(r["CVaR"]), "% Índice": pct(r["% Índice"]),
                }
                html += f'<tr style="background:{bg}">'
                for i_col, c in enumerate(cols_tbl):
                    v = vals[c]
                    base = f"padding:9px 12px;border-bottom:1px solid #1E293B;"
                    if i_col == 0:
                        style = base + "color:#CBD5E1;font-weight:700;letter-spacing:.03em;"
                    else:
                        style = base + cor_val(v) + ";"
                    html += f'<td style="{style}">{v}</td>'
                html += "</tr>"
            html += "</tbody></table>"
            st.markdown(html, unsafe_allow_html=True)

        with col_setor:
            st.markdown("<div class='st'>Exposição net por setor</div>", unsafe_allow_html=True)
            if not df_exp.empty:
                fundos_disp = [f for f in FUNDOS_ORDEM if f in df_exp["fundo"].unique()]
                sp = (df_exp.groupby(["subsetor","fundo"])["exposure_net"].sum().reset_index()
                      .pivot(index="subsetor", columns="fundo", values="exposure_net")
                      .reindex(columns=fundos_disp).fillna(0))
                sort_col = "LSH1" if "LSH1" in sp.columns else sp.columns[0]
                sp = sp.reindex(sp[sort_col].sort_values(ascending=False).index)
                st.dataframe(
                    sp * 100,
                    use_container_width=True,
                    height=385,
                    column_config={f: st.column_config.NumberColumn(format="%.2f%%") for f in sp.columns}
                )

        # Exposição net por ativo par — fundos nas colunas
        st.markdown("<div class='st'>Exposição net por ativo par</div>", unsafe_allow_html=True)
        if not df_exp.empty:
            fundos_disp = [f for f in FUNDOS_ORDEM if f in df_exp["fundo"].unique()]
            ep = (df_exp.groupby(["ativo_par","fundo"])["exposure_net"].sum().reset_index()
                  .pivot(index="ativo_par", columns="fundo", values="exposure_net")
                  .reindex(columns=fundos_disp).fillna(0))
            sort_col = "LSH1" if "LSH1" in ep.columns else ep.columns[0]
            ep = ep.reindex(ep[sort_col].sort_values(ascending=False).index)
            st.dataframe(
                ep * 100,
                use_container_width=True,
                height=575,
                column_config={f: st.column_config.NumberColumn(format="%.2f%%") for f in ep.columns}
            )

        # Exposição por market cap + Small caps — lado a lado
        st.markdown("<div class='st'>Exposição por market cap &nbsp;·&nbsp; Small caps por ativo</div>", unsafe_allow_html=True)
        if not df_mktcap.empty:
            FUNDOS_MC = [f for f in ["LO1","LSH1","LSH2"] if f in df_mktcap["fundo"].unique()]

            def cat_mc(v):
                if pd.isna(v): return "Sem dados"
                if v < 10_000:  return "Small (< R$10bi)"
                if v < 30_000:  return "Mid (R$10-30bi)"
                return "Large (> R$30bi)"

            mc = df_mktcap[df_mktcap["fundo"].isin(FUNDOS_MC)].copy()
            mc = mc[mc["subsetor"] != "ETF"].copy()
            mc["categoria"] = mc["mkt_cap"].apply(cat_mc)

            col_mc, col_sm = st.columns(2)

            # ── Gráfico market cap (empilhado por categoria, barras = fundos)
            with col_mc:
                mc_agg = (mc.groupby(["fundo","categoria"])["exposure_net"]
                          .sum().reset_index())
                mc_agg["exposure_pct"] = mc_agg["exposure_net"] * 100

                CATS = ["Large (> R$30bi)", "Mid (R$10-30bi)", "Small (< R$10bi)"]
                COR_CAT = {
                    "Large (> R$30bi)": "#3B82F6",
                    "Mid (R$10-30bi)":  "#8B5CF6",
                    "Small (< R$10bi)": "#F59E0B",
                }

                fig_mc = go.Figure()
                for cat in CATS:
                    df_cat = (pd.DataFrame({"fundo": FUNDOS_MC})
                              .merge(mc_agg[mc_agg["categoria"] == cat], on="fundo", how="left")
                              .fillna(0))
                    fig_mc.add_trace(go.Bar(
                        name=cat, x=df_cat["fundo"], y=df_cat["exposure_pct"],
                        marker_color=COR_CAT[cat],
                        text=[f"{v:.1f}%" for v in df_cat["exposure_pct"]],
                        textposition="inside", textfont=dict(size=13, color="#F1F5F9"),
                    ))

                # annotations de soma total por fundo
                totais_mc = mc_agg.groupby("fundo")["exposure_pct"].sum()
                annotations_mc = []
                for fundo in FUNDOS_MC:
                    tot = totais_mc.get(fundo, 0)
                    pos_sum = mc_agg[(mc_agg["fundo"]==fundo) & (mc_agg["exposure_pct"]>0)]["exposure_pct"].sum()
                    annotations_mc.append(dict(
                        x=fundo, y=pos_sum,
                        text=f"<b>{tot:.1f}%</b>",
                        showarrow=False, yanchor="bottom",
                        font=dict(size=13, color="#1E293B"),
                        bgcolor="#F1F5F9",
                        borderpad=3,
                        yshift=6,
                    ))

                fig_mc.update_layout(**{**PL,
                    "barmode": "relative", "height": 380,
                    "showlegend": True,
                    "annotations": annotations_mc,
                    "legend": dict(bgcolor="rgba(0,0,0,0)", orientation="h",
                                   yanchor="bottom", y=1.02, font=dict(size=11)),
                    "yaxis": dict(gridcolor="#1E293B", ticksuffix="%", zerolinecolor="#334155",
                                  tickfont=dict(size=11)),
                    "xaxis": dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=12)),
                    "margin": dict(l=0, r=0, t=50, b=20),
                })
                st.plotly_chart(fig_mc, use_container_width=True)

            # ── Gráfico small caps (empilhado por ativo, barras = fundos)
            with col_sm:
                small = mc[mc["categoria"] == "Small (< R$10bi)"].copy()
                small["exposure_total"] = small["exposure_cash"] + small["exposure_opcao"]
                small = small[small["exposure_total"] != 0]

                if small.empty:
                    st.info("Nenhuma posição em small caps.")
                else:
                    # ativos ordenados por maior absoluto cross-fundo
                    ordem_ativos = (small.groupby("codigo_ativo")["exposure_total"]
                                    .apply(lambda x: x.abs().sum())
                                    .sort_values(ascending=False)
                                    .head(12).index.tolist())

                    fig_sm = go.Figure()
                    for ativo in ordem_ativos:
                        df_a = (pd.DataFrame({"fundo": FUNDOS_MC})
                                .merge(small[small["codigo_ativo"] == ativo][["fundo","exposure_total"]],
                                       on="fundo", how="left")
                                .fillna(0))
                        fig_sm.add_trace(go.Bar(
                            name=ativo,
                            x=df_a["fundo"],
                            y=df_a["exposure_total"] * 100,
                            text=[f"{v:.1f}%" if v != 0 else "" for v in df_a["exposure_total"] * 100],
                            textposition="inside",
                            textfont=dict(size=11, color="#F1F5F9"),
                        ))

                    # annotations de soma total por fundo
                    totais_sm = (small.groupby("fundo")["exposure_total"].sum() * 100)
                    annotations_sm = []
                    for fundo in FUNDOS_MC:
                        tot = totais_sm.get(fundo, 0)
                        pos_sum = (small[small["fundo"]==fundo]["exposure_total"]
                                   .clip(lower=0).sum() * 100)
                        annotations_sm.append(dict(
                            x=fundo, y=pos_sum,
                            text=f"<b>{tot:.1f}%</b>",
                            showarrow=False, yanchor="bottom",
                            font=dict(size=13, color="#1E293B"),
                            bgcolor="#F1F5F9",
                            borderpad=3,
                            yshift=6,
                        ))

                    fig_sm.update_layout(**{**PL,
                        "barmode": "relative", "height": 380,
                        "showlegend": True,
                        "annotations": annotations_sm,
                        "legend": dict(bgcolor="rgba(0,0,0,0)", orientation="h",
                                       yanchor="bottom", y=1.02, font=dict(size=10)),
                        "yaxis": dict(gridcolor="#1E293B", ticksuffix="%", zerolinecolor="#334155",
                                      tickfont=dict(size=11)),
                        "xaxis": dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(size=12)),
                        "margin": dict(l=0, r=0, t=50, b=20),
                    })
                    st.plotly_chart(fig_sm, use_container_width=True)

# ── EXPOSIÇÃO
with tab2:
    if df_exp.empty:
        st.info("Aguardando dados...")
    else:
        c_sel,c_busca = st.columns([2,3])
        with c_sel: fundo_sel = st.selectbox("Fundo",FUNDOS_ORDEM,key="fe")
        with c_busca: busca = st.text_input("Buscar ativo",placeholder="PETR, AZZA...",key="be")

        exp_f = df_exp[df_exp["fundo"]==fundo_sel].copy()
        if busca: exp_f = exp_f[exp_f["ativo_par"].str.contains(busca.upper(),na=False) |
                                 exp_f["codigo_ativo"].str.contains(busca.upper(),na=False)]

        # agrupa por ativo_par
        exp_par = (exp_f.groupby(["ativo_par","subsetor"]).agg(
            exposure_cash=("exposure_cash","sum"),
            exposure_opcao=("exposure_opcao","sum"),
            exposure_net=("exposure_net","sum"),
            beta_ajustado=("beta_ajustado","sum"),
        ).reset_index().sort_values("exposure_net", ascending=False))

        c1,c2 = st.columns([1, 1])
        with c1:
            st.markdown("<div class='st'>Por ativo par</div>", unsafe_allow_html=True)
            t = exp_par[["ativo_par","subsetor","exposure_cash","exposure_opcao","exposure_net","beta_ajustado"]].copy()
            t.columns=["Par","Setor","Cash","Opção","Net","Beta"]
            t["Cash"]  = t["Cash"]  * 100
            t["Opção"] = t["Opção"] * 100
            t["Net"]   = t["Net"]   * 100
            t["Beta"]  = t["Beta"]  * 100
            st.dataframe(
                t.set_index("Par"),
                use_container_width=True,
                height=680,
                column_config={
                    "Cash":  st.column_config.NumberColumn(format="%.2f%%"),
                    "Opção": st.column_config.NumberColumn(format="%.2f%%"),
                    "Net":   st.column_config.NumberColumn(format="%.2f%%"),
                    "Beta":  st.column_config.NumberColumn(format="%.1f%%"),
                }
            )

        with c2:
            st.markdown("<div class='st'>Por setor</div>", unsafe_allow_html=True)
            sa = exp_par.groupby("subsetor")["exposure_net"].sum().reset_index().sort_values("exposure_net")
            cores = ["#34D399" if v>=0 else "#FB7185" for v in sa["exposure_net"]]
            fig = go.Figure(go.Bar(y=sa["subsetor"],x=sa["exposure_net"]*100,orientation="h",marker_color=cores,
                text=[f"{v*100:.1f}%" for v in sa["exposure_net"]],textposition="outside",textfont=dict(size=10,color="#94A3B8")))
            fig.update_layout(**{**PL,"height":340,"xaxis":dict(gridcolor="#1E293B",ticksuffix="%",zerolinecolor="#334155"),
                "yaxis":dict(gridcolor="rgba(0,0,0,0)",tickfont=dict(size=10)),
                "margin":dict(l=0,r=60,t=10,b=0)})
            st.plotly_chart(fig,use_container_width=True)

            if not df_op.empty:
                op_fundo = df_op[df_op["fundo"] == fundo_sel]
                if not op_fundo.empty:
                    st.markdown("<div class='st'>Exposição por opções</div>", unsafe_allow_html=True)
                    oo = op_fundo.groupby("ativo_objeto")["exposure"].sum().reset_index().sort_values("exposure")
                    cores_op = ["#34D399" if v>=0 else "#FB7185" for v in oo["exposure"]]
                    fig_op = go.Figure(go.Bar(
                        y=oo["ativo_objeto"], x=oo["exposure"]*100,
                        orientation="h", marker_color=cores_op,
                        text=[f"{v*100:.1f}%" for v in oo["exposure"]],
                        textposition="outside", textfont=dict(size=10, color="#94A3B8"),
                    ))
                    fig_op.update_layout(**{**PL,"height":280,
                        "xaxis":dict(gridcolor="#1E293B",ticksuffix="%",zerolinecolor="#334155"),
                        "yaxis":dict(gridcolor="rgba(0,0,0,0)",tickfont=dict(size=10)),
                        "margin":dict(l=0,r=60,t=10,b=0)})
                    st.plotly_chart(fig_op,use_container_width=True)

# ── OPÇÕES
with tab3:
    if df_op.empty:
        st.info("Sem dados de opções.")
    else:
        st.markdown("<div class='st'>Carteira — preço Black-Scholes</div>", unsafe_allow_html=True)
        fo = [f for f in ["LO1","LSH1","LSH2"] if f in df_op["fundo"].unique()]
        pv = df_op[df_op["fundo"].isin(fo)].pivot_table(
            index="codigo_ativo", columns="fundo", values="quantidade_hoje", aggfunc="sum"
        ).reindex(columns=fo)
        pv["Soma"] = pv.sum(axis=1)
        pv.insert(0,"Preço",df_op.groupby("codigo_ativo")["preco_hoje"].first())
        dp = pv.copy()
        dp["Preço"] = dp["Preço"].apply(lambda v: f"{v:.2f}" if pd.notna(v) else "—")
        for c in [col for col in dp.columns if col != "Preço"]:
            dp[c] = dp[c].apply(lambda v: f"{int(v):,}" if pd.notna(v) and v != 0 else "—")
        st.dataframe(dp, use_container_width=True)

        st.markdown("<div class='st'>Detalhe</div>", unsafe_allow_html=True)
        fop = st.selectbox("Fundo",fo,key="fop")
        det = df_op[df_op["fundo"]==fop][["codigo_ativo","ativo_objeto","tipo_opcao","data_expire",
            "spot","strike","vol","preco_hoje","delta","quantidade_hoje","exposure","exposure_bps"]].copy()
        det.columns=["Opção","Objeto","Tipo","Vcto","Spot","Strike","Vol","Preço BS","Delta","Qtd","Exposure","BPS"]
        det["Exposure"] = det["Exposure"] * 100
        st.dataframe(
            det.set_index("Opção"), use_container_width=True,
            column_config={
                "Vol":      st.column_config.NumberColumn(format="%.1f%%"),
                "Exposure": st.column_config.NumberColumn(format="%.2f%%"),
                "BPS":      st.column_config.NumberColumn(format="%.2f"),
                "Delta":    st.column_config.NumberColumn(format="%.4f"),
                "Preço BS": st.column_config.NumberColumn(format="%.4f"),
                "Spot":     st.column_config.NumberColumn(format="%.2f"),
                "Strike":   st.column_config.NumberColumn(format="%.2f"),
                "Qtd":      st.column_config.NumberColumn(format="%d"),
            }
        )

# ── PERFORMANCE
with tab4:
    if df_pa.empty:
        st.info("Aguardando dados...")
    else:
        fpa = st.selectbox("Fundo",[f for f in FUNDOS_ORDEM if f in df_pa["fundo"].unique()],key="fpa")
        pa = df_pa[df_pa["fundo"]==fpa].sort_values("contrib_dia",ascending=False)
        tot=pa["contrib_dia"].sum(); tc=pa["contrib_dia_cash"].sum(); to=pa["contrib_dia_opcao"].sum()
        c1,c2,c3 = st.columns(3)
        for cst,val,lbl in [(c1,tot,"Total"),(c2,tc,"Cash + Fut"),(c3,to,"Opções")]:
            cls="pos" if val>0 else "neg"
            with cst:
                st.markdown(f'''<div class="mc"><div class="ml">{lbl}</div><div class="mv {cls}">{pct(val,3)}</div></div>''',unsafe_allow_html=True)
        cl,cr = st.columns(2)
        with cl:
            st.markdown("<div class='st'>Por papel</div>", unsafe_allow_html=True)
            tp = pa[["ativo_par","subsetor","contrib_dia","contrib_dia_cash","contrib_dia_opcao"]].copy()
            tp.columns=["Par","Setor","Total","Cash/Fut","Opção"]
            tp["Total"]    = tp["Total"]    * 100
            tp["Cash/Fut"] = tp["Cash/Fut"] * 100
            tp["Opção"]    = tp["Opção"]    * 100
            st.dataframe(
                tp.set_index("Par"), use_container_width=True, height=420,
                column_config={
                    "Total":    st.column_config.NumberColumn(format="%.3f%%"),
                    "Cash/Fut": st.column_config.NumberColumn(format="%.3f%%"),
                    "Opção":    st.column_config.NumberColumn(format="%.3f%%"),
                }
            )
        with cr:
            st.markdown("<div class='st'>Por setor</div>", unsafe_allow_html=True)
            sp=pa.groupby("subsetor")["contrib_dia"].sum().reset_index().sort_values("contrib_dia")
            cp=["#10B981" if v>=0 else "#F87171" for v in sp["contrib_dia"]]
            fp=go.Figure(go.Bar(y=sp["subsetor"],x=sp["contrib_dia"]*100,orientation="h",marker_color=cp,
                text=[f"{v*100:.2f}%" for v in sp["contrib_dia"]],textposition="outside",textfont=dict(size=9,color="#94A3B8")))
            fp.update_layout(**{**PL,"height":420,"xaxis":dict(gridcolor="#1E293B",ticksuffix="%",zerolinecolor="#334155"),
                "yaxis":dict(gridcolor="rgba(0,0,0,0)",tickfont=dict(size=10))})
            st.plotly_chart(fp,use_container_width=True)

# ── VOLUME
with tab5:
    if df_vol.empty:
        st.info("Aguardando dados...")
    else:
        st.markdown("<div class='st'>V/ADTV 30d — ranking</div>", unsafe_allow_html=True)
        dv=df_vol.sort_values("V/ADTV 30D",ascending=False)
        c1,c2=st.columns([1,2])
        with c1:
            tv = dv[["Ativo","V/ADTV 30D","VOLUME","VOLUME_AVG_30D"]].copy()
            tv["VOLUME"]         = tv["VOLUME"] / 1e6
            tv["VOLUME_AVG_30D"] = tv["VOLUME_AVG_30D"] / 1e6
            tv.columns = ["Ativo","V/ADTV","Vol. Hoje (R$M)","ADTV 30d (R$M)"]
            st.dataframe(
                tv.set_index("Ativo"), use_container_width=True, height=520,
                column_config={
                    "V/ADTV":          st.column_config.NumberColumn(format="%.2fx"),
                    "Vol. Hoje (R$M)": st.column_config.NumberColumn(format="R$ %.0fM"),
                    "ADTV 30d (R$M)":  st.column_config.NumberColumn(format="R$ %.0fM"),
                }
            )
        with c2:
            top=dv.head(20)
            cv=["#F59E0B" if v>1.5 else ("#10B981" if v>0.8 else "#475569") for v in top["V/ADTV 30D"]]
            fv=go.Figure(go.Bar(y=top["Ativo"],x=top["V/ADTV 30D"],orientation="h",marker_color=cv,
                text=[f"{v:.1f}x" for v in top["V/ADTV 30D"]],textposition="outside",textfont=dict(size=9,color="#94A3B8")))
            fv.add_vline(x=1.0,line_dash="dash",line_color="#334155",line_width=1)
            fv.update_layout(**{**PL,"height":540,"xaxis":dict(gridcolor="#1E293B",ticksuffix="x",zerolinecolor="#334155"),
                "yaxis":dict(gridcolor="rgba(0,0,0,0)",tickfont=dict(size=10))})
            st.plotly_chart(fv,use_container_width=True)
