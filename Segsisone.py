import streamlit as st
import sys
import os
import logging
from streamlit_option_menu import option_menu

# — Configuração do Logging —

logging.basicConfig(
level=logging.INFO,
format=’%(asctime)s - %(levelname)s - %(name)s - %(message)s’,
datefmt=’%Y-%m-%d %H:%M:%S’
)
logger = logging.getLogger(‘segsisone_app’)

# — Configuração do Caminho (Path) —

root_dir = os.path.dirname(os.path.abspath(**file**))
if root_dir not in sys.path:
sys.path.append(root_dir)

# — Importações —

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

def configurar_pagina():
st.set_page_config(
page_title=“SEGMA-SIS | Gestão Inteligente”,
page_icon=“🚀”,
layout=“wide”,
initial_sidebar_state=“expanded”
)

def initialize_managers():
“””
Função central para criar, destruir e gerenciar as instâncias dos managers.
“””
unit_id = st.session_state.get(‘spreadsheet_id’)
folder_id = st.session_state.get(‘folder_id’)

```
if unit_id and st.session_state.get('managers_unit_id') != unit_id:
    logger.info(f"Trocando de unidade. Inicializando managers para a unidade: ...{unit_id[-6:]}")
    
    # CORRIGIDO: Limpar managers antigos primeiro para evitar conflitos de estado
    old_keys_to_delete = [
        'employee_manager', 'docs_manager', 'epi_manager', 
        'action_plan_manager', 'nr_analyzer', 'matrix_manager_unidade'
    ]
    for key in old_keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]
    
    # CORRIGIDO: Adicionar try/catch robusto para cada manager
    with st.spinner("Configurando ambiente da unidade..."):
        try:
            # Verificar se folder_id é válido, usar string vazia como fallback
            folder_id_safe = folder_id if folder_id else ""
            
            # Inicializar managers um por um com verificação individual
            logger.info("Inicializando EmployeeManager...")
            st.session_state.employee_manager = EmployeeManager(unit_id, folder_id_safe)
            
            logger.info("Inicializando CompanyDocsManager...")
            st.session_state.docs_manager = CompanyDocsManager(unit_id, folder_id_safe)
            
            logger.info("Inicializando EPIManager...")
            st.session_state.epi_manager = EPIManager(unit_id)
            
            logger.info("Inicializando ActionPlanManager...")
            st.session_state.action_plan_manager = ActionPlanManager(unit_id)
            
            logger.info("Inicializando NRAnalyzer...")
            st.session_state.nr_analyzer = NRAnalyzer(unit_id)
            
            logger.info("Inicializando TrainingMatrixManager...")
            st.session_state.matrix_manager_unidade = TrainingMatrixManager(unit_id)
            
            # CORRIGIDO: Verificar se todos foram inicializados corretamente
            required_managers = [
                'employee_manager', 'docs_manager', 'epi_manager', 
                'action_plan_manager', 'nr_analyzer', 'matrix_manager_unidade'
            ]
            
            failed_managers = []
            for manager_name in required_managers:
                if manager_name not in st.session_state:
                    failed_managers.append(manager_name)
            
            if failed_managers:
                raise Exception(f"Falha ao inicializar: {', '.join(failed_managers)}")
            
            # CORRIGIDO: Verificar se os managers têm data_loaded_successfully
            managers_with_data_check = ['employee_manager', 'docs_manager', 'action_plan_manager']
            failed_data_loads = []
            
            for manager_name in managers_with_data_check:
                manager = st.session_state.get(manager_name)
                if manager and hasattr(manager, 'data_loaded_successfully') and not manager.data_loaded_successfully:
                    failed_data_loads.append(manager_name)
            
            if failed_data_loads:
                logger.warning(f"Managers com falha no carregamento de dados: {', '.join(failed_data_loads)}")
                st.warning(f"Alguns dados podem não estar disponíveis: {', '.join(failed_data_loads)}")
                    
        except Exception as e:
            logger.error(f"Erro ao inicializar managers: {e}", exc_info=True)
            st.error(f"Erro ao configurar ambiente da unidade: {e}")
            
            # CORRIGIDO: Limpar estado inconsistente completamente
            for key in old_keys_to_delete + ['managers_unit_id', 'managers_initialized']:
                if key in st.session_state:
                    del st.session_state[key]
            
            st.session_state.managers_initialized = False
            return
        
    st.session_state.managers_unit_id = unit_id
    st.session_state.managers_initialized = True
    logger.info("Managers da unidade inicializados com sucesso.")

elif not unit_id:
    # CORRIGIDO: Limpeza mais robusta quando não há unidade selecionada
    if st.session_state.get('managers_initialized', False):
        logger.info("Nenhuma unidade selecionada. Resetando managers da unidade.")
        keys_to_delete = [
            'employee_manager', 'docs_manager', 'epi_manager', 
            'action_plan_manager', 'nr_analyzer', 'managers_unit_id', 
            'matrix_manager_unidade', 'managers_initialized'
        ]
        for key in keys_to_delete:
            if key in st.session_state:
                del st.session_state[key]
    st.session_state.managers_initialized = False

# CORRIGIDO: Inicialização mais robusta do MatrixManager global
if 'matrix_manager' not in st.session_state:
    logger.info("Inicializando MatrixManager global...")
    try:
        st.session_state.matrix_manager = MatrixManager()
        
        # CORRIGIDO: Verificar se o MatrixManager foi inicializado corretamente
        if not st.session_state.matrix_manager.data_loaded_successfully:
            logger.error("MatrixManager global falhou ao carregar dados.")
            st.error("Erro crítico: Não foi possível carregar dados do sistema de controle.")
        else:
            logger.info("MatrixManager global inicializado com sucesso.")
            
    except Exception as e:
        logger.error(f"Erro ao inicializar MatrixManager global: {e}", exc_info=True)
        st.error("Erro crítico: Não foi possível inicializar o sistema de controle de usuários.")
        # CORRIGIDO: Não interromper totalmente, permitir que o app continue sem algumas funcionalidades
        st.warning("Algumas funcionalidades administrativas podem não estar disponíveis.")
```

