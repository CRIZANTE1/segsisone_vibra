# front/dashboard.py (VERSÃO DE DEPURAÇÃO)

import streamlit as st
import pandas as pd

def show_dashboard_page():
    st.title("Dashboard - Modo de Depuração")

    # 1. Barreira de Proteção Essencial
    if not st.session_state.get('managers_initialized'):
        st.warning("Gerenciadores não inicializados. Selecione uma unidade operacional na barra lateral.")
        st.info("Se você já selecionou, pode haver um problema no carregamento inicial.")
        st.write("Conteúdo do st.session_state:")
        st.json(st.session_state) # Mostra o estado atual para depuração
        return
        
    # 2. Carrega os gerenciadores da sessão
    try:
        employee_manager = st.session_state.employee_manager
        docs_manager = st.session_state.docs_manager
        epi_manager = st.session_state.epi_manager
        action_plan_manager = st.session_state.action_plan_manager
    except AttributeError as e:
        st.error(f"Erro ao carregar gerenciadores da sessão: {e}")
        st.write("Isso indica que a inicialização em Segsisone.py falhou.")
        st.json(st.session_state)
        return

    st.header("Verificação de Dados Carregados")
    st.write(f"Operando na unidade: **{st.session_state.get('unit_name', 'N/A')}**")
    st.write(f"ID da Planilha: `{st.session_state.get('spreadsheet_id', 'Nenhum')}`")

    # 3. Exibição Direta e Simples dos DataFrames
    
    st.subheader("Dados da Aba 'empresas'")
    if not employee_manager.companies_df.empty:
        st.dataframe(employee_manager.companies_df)
    else:
        st.info("DataFrame de Empresas está vazio.")

    st.subheader("Dados da Aba 'funcionarios'")
    if not employee_manager.employees_df.empty:
        st.dataframe(employee_manager.employees_df)
    else:
        st.info("DataFrame de Funcionários está vazio.")

    st.subheader("Dados da Aba 'asos'")
    if not employee_manager.aso_df.empty:
        st.dataframe(employee_manager.aso_df)
    else:
        st.info("DataFrame de ASOs está vazio.")
        
    st.subheader("Dados da Aba 'treinamentos'")
    if not employee_manager.training_df.empty:
        st.dataframe(employee_manager.training_df)
    else:
        st.info("DataFrame de Treinamentos está vazio.")

    st.subheader("Dados da Aba 'matriz_treinamentos'")
    if not employee_manager.training_matrix_df.empty:
        st.dataframe(employee_manager.training_matrix_df)
    else:
        st.info("DataFrame da Matriz de Treinamentos está vazio.")
        
    st.subheader("Dados da Aba 'documentos_empresa'")
    if not docs_manager.docs_df.empty:
        st.dataframe(docs_manager.docs_df)
    else:
        st.info("DataFrame de Documentos da Empresa está vazio.")
        
    st.subheader("Dados da Aba 'fichas_epi'")
    if not epi_manager.epi_df.empty:
        st.dataframe(epi_manager.epi_df)
    else:
        st.info("DataFrame de Fichas de EPI está vazio.")
        
    st.subheader("Dados da Aba 'plano_acao'")
    if not action_plan_manager.action_plan_df.empty:
        st.dataframe(action_plan_manager.action_plan_df)
    else:
        st.info("DataFrame do Plano de Ação está vazio.")

    st.success("Teste de exibição direta concluído. Se você vê esta mensagem, o carregamento dos dados está funcionando.")
