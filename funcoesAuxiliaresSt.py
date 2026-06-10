import pandas as pd
from supabase import create_client, Client
import datetime
import streamlit as st


class funcoes_auxiliares:
    def __init__(self, delta_dias:0):
        
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        self.supabase_client = create_client(url,key)
     
        
        self.fundos_master = ['LO1','LSH1','LSH2']
        self.fundos_fic = ['LO1_FIC', 'LSH1_FIC', 'LSH2_FIC']
        
        #self.df_data_feriado = self.fetch_data_from_supabase(table='db_feriados_nacionais')['data']
        self.data_referencia = self.pega_data_referencia(datetime.date.today(),delta_dias)

        
    def fetch_data_from_supabase(
        self,
        field_date: str = 'data_referencia',
        start_date: str = None, 
        end_date: str = None, 
        filters: list = None, 
        schema_name: str = 'public', 
        table: str = None, 
        cols_select: str = '*'
        ) -> pd.DataFrame:
    
            
        # Building the query
        query = self.supabase_client.postgrest.schema(schema_name).table(table).select(cols_select)
    
        if start_date is not None:
            query = query.gte(field_date, start_date)
        
        if end_date is not None:
            query = query.lte(field_date, end_date)
    
        # Applying filters
        if filters is not None:
            for filter_field, filter_values in filters:
                query = query.in_(filter_field, filter_values)
    
        # Executing the query
        data = query.execute()
    
        # Creating a DataFrame from the results
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
        cols_select: str = '*'
        ) -> pd.DataFrame:
    
        # Lista para armazenar todos os resultados
        all_data = []
        limite = 100000
        offset = 0
    
        while True:
            # Building the query com range
            query = self.supabase_client.postgrest.schema(schema_name).table(table).select(cols_select).range(offset, offset + limite - 1)
    
            if start_date is not None:
                query = query.gte(field_date, start_date)
    
            if end_date is not None:
                query = query.lte(field_date, end_date)
    
            if filters is not None:
                for filter_field, filter_values in filters:
                    query = query.in_(filter_field, filter_values)
    
            # Executando
            data = query.execute()
    
            # Se não retornar mais dados, parar
            if not data.data:
                break
    
            # Adiciona ao resultado geral
            all_data.extend(data.data)
    
            # Incrementa o offset
            offset += limite
    
        # Criar DataFrame
        df = pd.DataFrame(all_data)
    
        return df
    
    def is_dia_util(self,data_referencia):
        df_data_feriado = self.fetch_data_from_supabase(table='db_feriados_nacionais')['data_referencia']
        feriados = pd.to_datetime(df_data_feriado).dt.date.tolist()
            
        # Verificar se o dia é um dia útil (não é sábado, domingo ou feriado)
        if data_referencia.weekday() < 5 and data_referencia not in feriados:
            return True
        else:
            return False

    def pega_data_referencia(self,data_hoje,delta_dias):
        df_data_feriado = self.fetch_data_from_supabase(table='db_feriados_nacionais')['data_referencia']
        feriados = pd.to_datetime(df_data_feriado).dt.date.tolist()
        data_referencia = data_hoje
        dias_adicionados = 0
        
        # Definir a direção do cálculo baseado no sinal do delta_dias
        if delta_dias < 0:
            passo = -1  # para trás
        elif delta_dias > 0:
            passo = 1   # para frente
        else:
            return data_hoje
    
        while dias_adicionados < abs(delta_dias):
            data_referencia += datetime.timedelta(days=passo)
            if data_referencia.weekday() < 5 and data_referencia not in feriados:
                dias_adicionados += 1
        
        return data_referencia
    
    def pega_distancia_datas(self, data_hoje, data_fim):
        df_data_feriado = self.fetch_data_from_supabase(table='db_feriados_nacionais')['data_referencia']
        feriados = pd.to_datetime(df_data_feriado).dt.date.tolist()
        data_referencia = data_hoje
        contador = 0
        if data_fim > data_hoje:
            while data_referencia <= data_fim:
                if data_referencia.weekday() < 5 and data_referencia not in feriados:
                    contador +=1
                
                data_referencia += datetime.timedelta(days=1)
        elif data_fim < data_hoje:
            while data_referencia >= data_fim:
                if data_referencia.weekday() < 5 and data_referencia not in feriados:
                    contador -=1
                
                data_referencia += datetime.timedelta(days=-1)        
        elif data_fim == data_hoje:
            contador = 0
        
        return contador

    def is_terceira_sexta_ou_util_anterior(self, str_data=False):
        # str_data não é obrigatorio e se for utilizar passar a data no formato string '2025-08-31'
        if str_data:
            data_referencia = datetime.datetime.strptime(str_data, "%Y-%m-%d").date()
        else:
            data_referencia = self.data_referencia
        
        feriados = self.fetch_data_from_supabase(table='db_feriados_nacionais')
        feriados = pd.to_datetime(feriados['data_referencia']).dt.date.tolist()
        
        
        # Encontrar todas as sextas-feiras do mês da data de referência
        inicio_mes = data_referencia.replace(day=1)
        fim_mes = (inicio_mes + pd.offsets.MonthEnd(0))
    
        dias_do_mes = pd.date_range(start=inicio_mes, end=fim_mes, freq='D')
        sextas = dias_do_mes[dias_do_mes.weekday == 4]  # 4 = sexta-feira
    
        # Pegar a terceira sexta-feira do mês
        terceira_sexta = sextas[2].date()  # Índice 2 -> terceira sexta
    
        # Verificar se a terceira sexta é feriado
        if terceira_sexta in feriados:
            # Se for feriado, pegar o dia útil anterior
            data_valida = terceira_sexta - pd.offsets.BDay(1)
            data_valida = data_valida.date()
        else:
            data_valida = terceira_sexta
    
        # Verificar se a data de referência é igual à data válida
        return data_referencia == data_valida

        
    