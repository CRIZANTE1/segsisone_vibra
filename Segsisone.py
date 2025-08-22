import streamlit as st
import sys
import os
from streamlit_option_menu import option_menu

# --- Configuração do Caminho (Path) ---
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# --- Importação das Funções de Página ---
from auth.login_page import show_login_page, show_user_header, show_logout_button
from auth.auth_utils import authenticate_user, is_user_logged_in, get_user_role
from gdrive.matrix_manager import MatrixManager
from front.dashboard import show_dashboard_page
from front.administracao import show_admin_page
from front.plano_de_acao import show_plano_acao_page

# --- 1. ADICIONE AS IMPORTAÇÕES DOS GERENCIADORES AQUI ---
from operations.employee import EmployeeManager
from operations.company_docs import CompanyDocsManager
from operations.epi import EPIManager
from operations.action_plan import ActionPlanManager
from analysis.nr_analyzer import NRAnalyzer
from gdrive.gdrive_upload import GoogleDriveUploader


def configurar_pagina():
    st.set_page_config(
        page_title="SEGMA-SIS | Gestão Inteligente",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )

# --- 2. CRIE A FUNÇÃO DE INICIALIZAÇÃO CENTRAL AQUI ---
def initialize_tenant_managers():
    """
    Cria instâncias dos gerenciadores para a unidade selecionada (tenant)
    e as armazena no session_state para serem usadas por todas as páginas.
    """
    # Só executa se houver uma unidade selecionada (não no modo 'Global' inicial do admin)
    if 'spreadsheet_id' not in st.session_state or not st.session_state.spreadsheet_id:
        st.session_state.managers_initialized = False
        return

    current_unit_id = st.session_state.spreadsheet_id
    
    # Recria os gerenciadores se a unidade mudou ou se eles nunca foram criados
    if st.session_state.get('managers_initialized_for') != current_unit_id:
        with st.spinner("Carregando dados da unidade..."):
            st.session_state.employee_manager = EmployeeManager(current_unit_id, st.session_state.folder_id)
            st.session_state.docs_manager = CompanyDocsManager(current_unit_id)
            st.session_state.epi_manager = EPIManager(current_unit_id)
            st.session_state.action_plan_manager = ActionPlanManager(current_unit_id)
            st.session_state.nr_analyzer = NRAnalyzer(current_unit_id)
            st.session_state.gdrive_uploader = GoogleDriveUploader(st.session_state.folder_id)
            
            # Guarda o ID da unidade para a qual os gerenciadores foram criados
            st.session_state.managers_initialized_for = current_unit_id
            st.session_state.managers_initialized = True
        st.rerun() # Força um rerun para garantir que a UI reflita os novos dados carregados

def main():
    configurar_pagina()

    if not is_user_logged_in():
        show_login_page()
        st.stop()
    
    if not authenticate_user():
        st.stop()

    # --- 3. CHAME A FUNÇÃO DE INICIALIZAÇÃO AQUI ---
    initialize_tenant_managers()

    # --- LÓGICA DO MENU DE NAVEGAÇÃO (sem alterações) ---
    with st.sidebar:
        show_user_header()
        user_role = get_user_role()
        if user_role == 'admin':
            matrix_manager = MatrixManager()
            all_units = matrix_manager.get_all_units()
            unit_options = [unit['nome_unidade'] for unit in all_units]
            unit_options.insert(0, 'Global')
            current_unit_name = st.session_state.get('unit_name', 'Global')
            try:
                default_index = unit_options.index(current_unit_name)
            except ValueError:
                default_index = 0

            selected_admin_unit = st.selectbox(
                "Operar como Unidade:",
                options=unit_options,
                index=default_index,
                key="admin_unit_selector"
            )

            if selected_admin_unit != current_unit_name:
                if selected_admin_unit == 'Global':
                    st.session_state.unit_name = 'Global'
                    st.session_state.spreadsheet_id = None
                    st.session_state.folder_id = None
                else:
                    selected_unit_info = matrix_manager.get_unit_info(selected_admin_unit)
                    if selected_unit_info:
                        st.session_state.unit_name = selected_unit_info['nome_unidade']
                        st.session_state.spreadsheet_id = selected_unit_info['spreadsheet_id']
                        st.session_state.folder_id = selected_unit_info['folder_id']
                    else:
                        st.error(f"Informações para a unidade '{selected_admin_unit}' não encontradas.")
                        st.session_state.unit_name = 'Global'
                        st.session_state.spreadsheet_id = None
                        st.session_state.folder_id = None
                st.rerun()

        menu_items = {
            "Dashboard": {"icon": "clipboard2-data-fill", "function": show_dashboard_page},
            "Plano de Ação": {"icon": "clipboard2-check-fill", "function": show_plano_acao_page},
        }

        if user_role == 'admin':
            menu_items["Administração"] = {"icon": "gear-fill", "function": show_admin_page}

        selected_page = option_menu(
            menu_title="Menu Principal",
            options=list(menu_items.keys()),
            icons=[item["icon"] for item in menu_items.values()],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "0 !important", "background-color": "transparent"},
                "icon": {"color": "inherit", "font-size": "15px"},
                "nav-link": {"font-size": "12px", "text-align": "left", "margin": "0px", "--hover-color": "rgba(255, 255, 255, 0.1)" if st.get_option("theme.base") == "dark" else "#f0f2f6"},
                "nav-link-selected": {"background-color": st.get_option("theme.primaryColor")},
            }
        )
        show_logout_button()
    
    if selected_page in menu_items:
        page_function = menu_items[selected_page]["function"]
        page_function()

if __name__ == "__main__":
    main()
