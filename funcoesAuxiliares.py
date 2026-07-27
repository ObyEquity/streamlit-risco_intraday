# -*- coding: utf-8 -*-
"""
funcoesAuxiliares.py (versão reduzida — só para o Performance Attribution)

Esta é uma cópia ENXUTA do funcoesAuxiliares.py original, contendo apenas o
que é de fato usado por perf_att_core.py / dashboard_perf_att.py:

    - funcoes_auxiliares.__init__      (conexão com o Supabase)
    - funcoes_auxiliares.fetch_data_from_supabase

Motivo de existir: ao colocar o dashboard de Performance Attribution como
página dentro do dashboard geral de risco, um import direto de
`funcoesAuxiliares` (o módulo completo, na pasta de scripts do Risco) pode
quebrar por causa do caminho relativo. Esta cópia local resolve isso sem
precisar alterar nenhuma linha de perf_att_core.py/dashboard_perf_att.py —
o `from funcoesAuxiliares import funcoes_auxiliares` continua funcionando
igual, só que apontando pra essa versão reduzida, que fica na mesma pasta
da página do dashboard.

IMPORTANTE: se o funcoesAuxiliares.py "de verdade" ganhar métodos que
o perf attribution passe a usar no futuro (ex.: pega_distancia_datas,
upsert_data etc.), essa cópia precisa ser atualizada também — ela não
herda automaticamente do original.

Credenciais: lidas via st.secrets["supabase"]["url"] / ["key"] (padrão do
Streamlit Cloud), não mais via variável de ambiente. O secrets.toml
(local, em .streamlit/secrets.toml, ou cadastrado no painel do Streamlit
Cloud) precisa ter:

    [supabase]
    url = "https://xxxxx.supabase.co"
    key = "..."
"""

import streamlit as st
import pandas as pd
from supabase import create_client


class funcoes_auxiliares:
    def __init__(self, delta_dias: int = 0):
        """
        `delta_dias` é aceito só por compatibilidade de assinatura com o
        funcoesAuxiliares.py completo (ex.: `funcoes_auxiliares(delta_dias=0)`
        já usado no dashboard) -- não é usado aqui, já que o Performance
        Attribution não depende de data_referencia/dia útil calculado no
        __init__ (isso evitava uma busca desnecessária em
        db_feriados_nacionais e a dependência de os.getlogin()).
        """
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        self.supabase_client = create_client(url, key)

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
