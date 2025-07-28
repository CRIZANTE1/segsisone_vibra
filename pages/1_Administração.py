import streamlit as st
from datetime import date

from operations.employee import EmployeeManager
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

# --- Instanciação do Gerenciador ---
@st.cache_resource
def get_employee_manager():
    return EmployeeManager()

employee_manager = get_employee_manager()

# --- UI com Abas para Cadastro ---
tab_empresa, tab_funcionario = st.tabs(["Cadastrar Nova Empresa", "Cadastrar Novo Funcionário"])

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
                # Remove formatação do CNPJ, se houver
                cnpj_clean = "".join(filter(str.isdigit, company_cnpj))
                
                with st.spinner("Cadastrando empresa..."):
                    company_id, message = employee_manager.add_company(company_name, cnpj_clean)
                    if company_id:
                        st.success(f"Sucesso: {message} (ID: {company_id})")
                        # Limpar o cache para que o novo selectbox mostre a nova empresa
                        st.cache_resource.clear()
                    else:
                        st.error(f"Falha: {message}")

# --- ABA DE CADASTRO DE FUNCIONÁRIO ---
with tab_funcionario:
    st.header("Formulário de Cadastro de Funcionário")
    
    # Selecionar a empresa à qual o funcionário pertence
    if employee_manager.companies_df.empty:
        st.warning("Nenhuma empresa cadastrada. Por favor, cadastre uma empresa primeiro na aba ao lado.")
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
                employee_name = st.text_input("Nome do Funcionário", placeholder="Digite o nome completo do funcionário")
                employee_role = st.text_input("Cargo", placeholder="Digite o cargo do funcionário")
                admission_date = st.date_input("Data de Admissão", value=date.today(), format="DD/MM/YYYY")

                submitted_employee = st.form_submit_button("Cadastrar Funcionário")

                if submitted_employee:
                    if not employee_name or not employee_role:
                        st.error("Por favor, preencha todos os campos do funcionário.")
                    else:
                        with st.spinner("Cadastrando funcionário..."):
                            employee_id, message = employee_manager.add_employee(
                                nome=employee_name,
                                cargo=employee_role,
                                data_admissao=admission_date,
                                empresa_id=selected_company_id
                            )
                            if employee_id:
                                st.success(f"Sucesso: {message} (ID: {employee_id})")
                            else:
                                st.error(f"Falha: {message}")
