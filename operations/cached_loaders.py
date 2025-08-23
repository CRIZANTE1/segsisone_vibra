import streamlit as st
import pandas as pd
from operations.sheet import SheetOperations

@st.cache_data(ttl=600, show_spinner="Carregando dados das empresas...")
def load_companies_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'nome', 'cnpj', 'status'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("empresas")
    if data and len(data) > 1:
        return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=['id', 'nome', 'cnpj', 'status'])

@st.cache_data(ttl=600, show_spinner="Carregando dados dos funcionários...")
def load_employees_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'nome', 'cargo', 'empresa_id'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("funcionarios")
    if data and len(data) > 1:
        return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=['id', 'nome', 'cargo', 'empresa_id'])

@st.cache_data(ttl=600, show_spinner="Carregando dados dos ASOs...")
def load_asos_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'funcionario_id', 'data_aso', 'tipo_aso', 'vencimento', 'cargo', 'riscos', 'arquivo_id'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("asos")
    if data and len(data) > 1:
        return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=['id', 'funcionario_id', 'data_aso', 'tipo_aso', 'vencimento', 'cargo', 'riscos', 'arquivo_id'])

@st.cache_data(ttl=600, show_spinner="Carregando dados dos treinamentos...")
def load_trainings_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'funcionario_id', 'norma', 'data', 'vencimento', 'tipo_treinamento', 'carga_horaria', 'arquivo_id'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("treinamentos")
    if data and len(data) > 1:
        return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=['id', 'funcionario_id', 'norma', 'data', 'vencimento', 'tipo_treinamento', 'carga_horaria', 'arquivo_id'])

@st.cache_data(ttl=600, show_spinner="Carregando dados dos EPIs...")
def load_epis_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'funcionario_id', 'descricao_epi', 'ca_epi', 'data_entrega', 'arquivo_id'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("epis")
    if data and len(data) > 1:
        return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=['id', 'funcionario_id', 'descricao_epi', 'ca_epi', 'data_entrega', 'arquivo_id'])

@st.cache_data(ttl=600, show_spinner="Carregando dados dos documentos da empresa...")
def load_company_docs_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'empresa_id', 'tipo_documento', 'data_emissao', 'vencimento', 'arquivo_id'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("documentos_empresa")
    if data and len(data) > 1:
        return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=['id', 'empresa_id', 'tipo_documento', 'data_emissao', 'vencimento', 'arquivo_id'])

@st.cache_data(ttl=600, show_spinner="Carregando dados do plano de ação...")
def load_action_plan_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['id', 'empresa_id', 'item', 'responsavel', 'prazo', 'status', 'observacao'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("plano_de_acao")
    if data and len(data) > 1:
        return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=['id', 'empresa_id', 'item', 'responsavel', 'prazo', 'status', 'observacao'])

@st.cache_data(ttl=600, show_spinner="Carregando matriz de treinamentos...")
def load_training_matrix_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=['funcao', 'treinamentos_obrigatorios'])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("matriz_treinamentos")
    if data and len(data) > 1:
        return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=['funcao', 'treinamentos_obrigatorios'])

@st.cache_data(ttl=600, show_spinner="Carregando dados de auditorias...")
def load_audits_df(spreadsheet_id: str) -> pd.DataFrame:
    if not spreadsheet_id: return pd.DataFrame(columns=["id", "id_auditoria", "data_auditoria", "id_empresa", "id_documento_original", "id_funcionario", "tipo_documento", "norma_auditada", "item_de_verificacao", "Status", "observacao"])
    sheet_ops = SheetOperations(spreadsheet_id)
    data = sheet_ops.carregar_dados_aba("auditorias")
    if data and len(data) > 1:
        return pd.DataFrame(data[1:], columns=data[0])
    return pd.DataFrame(columns=["id", "id_auditoria", "data_auditoria", "id_empresa", "id_documento_original", "id_funcionario", "tipo_documento", "norma_auditada", "item_de_verificacao", "Status", "observacao"])