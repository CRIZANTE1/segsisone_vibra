import streamlit as st
import sys
import os
import logging
from streamlit_option_menu import option_menu

# --- Configuração do Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('segsisone_app')

# --- Configuração do Caminho (Path) ---
try:
    root_dir = os.path.dirname(os.path.abspath(__file__))
    if root_dir not in sys.path:
        sys.path.append(root_dir)
except NameError:
    # __file__ não está definido em todos os contextos (ex: alguns notebooks)
    # Adiciona o diretório de trabalho atual como fallback
    if os.getcwd() not in sys.path:
        sys.path.append(os.getcwd())

def configurar_pagina():
    st.set_page_config(
        page_title="SEGMA-SIS | Gestão Inteligente",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )

def safe_import_modules():
    """Importa módulos de forma segura com tratamento de erro."""
    try:
        global show_login_page, show_user_header, show_logout_button
        global authenticate_user, is_user_logged_in, get_user_role
        global MatrixManager, TrainingMatrixManager
        global show_dashboard_page, show_admin_page, show_plano_acao_page
        global EmployeeManager, CompanyDocsManager, EPIManager, ActionPlanManager, NRAnalyzer

        from auth.login_page import show_login_page, show_user_header, show_logout_button
        from auth.auth_utils import authenticate_user, is_user_logged_in, get_user_role
        from gdrive.matrix_manager import MatrixManager
        from operations.training_matrix_manager import MatrixManager as TrainingMatrixManager
        from front.dashboard import show_dashboard_page
        from front.administracao import show_admin_page
        from front.plano_de_acao import show_plano_acao_page
        from operations.employee import EmployeeManager
        from operations.company_docs import CompanyDocsManager
        from operations.epi import EPIManager
        from operations.action_plan import ActionPlanManager
        from analysis.nr_analyzer import NRAnalyzer
        
        return True
    except ImportError as e:
        logger.error(f"Erro ao importar módulos: {e}")
        st.error(f"Erro crítico: Módulo não encontrado - {e}")
        return False
    except Exception as e:
        logger.error(f"Erro inesperado durante importação: {e}")
        st.error("Erro crítico durante inicialização do sistema.")
        return False

def safe_get_theme_style():
    """Retorna estilos seguros para o menu, independente do tema."""
    try:
        theme_base = st.get_option("theme.base")
        hover_color = "rgba(255, 255, 255, 0.1)" if theme_base == "dark" else "#f0f2f6"
    except:
        hover_color = "#f0f2f6"

    return {
        "container": {"padding": "0 !important", "background-color": "transparent"},
        "icon": {"color": "inherit", "font-size": "15px"},
        "nav-link": {"font-size": "12px", "text-align": "left", "margin": "0px", "--hover-color": hover_color},
        "nav-link-selected": {"background-color": "#FF4B4B"},
    }

def initialize_single_manager(manager_class, manager_name, *args):
    """Inicializa um manager específico com tratamento de erro robusto."""
    try:
        logger.info(f"Inicializando {manager_name}...")
        manager = manager_class(*args)

        if hasattr(manager, 'data_loaded_successfully'):
            if not manager.data_loaded_successfully:
                logger.warning(f"{manager_name} inicializado mas falhou ao carregar dados")
                return manager, False
            else:
                logger.info(f"{manager_name} inicializado com sucesso")
                return manager, True
        else:
            logger.info(f"{manager_name} inicializado (sem verificação de dados)")
            return manager, True
            
    except Exception as e:
        logger.error(f"Erro ao inicializar {manager_name}: {e}")
        return None, False

def initialize_managers():
    """Função central para criar, destruir e gerenciar as instâncias dos managers."""
    unit_id = st.session_state.get('spreadsheet_id')
    folder_id = st.session_state.get('folder_id')

    if unit_id and st.session_state.get('managers_unit_id') != unit_id:
        logger.info(f"Trocando de unidade. Inicializando managers para a unidade: ...{unit_id[-6:]}")
        
        old_keys_to_delete = ['employee_manager', 'docs_manager', 'epi_manager', 'action_plan_manager', 'nr_analyzer', 'matrix_manager_unidade']
        for key in old_keys_to_delete:
            st.session_state.pop(key, None)
        
        with st.spinner("Configurando ambiente da unidade..."):
            folder_id_safe = folder_id if folder_id else ""
            
            managers_to_init = [
                (EmployeeManager, 'employee_manager', unit_id, folder_id_safe),
                (CompanyDocsManager, 'docs_manager', unit_id, folder_id_safe),
                (EPIManager, 'epi_manager', unit_id),
                (ActionPlanManager, 'action_plan_manager', unit_id),
                (NRAnalyzer, 'nr_analyzer', unit_id),
                (TrainingMatrixManager, 'matrix_manager_unidade', unit_id),
            ]
            
            failed_managers, warning_managers = [], []
            
            for manager_class, manager_name, *args in managers_to_init:
                manager, success = initialize_single_manager(manager_class, manager_name, *args)
                if manager is None:
                    failed_managers.append(manager_name)
                else:
                    st.session_state[manager_name] = manager
                    if not success:
                        warning_managers.append(manager_name)
            
            if failed_managers:
                logger.error(f"Managers que falharam completamente: {failed_managers}")
                st.error(f"Erro crítico: Falha ao inicializar componentes essenciais: {', '.join(failed_managers)}")
                keys_to_reset = old_keys_to_delete + ['managers_unit_id', 'managers_initialized']
                for key in keys_to_reset:
                    st.session_state.pop(key, None)
                st.session_state.managers_initialized = False
                return
            
            if warning_managers:
                logger.warning(f"Managers com problemas de dados: {warning_managers}")
                st.warning(f"Atenção: Alguns componentes podem ter funcionalidade limitada: {', '.join(warning_managers)}")
        
        st.session_state.managers_unit_id = unit_id
        st.session_state.managers_initialized = True
        logger.info("Managers da unidade inicializados com sucesso.")

    elif not unit_id and st.session_state.get('managers_initialized', False):
        logger.info("Nenhuma unidade selecionada. Resetando managers da unidade.")
        keys_to_delete = ['employee_manager', 'docs_manager', 'epi_manager', 'action_plan_manager', 'nr_analyzer', 'managers_unit_id', 'matrix_manager_unidade', 'managers_initialized']
        for key in keys_to_delete:
            st.session_state.pop(key, None)
        st.session_state.managers_initialized = False

    if 'matrix_manager' not in st.session_state:
        logger.info("Inicializando MatrixManager global...")
        matrix_manager, success = initialize_single_manager(MatrixManager, 'MatrixManager')
        if matrix_manager is None:
            logger.error("Falha crítica ao inicializar MatrixManager global")
            st.error("Erro crítico: Sistema de controle indisponível.")
            st.stop()
        else:
            st.session_state.matrix_manager = matrix_manager
            if not success:
                st.warning("Sistema de controle inicializado com funcionalidade limitada.")