def main():
configurar_pagina()

```
# CORRIGIDO: Verificação mais robusta de autenticação
if not is_user_logged_in():
    show_login_page()
    st.stop()

# CORRIGIDO: Tentar autenticar e capturar erros
try:
    if not authenticate_user():
        st.error("Falha na autenticação. Tente fazer login novamente.")
        st.stop()
except Exception as e:
    logger.error(f"Erro durante autenticação: {e}", exc_info=True)
    st.error("Erro no sistema de autenticação. Contate o administrador.")
    st.stop()

# A inicialização dos managers acontece aqui, após a autenticação.
try:
    initialize_managers()
except Exception as e:
    logger.error(f"Erro crítico na inicialização dos managers: {e}", exc_info=True)
    st.error("Erro crítico no sistema. Contate o administrador.")
    st.stop()

with st.sidebar:
    show_user_header()
    user_role = get_user_role()

    if user_role == 'admin':
        # CORRIGIDO: Verificar se matrix_manager existe antes de usar
        if 'matrix_manager' not in st.session_state:
            st.error("Sistema de controle não está disponível.")
            st.stop()
            
        matrix_manager = st.session_state.matrix_manager
        
        try:
            all_units = matrix_manager.get_all_units()
            unit_options = [unit['nome_unidade'] for unit in all_units]
            unit_options.insert(0, 'Global')
            current_unit_name = st.session_state.get('unit_name', 'Global')
            
            try:
                default_index = unit_options.index(current_unit_name)
            except ValueError:
                logger.warning(f"Unidade atual '{current_unit_name}' não encontrada na lista. Usando 'Global'.")
                default_index = 0

            selected_admin_unit = st.selectbox(
                "Operar como Unidade:", options=unit_options,
                index=default_index, key="admin_unit_selector"
            )

            if selected_admin_unit != current_unit_name:
                logger.info(f"Admin trocando de unidade: de '{current_unit_name}' para '{selected_admin_unit}'.")
                
                if selected_admin_unit == 'Global':
                    st.session_state.unit_name = 'Global'
                    st.session_state.spreadsheet_id = None
                    st.session_state.folder_id = None
                else:
                    unit_info = matrix_manager.get_unit_info(selected_admin_unit)
                    if unit_info:
                        st.session_state.unit_name = unit_info['nome_unidade']
                        st.session_state.spreadsheet_id = unit_info['spreadsheet_id']
                        st.session_state.folder_id = unit_info['folder_id']
                    else:
                        logger.error(f"Informações da unidade '{selected_admin_unit}' não encontradas.")
                        st.error(f"Erro: Informações da unidade '{selected_admin_unit}' não encontradas.")
                
                # Força a re-inicialização dos managers no próximo ciclo
                st.session_state.managers_unit_id = None 
                st.rerun()
                
        except Exception as e:
            logger.error(f"Erro ao carregar unidades para admin: {e}", exc_info=True)
            st.error("Erro ao carregar lista de unidades.")

    # CORRIGIDO: Menu mais robusto com verificação de permissões
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
            styles={
                "container": {"padding": "0 !important", "background-color": "transparent"},
                "icon": {"color": "inherit", "font-size": "15px"},
                "nav-link": {"font-size": "12px", "text-align": "left", "margin": "0px", "--hover-color": "rgba(255, 255, 255, 0.1)" if st.get_option("theme.base") == "dark" else "#f0f2f6"},
                "nav-link-selected": {"background-color": st.get_option("theme.primaryColor")},
            }
        )
    except Exception as e:
        logger.error(f"Erro ao renderizar menu: {e}", exc_info=True)
        st.error("Erro no menu principal.")
        selected_page = "Dashboard"  # Fallback para dashboard
        
    show_logout_button()

# CORRIGIDO: Execução de página mais robusta com tratamento de erro
page_to_run = menu_items.get(selected_page)
if page_to_run:
    logger.info(f"Navegando para a página: {selected_page}")
    try:
        page_to_run["function"]()
    except Exception as e:
        logger.error(f"Erro ao executar página '{selected_page}': {e}", exc_info=True)
        st.error(f"Erro ao carregar a página '{selected_page}'. Contate o administrador.")
        
        # CORRIGIDO: Mostrar informações de debug para admin
        if user_role == 'admin':
            with st.expander("Informações de Debug (Admin)"):
                st.code(f"Erro: {str(e)}")
                st.code(f"Managers inicializados: {st.session_state.get('managers_initialized', False)}")
                st.code(f"Unidade atual: {st.session_state.get('unit_name', 'N/A')}")
else:
    logger.error(f"Página '{selected_page}' não encontrada no menu.")
    st.error("Página não encontrada.")
```

if **name** == “**main**”:
try:
main()
except Exception as e:
logger.critical(f”Erro crítico na aplicação: {e}”, exc_info=True)
st.error(“Erro crítico na aplicação. Recarregue a página.”)
st.exception(e)