# -*- coding: utf-8 -*-
"""
perf_att_core.py

Módulo de agregação de Performance Attribution por período.

Substitui a lógica de soma linear (`cumsum`) do legado `Performance_Attribution.py`
por suavização de Cariño (1999), que garante que a soma das contribuições
diárias suavizadas de um período seja EXATAMENTE igual ao retorno composto
real do fundo naquele período — sem "check" manual de divergência.

Também resolve a integração FIC vs Master: `db_perf_att_master` é calculado
sobre a carteira "Master" (bruta, sem taxas). A diferença entre o retorno
Master e o retorno FIC (líquido de tx_adm/tx_pfee) vira uma linha sintética
de contribuição ("Custos e Taxas"), suavizada com o mesmo método, de forma
que a soma final bate com a cota líquida do FIC (a que o cotista realmente vê).

Fontes:
    - risco.db_perf_att_master      (contrib_dia por ativo_par/subsetor, nível Master)
    - resultados.db_resultados_fundos (rent_dia Master e FIC, tx_adm_dia, tx_pfee_dia)

Uso típico:
    fa = funcoesAuxiliares(delta_dias=0)
    df = monta_perf_att_periodo(fa, fundo='LO1', data_inicio='2026-06-01', data_fim='2026-06-30')
    tabela, check = agrega_perf_att(df, agrupar_por='subsetor')
"""

import numpy as np
import pandas as pd

FUNDOS_VALIDOS = ['LO1', 'LSH1', 'LSH2', 'LS Total', 'OO1']  # OH1 fica de fora (tratamento à parte)

# Fundos cujo contrib_dia em db_perf_att_master já é RELATIVO ao benchmark
# (ver Risco_New_Supabase.py: "if fundo in fundos_lo: cota_fundo = cota_fundo - ret_ibov").
# Para esses fundos, a soma diária de contrib_dia fecha contra (cota_fundo - ret_bench),
# não contra a cota bruta do fundo -- então a reconciliação de período precisa somar de
# volta o retorno do benchmark para fechar contra a cota FIC total.
FUNDOS_RELATIVOS_BENCHMARK = {
    'LO1': 'IBOV',
}

# tabela/coluna de onde ler cada benchmark suportado (schema public)
BENCHMARKS = {
    'IBOV': {'schema': 'dados_publicos', 'table': 'db_hist_ibovespa', 'filtro_codigo_ativo': 'IBOV', 'coluna_valor': 'valor', 'tipo': 'nivel'},
    'CDI': {'schema': 'public', 'table': 'db_cota_cdi', 'filtro_codigo_ativo': None, 'coluna_valor': 'taxa_over_diaria', 'tipo': 'retorno_pct'},
}

LINHA_CUSTOS = 'Custos e Taxas'
LINHA_BENCHMARK = 'Benchmark'

# Linhas sintéticas / não-ativos de bolsa que não devem entrar no mapa de calor
# (o mapa é só de ativos de renda variável, agrupados por subsetor)
LINHAS_EXCLUIDAS_MAPA = {LINHA_CUSTOS, 'Dif Fut Spot', 'Outros', 'Renda Fixa'}


# --------------------------------------------------------------------------- #
# 1) Carga de dados
# --------------------------------------------------------------------------- #

