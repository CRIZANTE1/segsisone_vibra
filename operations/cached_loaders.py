import streamlit as st
import pandas as pd
from operations.sheet import SheetOperations
import logging

logger = logging.getLogger(__name__)

@st.cache_data(ttl=600, show_spinner="Carregando dados das empresas...")
def load_companies_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'nome', 'cnpj', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    return sheet_ops.get_df_from_worksheet("empresas")

@st.cache_data(ttl=600, show_spinner="Carregando dados dos funcionários...")
def load_employees_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'empresa_id', 'nome', 'funcao', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    return sheet_ops.get_df_from_worksheet("funcionarios")

@st.cache_data(ttl=600, show_spinner="Carregando dados dos ASOs...")
def load_asos_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'funcionario_id', 'tipo', 'data_emissao', 'data_vencimento', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    return sheet_ops.get_df_from_worksheet("asos")

@st.cache_data(ttl=600, show_spinner="Carregando dados dos treinamentos...")
def load_trainings_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'funcionario_id', 'nome', 'data_emissao', 'data_vencimento', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    return sheet_ops.get_df_from_worksheet("treinamentos")

@st.cache_data(ttl=600, show_spinner="Carregando dados das fichas de EPI...")
def load_epis_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'funcionario_id', 'data_emissao', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    return sheet_ops.get_df_from_worksheet("fichas_epi")

def load_action_plan_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: 
        return pd.DataFrame(columns=[
            'id', 'audit_run_id', 'id_empresa', 'id_documento_original', 
            'id_funcionario', 'item_nao_conforme', 'referencia_normativa', 
            'plano_de_acao', 'responsavel', 'prazo', 'status', 
            'data_criacao', 'data_conclusao'
        ])
    sheet_ops = SheetOperations(spreadsheet_id)
    return sheet_ops.get_df_from_worksheet("plano_acao")

@st.cache_data(ttl=600, show_spinner="Carregando documentos da empresa...")
def load_company_docs_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'empresa_id', 'nome_documento', 'data_vencimento', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    return sheet_ops.get_df_from_worksheet("documentos_empresa")

@st.cache_data(ttl=600, show_spinner="Carregando matriz de treinamentos...")
def load_training_matrix_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['funcao', 'treinamentos_obrigatorios'])
    sheet_ops = SheetOperations(spreadsheet_id)
    return sheet_ops.get_df_from_worksheet("matriz_treinamentos")

@st.cache_data(ttl=600, show_spinner="Carregando dados de auditorias...")
def load_audits_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'id_empresa', 'id_documento_original', 'item_nao_conforme', 'referencia_normativa', 'plano_de_acao', 'responsavel', 'prazo', 'status', 'data_criacao', 'data_conclusao'])
    sheet_ops = SheetOperations(spreadsheet_id)
    return sheet_ops.get_df_from_worksheet("auditorias")

@st.cache_data(ttl=600, show_spinner="Carregando dados...")
def load_all_unit_data(spreadsheet_id: str) -> dict:
    """
    Carrega TODOS os dados de uma vez.
    Cache de 10 minutos (600 segundos)
    """
    # 1. Validação inicial
    if not spreadsheet_id:
        return {
            'companies': pd.DataFrame(),
            'employees': pd.DataFrame(),
            'asos': pd.DataFrame(),
            'trainings': pd.DataFrame(),
            'epis': pd.DataFrame(),
            'company_docs': pd.DataFrame(),
            'action_plan': pd.DataFrame()
        }
    
    # 2. Cria UMA ÚNICA instância do SheetOperations
    sheet_ops = SheetOperations(spreadsheet_id)
    
    # 3. Carrega todas as abas SEQUENCIALMENTE (mas na mesma função)
    data = {
        'companies': sheet_ops.get_df_from_worksheet("empresas"),
        'employees': sheet_ops.get_df_from_worksheet("funcionarios"),
        'asos': sheet_ops.get_df_from_worksheet("asos"),
        'trainings': sheet_ops.get_df_from_worksheet("treinamentos"),
        'epis': sheet_ops.get_df_from_worksheet("fichas_epi"),
        'company_docs': sheet_ops.get_df_from_worksheet("documentos_empresa"),
        'action_plan': sheet_ops.get_df_from_worksheet("plano_acao")
    }
    
    # 4. Processa TODAS as datas de uma vez (eficiente!)
    for df_name, date_cols in [
        ('asos', ['data_aso', 'vencimento']),
        ('trainings', ['data', 'vencimento']),
        ('company_docs', ['data_emissao', 'vencimento']),
        ('employees', ['data_admissao'])
    ]:
        df = data[df_name]
        if not df.empty:
            for col in date_cols:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], format='%d/%m/%Y', errors='coerce')
    
    # 5. Retorna TUDO de uma vez
    return data