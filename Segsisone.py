# --- START OF FILE Segsisone.py (VERSÃO COM OPTION_MENU) ---

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
from front.dashboard import show_dashboard_page
from front.administracao import show_admin_page
from front.plano_de_acao import show_plano_acao_page

def configurar_pagina():
    st.set_page_config(
        page_title="SEGMA-SIS | Gestão Inteligente",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )

def main():
    configurar_pagina()

    if not is_user_logged_in():
        show_login_page()
        st.stop()
    
    # Se o usuário está logado, autentica no sistema e carrega o contexto do tenant
    if not authenticate_user():
        st.stop() # A autenticação falhou, a mensagem de erro já foi mostrada

    # --- LÓGICA DO MENU DE NAVEGAÇÃO ---
    with st.sidebar:
        show_user_header()

        # Obtém o papel do usuário para construir o menu dinamicamente
        user_role = get_user_role()
        
        # Opções de menu visíveis para todos
        menu_items = {
            "Dashboard": {"icon": "clipboard2-data-fill", "function": show_dashboard_page},
            "Plano de Ação": {"icon": "clipboard2-check-fill", "function": show_plano_acao_page},
        }

        # Adiciona a opção de Administração apenas se o usuário for 'admin'
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
    
    # --- Roteamento para a Página Selecionada ---
    if selected_page in menu_items:
        # Chama a função da página correspondente
        page_function = menu_items[selected_page]["function"]
        page_function()

if __name__ == "__main__":
    main()