def main():
    configurar_pagina()

    if not safe_import_modules():
        st.stop()

    if not is_user_logged_in():
        show_login_page()
        st.stop()

    try:
        if not authenticate_user():
            st.error("Falha na autenticação. Tente fazer login novamente.")
            st.stop()
    except Exception as e:
        logger.error(f"Erro durante autenticação: {e}")
        st.error("Erro no sistema de autenticação. Contate o administrador.")
        st.stop()

    try:
        initialize_managers()
    except Exception as e:
        logger.error(f"Erro crítico na inicialização dos managers: {e}")
        st.error("Erro crítico no sistema. Recarregue a página.")
        st.stop()

    with st.sidebar:
        show_user_header()
        user_role = get_user_role()

        if user_role == 'admin':
            if 'matrix_manager' in st.session_state:
                matrix_manager = st.session_state.matrix_manager
                try:
                    all_units = matrix_manager.get_all_units()
                    unit_options = [unit['nome_unidade'] for unit in all_units]
                    unit_options.insert(0, 'Global')
                    current_unit_name = st.session_state.get('unit_name', 'Global')
                    
                    try:
                        default_index = unit_options.index(current_unit_name)
                    except ValueError:
                        default_index = 0

                    selected_admin_unit = st.selectbox(
                        "Operar como Unidade:", options=unit_options,
                        index=default_index, key="admin_unit_selector"
                    )

                    if selected_admin_unit != current_unit_name:
                        logger.info(f"Admin trocando de unidade: '{current_unit_name}' → '{selected_admin_unit}'")
                        if selected_admin_unit == 'Global':
                            st.session_state.unit_name = 'Global'
                            st.session_state.spreadsheet_id = None
                            st.session_state.folder_id = None
                        else:
                            unit_info = matrix_manager.get_unit_info(selected_admin_unit)
                            if unit_info:
                                st.session_state.update(unit_info)
                        st.session_state.managers_unit_id = None 
                        st.rerun()
                except Exception as e:
                    logger.error(f"Erro ao carregar unidades: {e}")
                    st.error("Erro ao carregar lista de unidades.")
        
        menu_items = {
            "Dashboard": {"icon": "clipboard2-data-fill", "function": show_dashboard_page},
            "Plano de Ação": {"icon": "clipboard2-check-fill", "function": show_plano_acao_page},
        }
        if user_role == 'admin':
            menu_items["Administração"] = {"icon": "gear-fill", "function": show_admin_page}

        try:
            selected_page = option_menu(
                menu_title="Menu Principal",
                options=list(menu_items.keys()),
                icons=[item["icon"] for item in menu_items.values()],
                menu_icon="cast",
                default_index=0,
                styles=safe_get_theme_style()
            )
        except Exception as e:
            logger.error(f"Erro ao renderizar menu: {e}")
            st.error("Erro no menu principal.")
            selected_page = "Dashboard"
            
        show_logout_button()

    page_to_run = menu_items.get(selected_page)
    if page_to_run:
        logger.info(f"Navegando para: {selected_page}")
        try:
            page_to_run["function"]()
        except Exception as e:
            logger.error(f"Erro na página '{selected_page}': {e}")
            st.error(f"Erro ao carregar '{selected_page}'. Contate o administrador.")
            if user_role == 'admin':
                with st.expander("Debug Info (Admin Only)"):
                    st.code(f"Erro: {str(e)}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Erro não capturado na execução principal: {e}", exc_info=True)
        st.error("Ocorreu um erro crítico na aplicação. Por favor, recarregue a página.")
        if st.button("Recarregar"):
            st.rerun()