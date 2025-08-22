import streamlit as st
import sys
import os
from streamlit_option_menu import option_menu

# --- Configuração do Caminho (Path) ---
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# --- Importações dos Módulos ---
from auth.login_page import show_login_page, show_user_header, show_logout_button
from auth.auth_utils import authenticate_user, is_user_logged_in, get_user_role
from gdrive.matrix_manager import MatrixManager
from front.dashboard import show_dashboard_page
from front.administracao import show_admin_page
from front.plano_de_acao import show_plano_acao_page
from operations.employee import EmployeeManager
from operations.company_docs import CompanyDocsManager
from operations.epi import EPIManager
from operations.action_plan import ActionPlanManager
from analysis.nr_analyzer import NRAnalyzer

def configurar_pagina():
    st.set_page_config(
        page_title="SEGMA-SIS | Gestão Inteligente",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )

def initialize_managers():
    """
    Ponto central para inicializar ou recarregar TODOS os gerenciadores.
    - Gerenciadores globais são criados uma vez.
    - Gerenciadores de tenant são (re)criados se a unidade mudar ou se uma recarga for solicitada.
    """
    # 1. Gerenciadores Globais
    if 'matrix_manager' not in st.session_state:
        st.session_state.matrix_manager = MatrixManager()

    # 2. Gerenciadores de Tenant
    unit_id = st.session_state.get('spreadsheet_id')
    
    # Condição para (re)criar: A unidade mudou OU uma recarga foi explicitamente solicitada.
    if unit_id and (st.session_state.get('managers_unit_id') != unit_id or st.session_state.get('force_reload', False)):
        with st.spinner("Carregando dados da unidade..."):
            # Limpa o cache de dados antes de recarregar
            st.cache_data.clear()
            
            st.session_state.employee_manager = EmployeeManager(unit_id, st.session_state.folder_id)
            st.session_state.docs_manager = CompanyDocsManager(unit_id)
            st.session_state.epi_manager = EPIManager(unit_id)
            st.session_state.action_plan_manager = ActionPlanManager(unit_id)
            st.session_state.nr_analyzer = NRAnalyzer(unit_id)
            
            st.session_state.managers_unit_id = unit_id
            st.session_state.managers_initialized = True
            st.session_state.force_reload = False # Reseta a flag
        
        # Rerun é crucial aqui para garantir que a UI inteira seja atualizada com os novos dados
        st.rerun()

    elif not unit_id:
        st.session_state.managers_initialized = False

def main():
    configurar_pagina()

    if not is_user_logged_in():
        show_login_page()
        st.stop()
    
    if not authenticate_user():
        st.stop()

    initialize_managers()

    with st.sidebar:
        show_user_header()
        user_role = get_user_role()

        if user_role == 'admin':
            matrix_manager = st.session_state.matrix_manager
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
