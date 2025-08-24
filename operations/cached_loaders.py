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
    return sheet_ops.get_df_from_worksheet("epis")

@st.cache_data(ttl=600, show_spinner="Carregando dados do plano de ação...")
def load_action_plan_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'origem', 'item_id', 'descricao', 'responsavel', 'data_limite', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    return sheet_ops.get_df_from_worksheet("plano_de_acao")

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
