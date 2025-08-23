import streamlit as st
import pandas as pd
from operations.sheet import SheetOperations

# --- Funções de Cache para Dados de Tenant ---

@st.cache_data(ttl=600)
def get_companies_df(spreadsheet_id: str) -> pd.DataFrame:
    """Carrega a aba 'empresas' de uma planilha de unidade."""
    if not spreadsheet_id: return pd.DataFrame()
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("empresas")
    expected_cols = ['id', 'nome', 'cnpj', 'status']
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        return df
    return pd.DataFrame(columns=expected_cols)

@st.cache_data(ttl=600)
def get_employees_df(spreadsheet_id: str) -> pd.DataFrame:
    """Carrega a aba 'funcionarios' de uma planilha de unidade."""
    if not spreadsheet_id: return pd.DataFrame()
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("funcionarios")
    expected_cols = ['id', 'nome', 'empresa_id', 'cargo', 'data_admissao', 'status']
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        return df
    return pd.DataFrame(columns=expected_cols)

@st.cache_data(ttl=600)
def get_asos_df(spreadsheet_id: str) -> pd.DataFrame:
    """Carrega a aba 'asos' de uma planilha de unidade."""
    if not spreadsheet_id: return pd.DataFrame()
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("asos")
    expected_cols = ['id', 'funcionario_id', 'data_aso', 'vencimento', 'arquivo_id', 'riscos', 'cargo', 'tipo_aso']
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        return df
    return pd.DataFrame(columns=expected_cols)

@st.cache_data(ttl=600)
def get_trainings_df(spreadsheet_id: str) -> pd.DataFrame:
    """Carrega a aba 'treinamentos' de uma planilha de unidade."""
    if not spreadsheet_id: return pd.DataFrame()
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("treinamentos")
    expected_cols = ['id', 'funcionario_id', 'data', 'vencimento', 'norma', 'modulo', 'status', 'anexo', 'tipo_treinamento', 'carga_horaria']
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        return df
    return pd.DataFrame(columns=expected_cols)

@st.cache_data(ttl=600)
def get_docs_df(spreadsheet_id: str) -> pd.DataFrame:
    """Carrega a aba 'documentos_empresa' de uma planilha de unidade."""
    if not spreadsheet_id: return pd.DataFrame()
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("documentos_empresa")
    expected_cols = ['id', 'empresa_id', 'tipo_documento', 'data_emissao', 'vencimento', 'arquivo_id']
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        return df
    return pd.DataFrame(columns=expected_cols)

@st.cache_data(ttl=600)
def get_epi_df(spreadsheet_id: str) -> pd.DataFrame:
    """Carrega a aba 'fichas_epi' de uma planilha de unidade."""
    if not spreadsheet_id: return pd.DataFrame()
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("fichas_epi")
    expected_cols = ['id', 'funcionario_id', 'item_id', 'descricao_epi', 'ca_epi', 'data_entrega', 'arquivo_id']
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        return df
    return pd.DataFrame(columns=expected_cols)

@st.cache_data(ttl=600)
def get_action_plan_df(spreadsheet_id: str) -> pd.DataFrame:
    """Carrega a aba 'plano_acao' de uma planilha de unidade."""
    if not spreadsheet_id: return pd.DataFrame()
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("plano_acao")
    expected_cols = ['id', 'audit_run_id', 'id_empresa', 'id_documento_original', 'item_nao_conforme', 'referencia_normativa', 'plano_de_acao', 'responsavel', 'prazo', 'status', 'data_criacao', 'data_conclusao']
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        # Assegura que colunas essenciais existam
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        df.columns = [col.strip().lower() for col in df.columns]
        return df
    return pd.DataFrame(columns=expected_cols)