def carrega_perf_att_master(fa, fundo: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Busca as linhas de contrib_dia por ativo_par/subsetor no período, já filtrado por fundo."""
    df = fa.fetch_data_from_supabase_grandes(
        field_date='data_referencia',
        start_date=data_inicio,
        end_date=data_fim,
        filters=[('fundo', [fundo])],
        schema_name='risco',
        table='db_perf_att_master',
    )
    if df.empty:
        return df
    df['data_referencia'] = pd.to_datetime(df['data_referencia'])
    for col in ['contrib_dia', 'contrib_dia_opcao', 'contrib_dia_cash']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    return df.sort_values('data_referencia').reset_index(drop=True)


def carrega_benchmark(fa, benchmark: str, data_inicio: str, data_fim: str) -> pd.Series:
    """
    Retorna a serie de rent_dia (retorno diario) do benchmark no periodo,
    indexada por data_referencia. Suporta IBOV (nivel, precisa pct_change)
    e CDI (taxa_over_diaria ja e o retorno do dia, em %).

    Busca com um colchao de dias antes de data_inicio para os benchmarks
    de nivel (IBOV), que precisam de um dia anterior para pct_change().
    """
    if benchmark not in BENCHMARKS:
        raise ValueError(f"Benchmark '{benchmark}' nao configurado em BENCHMARKS.")

    cfg = BENCHMARKS[benchmark]
    precisa_colchao = cfg['tipo'] == 'nivel'
    inicio_busca = (
        (pd.Timestamp(data_inicio) - pd.Timedelta(days=10)).date().isoformat()
        if precisa_colchao else data_inicio
    )

    df = fa.fetch_data_from_supabase_grandes(
        field_date='data_referencia',
        start_date=inicio_busca,
        end_date=data_fim,
        schema_name=cfg['schema'],
        table=cfg['table'],
    )
    if df.empty:
        raise ValueError(f"Sem dados em public.{cfg['table']} para o benchmark {benchmark}.")

    if cfg['filtro_codigo_ativo'] is not None:
        df = df[df['codigo_ativo'] == cfg['filtro_codigo_ativo']].copy()
    df['data_referencia'] = pd.to_datetime(df['data_referencia'])
    df = df.sort_values('data_referencia')

    if cfg['tipo'] == 'nivel':
        df['rent_dia'] = pd.to_numeric(df[cfg['coluna_valor']], errors='coerce').pct_change()
    elif cfg['tipo'] == 'retorno_pct':
        df['rent_dia'] = pd.to_numeric(df[cfg['coluna_valor']], errors='coerce') / 100.0
    else:
        df['rent_dia'] = pd.to_numeric(df[cfg['coluna_valor']], errors='coerce')

    serie = df.set_index('data_referencia')['rent_dia']
    return serie[(serie.index >= pd.Timestamp(data_inicio)) & (serie.index <= pd.Timestamp(data_fim))]


def carrega_resultados_fundo(fa, fundo: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Busca rent_dia Master e FIC + tx_adm_dia/tx_pfee_dia no período."""
    df = fa.fetch_data_from_supabase_grandes(
        field_date='data_referencia',
        start_date=data_inicio,
        end_date=data_fim,
        filters=[('fundo', [fundo])],
        schema_name='resultados',
        table='db_resultados_fundos',
    )
    if df.empty:
        return df
    df['data_referencia'] = pd.to_datetime(df['data_referencia'])
    for col in ['rent_dia', 'tx_adm_dia', 'tx_pfee_dia', 'cota']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df.sort_values('data_referencia').reset_index(drop=True)


# --------------------------------------------------------------------------- #
# 2) Suavização de Cariño
# --------------------------------------------------------------------------- #

def fator_carino(r: float) -> float:
    """
    Fator de suavização logarítmica de Cariño para um retorno diário r.
    Para r muito próximo de 0, usa o limite (1/(1+r) ~ 1) para evitar divisão por zero.
    """
    if r is None or pd.isna(r) or abs(r) < 1e-12:
        return 1.0
    return np.log1p(r) / r


def calcula_fatores_periodo(rent_dia: pd.Series) -> pd.Series:
    """
    Recebe a série de retornos diários (rent_dia) de um fundo/linha (Master ou FIC)
    ao longo do período e devolve, para cada dia, o peso de suavização k_t/K a ser
    aplicado sobre a contribuição bruta daquele dia.

    K é o fator de Cariño do retorno TOTAL composto do período inteiro.
    k_t é o fator de Cariño do retorno daquele dia especificamente.
    """
    rent_dia = rent_dia.fillna(0.0)
    retorno_total_periodo = (1.0 + rent_dia).prod() - 1.0
    K = fator_carino(retorno_total_periodo)
    k_t = rent_dia.apply(fator_carino)
    # peso de suavização: k_t / K (adimensional, em torno de 1.0)
    return k_t / K, retorno_total_periodo


# --------------------------------------------------------------------------- #
# 3) Monta o dataset consolidado do período (Master + linha de Custos e Taxas)
# --------------------------------------------------------------------------- #

def monta_perf_att_periodo(fa, fundo: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    """
    Retorna um DataFrame já com a contribuição SUAVIZADA de cada
    ativo_par/subsetor/dia, pronta para agregação por soma simples no período,
    incluindo a linha sintética de Custos e Taxas (drag FIC vs Master).

    Colunas de saída:
        data_referencia, fundo, codigo_ativo, ativo_par, subsetor,
        contrib_dia, contrib_dia_suavizada
    """
    pa = carrega_perf_att_master(fa, fundo, data_inicio, data_fim)
    res = carrega_resultados_fundo(fa, fundo, data_inicio, data_fim)

    if pa.empty:
        return pd.DataFrame(columns=[
            'data_referencia', 'fundo', 'codigo_ativo', 'ativo_par', 'subsetor',
            'contrib_dia', 'contrib_dia_suavizada'
        ])

    if res.empty:
        raise ValueError(
            f"Não há dados em resultados.db_resultados_fundos para {fundo} "
            f"entre {data_inicio} e {data_fim} — impossível suavizar ou reconciliar com a cota FIC."
        )

    res_master = res[res['tipo'] == 'Master'].set_index('data_referencia')
    res_fic = res[res['tipo'] == 'FIC'].set_index('data_referencia')

    # --- Dias "órfãos" (três casos, todos tratados igual: dia descartado dos dois lados) ---
    # 1) pa tem a linha do dia, mas res não tem o par Master+FIC oficial ainda (custodiante
    #    atrasado) -- sem o rent_dia oficial não há como suavizar/reconciliar esse dia.
    # 2) res tem o rent_dia oficial do dia, mas pa NÃO TEM NENHUMA LINHA daquele dia (ex.:
    #    falha pontual do script de risco) -- nesse caso o dia entraria no cálculo do peso/
    #    retorno total via res, mas nenhum ativo carregaria a contribuição dele, quebrando a
    #    identidade exata contrib(t)+custos(t) = rent_dia_fic(t) que a suavização depende.
    # 3) res TEM a linha Master e/ou FIC do dia, mas rent_dia está NULL nela (linha existe,
    #    valor não) -- ex.: custodiante não reportou a cota naquele dia e o pipeline gravou a
    #    linha mesmo assim, com rent_dia em branco. Checar só a EXISTÊNCIA da linha (índice)
    #    não pega esse caso -- por isso exigimos rent_dia não-nulo, não só o dia estar presente.
    # Em todos os casos o dia é descartado dos DOIS lados e reportado para auditoria, em vez de
    # distorcer a soma silenciosamente (ou, pior, um NULL virar 0.0 sem ninguém perceber).
    dias_com_resultado_completo = (
        res_master['rent_dia'].dropna().index.intersection(res_fic['rent_dia'].dropna().index)
    )
    dias_pa = pd.DatetimeIndex(sorted(pa['data_referencia'].unique()))

    dias_orfaos_pa = dias_pa.difference(dias_com_resultado_completo)
    dias_faltantes_pa = dias_com_resultado_completo.difference(dias_pa)

    dias_finais = dias_com_resultado_completo.intersection(dias_pa)

    if len(dias_orfaos_pa) > 0:
        pa = pa[~pa['data_referencia'].isin(dias_orfaos_pa)].copy()

    res_master = res_master.loc[res_master.index.isin(dias_finais)]
    res_fic = res_fic.loc[res_fic.index.isin(dias_finais)]

    if pa.empty:
        raise ValueError(
            f"Depois de descartar dias sem confirmação em db_resultados_fundos, não sobrou "
            f"nenhum dia com dado completo para {fundo} entre {data_inicio} e {data_fim}."
        )

    linhas_extra = []
    dias_bench_ajustados = []

    # --- Peso ÚNICO de suavização, derivado do retorno FIC (o que o cotista de fato recebe) ---
    # Por que um peso só, e não um por série (Master, FIC, benchmark)?
    # Todo dia vale a identidade EXATA: ativo_dia(t) + drag_dia(t) [+ rent_bench(t), se relativo]
    # = rent_dia_fic(t). Suavizando TODOS os componentes desse dia com o MESMO peso k_t(fic)/K(fic),
    # a soma do período inteiro reconstrói R_fic_total exatamente (identidade de Cariño), não
    # importa quantos anos o período tenha. Usar pesos de séries diferentes por componente (como
    # era feito antes: ativos com peso do Master, custos com peso do FIC) é só uma aproximação —
    # válida para janelas curtas, mas que diverge conforme o período cresce e Master/FIC se
    # afastam pelo acúmulo de taxas (foi a causa da divergência de centenas de bps em janelas
    # de vários anos).
    pesos_fic, retorno_fic_periodo_smoothing = calcula_fatores_periodo(res_fic['rent_dia'])
    mapa_peso_fic = pesos_fic.to_dict()

    pa['contrib_dia_suavizada'] = pa.apply(
        lambda row: row['contrib_dia'] * mapa_peso_fic.get(row['data_referencia'], 1.0),
        axis=1,
    )

    retorno_bench_periodo = None

    if fundo in FUNDOS_RELATIVOS_BENCHMARK:
        # --- Caso LO1 (e outros long-only): contrib_dia já é RELATIVO ao benchmark ---
        # Não entra como linha na tabela (visão puramente relativa), mas o retorno do
        # benchmark do período -- suavizado com o MESMO peso do FIC -- é necessário para
        # calcular o alvo de reconciliação de forma EXATA (ver retorno_alvo_periodo abaixo).
        benchmark = FUNDOS_RELATIVOS_BENCHMARK[fundo]

        rent_bench = carrega_benchmark(fa, benchmark, data_inicio, data_fim)

        # Dias em que o FUNDO marcou cota (existe em pa/res_master) mas o benchmark
        # não teve pregão (feriado local, greve na B3 etc.) -- nesses dias o benchmark
        # entra com retorno 0, mas o dia fica registrado para auditoria.
        dias_fundo = pd.DatetimeIndex(sorted(pa['data_referencia'].unique()))
        dias_faltantes_bench = dias_fundo.difference(rent_bench.dropna().index)

        rent_bench = rent_bench.reindex(dias_fundo)
        if len(dias_faltantes_bench) > 0:
            rent_bench.loc[dias_faltantes_bench] = 0.0
            dias_bench_ajustados = [d.date().isoformat() for d in dias_faltantes_bench]

        rent_bench_suavizado = rent_bench.reindex(pesos_fic.index).fillna(0.0) * pesos_fic
        retorno_bench_periodo = rent_bench_suavizado.sum()

    # --- linha sintética de Custos e Taxas: drag = rent_dia_FIC - rent_dia_Master ---
    # (mesmo peso único derivado do FIC, igual aos ativos acima)
    drag_dia = (res_fic['rent_dia'] - res_master['rent_dia']).dropna()

    for data_ref, drag in drag_dia.items():
        linhas_extra.append({
            'data_referencia': data_ref,
            'fundo': fundo,
            'codigo_ativo': LINHA_CUSTOS,
            'ativo_par': LINHA_CUSTOS,
            'subsetor': LINHA_CUSTOS,
            'contrib_dia': drag,
            'contrib_dia_suavizada': drag * mapa_peso_fic.get(data_ref, 1.0),
        })

    df_extra = pd.DataFrame(linhas_extra)

    saida = pd.concat([
        pa[['data_referencia', 'fundo', 'codigo_ativo', 'ativo_par', 'subsetor',
            'contrib_dia', 'contrib_dia_suavizada']],
        df_extra,
    ], ignore_index=True)

    saida.attrs['retorno_master_periodo'] = (1.0 + res_master['rent_dia'].fillna(0)).prod() - 1.0
    saida.attrs['retorno_fic_periodo'] = (1.0 + res_fic['rent_dia'].fillna(0)).prod() - 1.0
    saida.attrs['dias_bench_ajustados'] = dias_bench_ajustados
    saida.attrs['dias_orfaos_descartados'] = [d.date().isoformat() for d in dias_orfaos_pa]
    saida.attrs['dias_faltantes_perf_att'] = [d.date().isoformat() for d in dias_faltantes_pa]

    eh_relativo = fundo in FUNDOS_RELATIVOS_BENCHMARK
    saida.attrs['eh_relativo_benchmark'] = eh_relativo
    if eh_relativo:
        saida.attrs['benchmark'] = FUNDOS_RELATIVOS_BENCHMARK[fundo]
        saida.attrs['retorno_benchmark_periodo'] = retorno_bench_periodo
        # Alvo de reconciliação relativo: R_fic_total menos o benchmark do período, ambos
        # suavizados com o MESMO peso (derivado do FIC) -- por construção, EXATO (ver
        # comentário acima sobre o peso único), não uma aproximação aritmética.
        saida.attrs['retorno_alvo_periodo'] = saida.attrs['retorno_fic_periodo'] - retorno_bench_periodo
    else:
        saida.attrs['retorno_alvo_periodo'] = saida.attrs['retorno_fic_periodo']

    return saida


# --------------------------------------------------------------------------- #
# 3.4) Diagnóstico dia a dia -- acha os DIAS com erro de dado na base
# --------------------------------------------------------------------------- #

def diagnostico_diario(fa, fundo: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    """
    Compara, DIA A DIA (sem suavização de período), o que db_perf_att_master
    diz que os ativos somam vs. o que deveria ser a partir do rent_dia oficial
    em db_resultados_fundos.

    Cobre DOIS tipos de problema:
    1) Dia com linha em db_perf_att_master mas com VALOR errado (soma dos
       ativos não bate com o rent_dia oficial daquele dia) -- ex.: erro de
       cálculo de risco não corrigido, como aconteceu com o LS Total.
    2) Dia com rent_dia oficial em db_resultados_fundos mas SEM NENHUMA
       linha em db_perf_att_master (dia inteiro ausente, não é uma diferença
       de valor) -- ex.: falha pontual do script de risco naquele dia. Esse
       caso é sinalizado separadamente (coluna 'sem_dados_perf_att'), já que
       um diagnóstico que olhasse só os dias existentes em pa nunca o pegaria.

    Em uma soma de vários anos, um único dia de qualquer um desses dois tipos
    já é suficiente para gerar centenas de bps de divergência total.

    Retorna DataFrame ordenado pelo MAIOR |delta| primeiro (dias sem dados
    aparecem no topo, já que ali o delta é o próprio retorno esperado do dia):
        data_referencia, soma_contrib_dia, esperado_dia, delta_dia, delta_bps,
        sem_dados_perf_att
    """
    pa = carrega_perf_att_master(fa, fundo, data_inicio, data_fim)
    res = carrega_resultados_fundo(fa, fundo, data_inicio, data_fim)

    if res.empty:
        return pd.DataFrame(columns=[
            'data_referencia', 'soma_contrib_dia', 'esperado_dia', 'delta_dia',
            'delta_bps', 'sem_dados_perf_att'
        ])

    res_master = res[res['tipo'] == 'Master'].set_index('data_referencia')['rent_dia']
    ativo_dia = pa.groupby('data_referencia')['contrib_dia'].sum() if not pa.empty else pd.Series(dtype=float)

    # União das datas: dias em qualquer uma das duas fontes, não só em pa --
    # é essa união que permite pegar dias 100% ausentes em db_perf_att_master.
    dias_uniao = res_master.index.union(ativo_dia.index)

    if fundo in FUNDOS_RELATIVOS_BENCHMARK:
        benchmark = FUNDOS_RELATIVOS_BENCHMARK[fundo]
        rent_bench = carrega_benchmark(fa, benchmark, data_inicio, data_fim)
        rent_bench = rent_bench.reindex(dias_uniao).fillna(0.0)
        esperado_dia = res_master.reindex(dias_uniao) - rent_bench
    else:
        esperado_dia = res_master.reindex(dias_uniao)

    soma_contrib_dia = ativo_dia.reindex(dias_uniao)  # NaN = dia sem NENHUMA linha em pa

    diagnostico = pd.DataFrame({
        'soma_contrib_dia': soma_contrib_dia,
        'esperado_dia': esperado_dia,
    })
    diagnostico['sem_dados_perf_att'] = diagnostico['soma_contrib_dia'].isna()
    # Para o cálculo do delta, dia sem pa entra como contribuição 0 (não suavizada,
    # é só pra medir o tamanho do buraco) -- mas fica marcado em sem_dados_perf_att.
    diagnostico['soma_contrib_dia'] = diagnostico['soma_contrib_dia'].fillna(0.0)
    diagnostico = diagnostico.dropna(subset=['esperado_dia'])  # sem rent_dia oficial -> não dá pra comparar

    diagnostico['delta_dia'] = diagnostico['soma_contrib_dia'] - diagnostico['esperado_dia']
    diagnostico['delta_bps'] = diagnostico['delta_dia'] * 10000

    diagnostico = diagnostico.reset_index().rename(columns={'index': 'data_referencia'})
    diagnostico = diagnostico.sort_values('delta_bps', key=lambda s: s.abs(), ascending=False).reset_index(drop=True)

    return diagnostico


def diagnostico_acumulado(diagnostico: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe a saída de diagnostico_diario() e devolve o delta diário ORDENADO
    POR DATA (não por |delta|) com uma coluna de delta acumulado no tempo.

    Serve para LOCALIZAR visualmente em que data/período o problema está: ao
    plotar 'delta_bps_acumulado' ao longo do tempo, um salto brusco na linha
    aponta exatamente o dia em que o erro entrou -- muito mais rápido que
    bissecção manual via filtro de datas.
    """
    if diagnostico.empty:
        return diagnostico

    diag_ordenado = diagnostico.sort_values('data_referencia').reset_index(drop=True)
    diag_ordenado['delta_bps_acumulado'] = diag_ordenado['delta_bps'].cumsum()
    return diag_ordenado


# --------------------------------------------------------------------------- #
# 3.5) Cota do fundo (FIC) vs benchmark, no período filtrado
# --------------------------------------------------------------------------- #

def monta_cota_vs_benchmark(fa, fundo: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    """
    Monta a série (base 100) da cota FIC do fundo vs. o retorno do seu benchmark
    no período filtrado, a partir de resultados.db_resultados_fundos (rent_dia FIC
    + coluna 'benchmark' já cadastrada por fundo).

    Retorna DataFrame indexado por data_referencia com colunas:
        'Cota FIC', 'Benchmark (<nome>)'
    """
    res = carrega_resultados_fundo(fa, fundo, data_inicio, data_fim)
    if res.empty:
        raise ValueError(
            f"Não há dados em resultados.db_resultados_fundos para {fundo} "
            f"entre {data_inicio} e {data_fim}."
        )

    res_fic = res[res['tipo'] == 'FIC'].set_index('data_referencia').sort_index()
    if res_fic.empty:
        raise ValueError(f"Não há linhas tipo='FIC' para {fundo} no período.")

    benchmark = res_fic['benchmark'].dropna().iloc[0] if 'benchmark' in res_fic.columns else None
    if benchmark is None:
        raise ValueError(f"Coluna 'benchmark' ausente ou vazia para {fundo}.")

    rent_bench = carrega_benchmark(fa, benchmark, data_inicio, data_fim)
    rent_bench = rent_bench.reindex(res_fic.index).fillna(0.0)  # feriado local -> 0, mesma convenção usada na attribution

    # Usa a coluna 'cota' (nível) diretamente, em vez de reconstruir via cumprod de rent_dia --
    # evita o caso de rent_dia vir NULL num dia em que a cota em si está OK (ex.: custodiante
    # não recalculou rent_dia naquele dia, mas a cota do dia foi reportada normalmente). Um NULL
    # em rent_dia tratado como 0% (fillna) faria o gráfico mostrar retorno flat num dia que na
    # verdade teve movimento -- usar a cota elimina essa dependência por completo.
    if 'cota' in res_fic.columns and res_fic['cota'].notna().any():
        res_fic_valido = res_fic[res_fic['cota'].notna()].sort_index()
        cota_fic = 100.0 * res_fic_valido['cota'] / res_fic_valido['cota'].iloc[0]
    else:
        rent_fic = res_fic['rent_dia'].fillna(0.0)
        cota_fic = 100.0 * (1.0 + rent_fic).cumprod()

    cota_bench = 100.0 * (1.0 + rent_bench.reindex(cota_fic.index).fillna(0.0)).cumprod()

    saida = pd.DataFrame({
        'Cota FIC': cota_fic,
        f'Benchmark ({benchmark})': cota_bench,
    })

    # Âncora em 100 no dia anterior ao início do período -- sem ela, o primeiro ponto
    # plotado já é 100*(1+retorno do 1º dia), o que faz o gráfico "não começar em 100".
    data_ancora = saida.index.min() - pd.Timedelta(days=1)
    linha_ancora = pd.DataFrame(
        {col: 100.0 for col in saida.columns}, index=[data_ancora]
    )
    saida = pd.concat([linha_ancora, saida]).sort_index()
    saida.index.name = 'data_referencia'  # concat com index sem nome zera o name -- reforça aqui

    saida.attrs['benchmark'] = benchmark
    return saida


def agrega_mapa_calor(df_periodo: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega a contribuição suavizada por subsetor > ativo_par, para o mapa de calor
    (treemap), excluindo linhas sintéticas que não são ativos de bolsa
    (Custos e Taxas, Dif Fut Spot, Outros, Renda Fixa).

    Retorna colunas: subsetor, ativo_par, contribuicao_periodo, contribuicao_abs.
    """
    if df_periodo.empty:
        return pd.DataFrame(columns=['subsetor', 'ativo_par', 'contribuicao_periodo', 'contribuicao_abs'])

    df = df_periodo[
        ~df_periodo['ativo_par'].isin(LINHAS_EXCLUIDAS_MAPA)
        & ~df_periodo['subsetor'].isin(LINHAS_EXCLUIDAS_MAPA)
    ]

    tabela = (
        df.groupby(['subsetor', 'ativo_par'], as_index=False)['contrib_dia_suavizada']
        .sum()
        .rename(columns={'contrib_dia_suavizada': 'contribuicao_periodo'})
    )
    tabela['contribuicao_abs'] = tabela['contribuicao_periodo'].abs()
    return tabela.sort_values('contribuicao_abs', ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# 4) Agregação final + reconciliação
# --------------------------------------------------------------------------- #

def agrega_perf_att(df_periodo: pd.DataFrame, agrupar_por: str = 'ativo_par'):
    """
    Agrega a contribuição suavizada por `ativo_par` ou `subsetor` (ou `codigo_ativo`)
    ao longo de TODO o período (soma simples, já que a suavização faz a soma
    ser consistente com o retorno composto).

    Retorna (tabela_agregada, dict_reconciliacao).
    """
    assert agrupar_por in ('ativo_par', 'subsetor', 'codigo_ativo')

    if df_periodo.empty:
        return pd.DataFrame(), {}

    tabela = (
        df_periodo
        .groupby(agrupar_por, as_index=False)['contrib_dia_suavizada']
        .sum()
        .rename(columns={'contrib_dia_suavizada': 'contribuicao_periodo'})
        .sort_values('contribuicao_periodo', ascending=False)
        .reset_index(drop=True)
    )

    soma_total = tabela['contribuicao_periodo'].sum()
    retorno_alvo = df_periodo.attrs.get('retorno_alvo_periodo', np.nan)
    eh_relativo = df_periodo.attrs.get('eh_relativo_benchmark', False)

    reconciliacao = {
        'soma_contribuicoes': soma_total,
        'retorno_alvo_periodo': retorno_alvo,
        'eh_relativo_benchmark': eh_relativo,
        'benchmark': df_periodo.attrs.get('benchmark'),
        'diferenca': soma_total - retorno_alvo if pd.notna(retorno_alvo) else np.nan,
    }

    return tabela, reconciliacao