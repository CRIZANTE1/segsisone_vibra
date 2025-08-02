import streamlit as st
from datetime import date
import pandas as pd

from operations.employee import EmployeeManager
from operations.matrix_manager import MatrixManager
from ui.metrics import display_minimalist_metrics
from auth.auth_utils import check_admin_permission, is_user_logged_in

st.set_page_config(page_title="Administração", page_icon="⚙️", layout="wide")

st.title("⚙️ Painel de Administração")

# --- Verificação de Segurança ---
if not is_user_logged_in():
    st.warning("Por favor, faça login para acessar esta página.")
    st.stop()
if not check_admin_permission():
    st.error("Você não tem permissão para acessar o painel de administração.")
    st.stop()

# --- Instanciação Padronizada dos Gerenciadores ---
@st.cache_resource
def get_admin_managers():
    """Instancia os gerenciadores necessários para a página de Administração."""
    return EmployeeManager(), MatrixManager()

employee_manager, matrix_manager = get_admin_managers()

# --- Exibição das Métricas ---
st.header("Visão Geral das Pendências")
display_minimalist_metrics(employee_manager)

# --- UI com Abas para Cadastro ---
tab_empresa, tab_funcionario, tab_matriz = st.tabs([
    "Cadastrar Empresa", "Cadastrar Funcionário", "Gerenciar Matriz de Treinamento"
])

# --- ABA DE CADASTRO DE EMPRESA ---
with tab_empresa:
    st.header("Formulário de Cadastro de Empresa")
    with st.form("form_add_company", clear_on_submit=True):
        company_name = st.text_input("Nome da Empresa", placeholder="Digite o nome completo da empresa")
        company_cnpj = st.text_input("CNPJ", placeholder="Digite o CNPJ (apenas números)")
        submitted = st.form_submit_button("Cadastrar Empresa")
        if submitted:
            if not company_name or not company_cnpj:
                st.error("Por favor, preencha todos os campos.")
            else:
                cnpj_clean = "".join(filter(str.isdigit, company_cnpj))
                with st.spinner("Cadastrando empresa..."):
                    company_id, message = employee_manager.add_company(company_name, cnpj_clean)
                    if company_id:
                        st.success(f"Sucesso: {message} (ID: {company_id})")
                        st.cache_resource.clear() # Limpa o cache para atualizar os selectboxes
                        st.rerun()
                    else:
                        st.error(f"Falha: {message}")

# --- ABA DE CADASTRO DE FUNCIONÁRIO ---
with tab_funcionario:
    st.header("Formulário de Cadastro de Funcionário")
    if employee_manager.companies_df.empty:
        st.warning("Nenhuma empresa cadastrada. Por favor, cadastre uma empresa primeiro.")
    else:
        company_list = employee_manager.companies_df.copy()
        selected_company_id = st.selectbox(
            "Selecione a Empresa do Funcionário",
            options=company_list['id'].tolist(),
            format_func=lambda x: employee_manager.get_company_name(x),
            index=None,
            placeholder="Escolha uma empresa..."
        )
        if selected_company_id:
            with st.form("form_add_employee", clear_on_submit=True):
                employee_name = st.text_input("Nome do Funcionário")
                employee_role = st.text_input("Cargo")
                admission_date = st.date_input("Data de Admissão", value=None, format="DD/MM/YYYY")
                submitted_employee = st.form_submit_button("Cadastrar Funcionário")
                if submitted_employee:
                    if not all([employee_name, employee_role, admission_date]):
                        st.error("Por favor, preencha todos os campos do funcionário.")
                    else:
                        with st.spinner("Cadastrando funcionário..."):
                            employee_id, message = employee_manager.add_employee(
                                nome=employee_name, cargo=employee_role,
                                data_admissao=admission_date, empresa_id=selected_company_id
                            )
                            if employee_id:
                                st.success(f"Sucesso: {message} (ID: {employee_id})")
                            else:
                                st.error(f"Falha: {message}")

with tab_matriz:
    st.header("Matriz de Treinamento por Função")
    
    st.subheader("1. Importar Matriz a partir de um Documento (PDF)")
    
    uploaded_matrix_file = st.file_uploader(
        "Selecione um arquivo PDF com a sua matriz de treinamentos",
        type="pdf",
        key="matrix_uploader"
    )

    if uploaded_matrix_file:
        if st.button("Processar Matriz com IA", type="primary"):
            with st.spinner("A IA está lendo e interpretando sua matriz..."):
                success, message = matrix_manager.process_matrix_pdf(uploaded_matrix_file)
            
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    st.markdown("---")
        
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("2. Cadastrar/Ver Funções")
        with st.form("form_add_function"):
            func_name = st.text_input("Nome da Nova Função (ex: Soldador)")
            func_desc = st.text_area("Descrição (opcional)")
            submitted_func = st.form_submit_button("Adicionar Função")
            if submitted_func and func_name:
                func_id, msg = matrix_manager.add_function(func_name, func_desc)
                if func_id:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        st.markdown("---")
        st.write("**Funções Cadastradas:**")
        st.dataframe(matrix_manager.functions_df[['nome_funcao', 'descricao']], use_container_width=True)

    with col2:
        st.subheader("3. Mapear Treinamentos para Funções")
        if matrix_manager.functions_df.empty:
            st.warning("Cadastre uma função à esquerda primeiro.")
        else:
            selected_function_id = st.selectbox(
                "Selecione a Função",
                options=matrix_manager.functions_df['id'].tolist(),
                format_func=lambda id: matrix_manager.functions_df.loc[matrix_manager.functions_df['id'] == id, 'nome_funcao'].iloc[0]
            )
            all_norms = sorted(list(employee_manager.nr_config.keys()))
            if 'NR-20' not in all_norms: all_norms.insert(0, 'NR-20')
            
            required_norm = st.selectbox("Selecione o Treinamento Obrigatório", options=all_norms)
            
            if st.button("Mapear Treinamento"):
                if selected_function_id and required_norm:
                    map_id, msg = matrix_manager.add_training_to_function(selected_function_id, required_norm)
                    if map_id:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    st.markdown("---")
    st.subheader("Matriz de Treinamentos Atual")
    if not matrix_manager.matrix_df.empty and not matrix_manager.functions_df.empty:
        func_id_to_name = matrix_manager.functions_df.set_index('id')['nome_funcao']
        display_matrix = matrix_manager.matrix_df.copy()
        display_matrix['nome_funcao'] = display_matrix['id_funcao'].map(func_id_to_name)
        st.dataframe(display_matrix[['nome_funcao', 'norma_obrigatoria']], use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum mapeamento de treinamento foi criado ainda.")
