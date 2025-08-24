import streamlit as st
import pandas as pd
from operations.sheet import SheetOperations

@st.cache_data(ttl=600, show_spinner="Carregando dados das empresas...")
def load_companies_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'nome', 'cnpj', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("empresas")
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    return pd.DataFrame(columns=['id', 'nome', 'cnpj', 'status'])

@st.cache_data(ttl=600, show_spinner="Carregando dados dos funcionários...")
def load_employees_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'empresa_id', 'nome', 'funcao', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("funcionarios")
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    return pd.DataFrame(columns=['id', 'empresa_id', 'nome', 'funcao', 'status'])

@st.cache_data(ttl=600, show_spinner="Carregando dados dos ASOs...")
def load_asos_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'funcionario_id', 'tipo', 'data_emissao', 'data_vencimento', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("asos")
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    return pd.DataFrame(columns=['id', 'funcionario_id', 'tipo', 'data_emissao', 'data_vencimento', 'status'])

@st.cache_data(ttl=600, show_spinner="Carregando dados dos treinamentos...")
def load_trainings_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'funcionario_id', 'nome', 'data_emissao', 'data_vencimento', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("treinamentos")
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    return pd.DataFrame(columns=['id', 'funcionario_id', 'nome', 'data_emissao', 'data_vencimento', 'status'])

@st.cache_data(ttl=600, show_spinner="Carregando dados das fichas de EPI...")
def load_epis_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'funcionario_id', 'data_emissao', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("epis")
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    return pd.DataFrame(columns=['id', 'funcionario_id', 'data_emissao', 'status'])

@st.cache_data(ttl=600, show_spinner="Carregando dados do plano de ação...")
def load_action_plan_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'origem', 'item_id', 'descricao', 'responsavel', 'data_limite', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("plano_de_acao")
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    return pd.DataFrame(columns=['id', 'origem', 'item_id', 'descricao', 'responsavel', 'data_limite', 'status'])

@st.cache_data(ttl=600, show_spinner="Carregando documentos da empresa...")
def load_company_docs_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'empresa_id', 'nome_documento', 'data_vencimento', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("documentos_empresa")
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    return pd.DataFrame(columns=['id', 'empresa_id', 'nome_documento', 'data_vencimento', 'status'])

@st.cache_data(ttl=600, show_spinner="Carregando matriz de treinamentos...")
def load_training_matrix_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['funcao', 'treinamentos_obrigatorios'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("matriz_treinamentos")
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    return pd.DataFrame(columns=['funcao', 'treinamentos_obrigatorios'])

@st.cache_data(ttl=600, show_spinner="Carregando dados de auditorias...")
def load_audits_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'id_empresa', 'id_documento_original', 'item_nao_conforme', 'referencia_normativa', 'plano_de_acao', 'responsavel', 'prazo', 'status', 'data_criacao', 'data_conclusao'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("auditorias")
    if data and len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    return pd.DataFrame(columns=['id', 'id_empresa', 'id_documento_original', 'item_nao_conforme', 'referencia_normativa', 'plano_de_acao', 'responsavel', 'prazo', 'status', 'data_criacao', 'data_conclusao'])
