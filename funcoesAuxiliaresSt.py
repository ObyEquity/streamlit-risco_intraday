# -*- coding: utf-8 -*-
"""
funcoesAuxiliaresSt.py (versão enxuta, unificada para o dashboard geral)

Substitui a versão anterior de funcoesAuxiliaresSt.py, mantendo só o que é
de fato usado pelas páginas do dashboard hoje:

    - historico_de_cotas.py  -> fetch_data_from_supabase, pega_data_referencia
    - Performance Attribution (perf_att_core.py) -> fetch_data_from_supabase_grandes
      (períodos longos estouram timeout do PostgREST sem paginação)

    - metricas_no_tempo.py e risco_do_dia.py NÃO usam esta classe (falam
      direto com supabase_client.py) -- não precisam de nada daqui.

Métodos que existiam na versão anterior e foram removidos por não terem
uso identificado em nenhuma página atual: is_dia_util, pega_distancia_datas,
is_terceira_sexta_ou_util_anterior, self.fundos_master, self.fundos_fic.

IMPORTANTE: se alguma página nova (ou uma existente) passar a precisar de
um desses métodos, é só copiar de volta do funcoesAuxiliares.py original
(pasta de scripts do Risco) -- essa cópia não herda nada automaticamente.

Credenciais via st.secrets["supabase"]["url"] / ["key"]:

    [supabase]
    url = "https://xxxxx.supabase.co"
    key = "..."
"""

import datetime
import pandas as pd
import streamlit as st
from supabase import create_client


class funcoes_auxiliares:
    def __init__(self, delta_dias: int = 0):
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        self.supabase_client = create_client(url, key)

        # Mantido por compatibilidade -- historico_de_cotas.py cria
        # `funcoes_auxiliares(-1)` e depois chama pega_data_referencia
        # de novo explicitamente com outros argumentos, então o valor
        # aqui não costuma ser usado diretamente, mas é barato de manter.
        self.data_referencia = self.pega_data_referencia(datetime.date.today(), delta_dias)

    def fetch_data_from_supabase(
        self,
        field_date: str = 'data_referencia',
        start_date: str = None,
        end_date: str = None,
        filters: list = None,
        schema_name: str = 'public',
        table: str = None,
        cols_select: str = '*',
    ) -> pd.DataFrame:
        """Idêntico ao método original -- copiado sem alterações."""
        query = self.supabase_client.postgrest.schema(schema_name).table(table).select(cols_select)

        if start_date is not None:
            query = query.gte(field_date, start_date)

        if end_date is not None:
            query = query.lte(field_date, end_date)

        if filters is not None:
            for filter_field, filter_values in filters:
                query = query.in_(filter_field, filter_values)

        data = query.execute()
        df = pd.DataFrame(data.data)

        return df

    def fetch_data_from_supabase_grandes(
        self,
        field_date: str = 'data_referencia',
        start_date: str = None,
        end_date: str = None,
        filters: list = None,
        schema_name: str = 'public',
        table: str = None,
        cols_select: str = '*',
    ) -> pd.DataFrame:
        """
        Idêntico ao método original -- copiado sem alterações. Pagina a busca
        via .range() em blocos de 100k linhas, evitando o timeout do
        PostgREST (`statement timeout`) que fetch_data_from_supabase sofre
        em consultas com muitas linhas (ex.: períodos de vários anos).
        """
        all_data = []
        limite = 15000
        offset = 0

        while True:
            query = (
                self.supabase_client.postgrest.schema(schema_name)
                .table(table)
                .select(cols_select)
                .range(offset, offset + limite - 1)
            )

            if start_date is not None:
                query = query.gte(field_date, start_date)

            if end_date is not None:
                query = query.lte(field_date, end_date)

            if filters is not None:
                for filter_field, filter_values in filters:
                    query = query.in_(filter_field, filter_values)

            data = query.execute()

            if not data.data:
                break

            all_data.extend(data.data)
            offset += limite

        df = pd.DataFrame(all_data)

        return df

    def pega_data_referencia(self, data_hoje, delta_dias):
        """Idêntico ao método original -- copiado sem alterações."""
        df_data_feriado = self.fetch_data_from_supabase(table='db_feriados_nacionais')['data_referencia']
        feriados = pd.to_datetime(df_data_feriado).dt.date.tolist()
        data_referencia = data_hoje
        dias_adicionados = 0

        if delta_dias < 0:
            passo = -1
        elif delta_dias > 0:
            passo = 1
        else:
            return data_hoje

        while dias_adicionados < abs(delta_dias):
            data_referencia += datetime.timedelta(days=passo)
            if data_referencia.weekday() < 5 and data_referencia not in feriados:
                dias_adicionados += 1

        return data_referencia