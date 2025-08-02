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
        "Selecione um arquivo PDF...", type="pdf", key="matrix_uploader"
    )

    # --- NOVO FLUXO DE ANÁLISE E CONFIRMAÇÃO ---
    if uploaded_matrix_file:
        if st.button("Analisar Matriz com IA"):
            with st.spinner("A IA está lendo e interpretando sua matriz..."):
                # Etapa 1: Apenas analisa e retorna os dados
                extracted_data, message = matrix_manager.analyze_matrix_pdf(uploaded_matrix_file)
            
            if extracted_data:
                st.success(message)
                # Salva os dados extraídos no session_state para confirmação
                st.session_state.extracted_matrix_data = extracted_data
            else:
                st.error(message)

    # Se houver dados extraídos aguardando confirmação, exibe a tabela
    if 'extracted_matrix_data' in st.session_state:
        st.markdown("---")
        st.subheader("Dados Extraídos para Confirmação")
        st.info("Revise os dados extraídos. Se corretos, clique em 'Salvar' para adicioná-los.")
        
        matrix_to_display = {
            item.get('funcao'): item.get('normas_obrigatorias', [])
            for item in st.session_state.extracted_matrix_data
        }
        st.json(matrix_to_display, expanded=True)

        if st.button("Confirmar e Salvar Matriz", type="primary"):
            with st.spinner("Salvando dados na planilha..."):
                added_funcs, added_maps = matrix_manager.save_extracted_matrix(st.session_state.extracted_matrix_data)
            st.success(f"Matriz salva! {added_funcs} novas funções e {added_maps} mapeamentos adicionados.")
            del st.session_state.extracted_matrix_data
            st.rerun()

    st.markdown("---")
    
    st.subheader("2. Gerenciar Manualmente")    
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
            
    with col2:
        st.write("**Mapear Treinamentos para Funções**")
        if matrix_manager.functions_df.empty:
            st.warning("Cadastre uma função à esquerda primeiro.")
        else:
            selected_function_id = st.selectbox(
                "Selecione a Função",
                options=matrix_manager.functions_df['id'].tolist(),
                format_func=lambda id: matrix_manager.functions_df.loc[matrix_manager.functions_df['id'] == id, 'nome_funcao'].iloc[0]
            )
            
            if selected_function_id:
                selected_function_name = matrix_manager.functions_df.loc[matrix_manager.functions_df['id'] == selected_function_id, 'nome_funcao'].iloc[0]
                
                
                current_mappings = matrix_manager.get_required_trainings_for_function(selected_function_name)

                all_options = set()
                all_options.update(employee_manager.nr_config.keys())
                all_options.update(employee_manager.nr20_config.keys())
                if not matrix_manager.matrix_df.empty:
                    all_options.update(matrix_manager.matrix_df['norma_obrigatoria'].unique())
                
                # --- CORREÇÃO AQUI: Aplainar a lista 'current_mappings' ---
                if current_mappings:
                    def flatten(l):
                        for el in l:
                            if isinstance(el, collections.abc.Iterable) and not isinstance(el, (str, bytes)):
                                yield from flatten(el)
                            else:
                                yield el
                    all_options.update(list(flatten(current_mappings)))
                
                final_options = sorted(list(all_options))
                
                st.markdown("**Selecione os Treinamentos Obrigatórios:**")
                
                checkbox_states = {}
                for norm in final_options:
                    is_checked = norm in current_mappings
                    checkbox_states[norm] = st.checkbox(norm, value=is_checked, key=f"cb_{selected_function_id}_{norm}")
                
                if st.button("Salvar Mapeamentos para esta Função", type="primary"):
                    new_required_norms = [norm for norm, checked in checkbox_states.items() if checked]
                    
                    with st.spinner("Atualizando mapeamentos..."):
                        success, message = matrix_manager.update_function_mappings(selected_function_id, new_required_norms)
                    
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

    st.markdown("---")
    st.subheader("Matriz de Treinamentos Atual no Sistema")
    
    if not matrix_manager.matrix_df.empty and not matrix_manager.functions_df.empty:
        # Agrupa os mapeamentos por função para criar a estrutura de dicionário
        func_id_to_name = matrix_manager.functions_df.set_index('id')['nome_funcao']
        display_df = matrix_manager.matrix_df.copy()
        display_df['nome_funcao'] = display_df['id_funcao'].map(func_id_to_name)
        
        json_view = display_df.groupby('nome_funcao')['norma_obrigatoria'].apply(list).to_dict()
        
        st.json(json_view, expanded=False) # Começa recolhido por padrão
    else:
        st.info("Nenhum mapeamento de treinamento foi criado ainda.")
