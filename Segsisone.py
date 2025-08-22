import streamlit as st
import sys
import os
from operations.front import front_page
from auth.login_page import show_login_page, show_user_header, show_logout_button
from auth.auth_utils import authenticate_user, is_admin # Import the new functions

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)


def configurar_pagina():
    st.set_page_config(
        page_title="SEGMA-SIS | Gestão Multi-Tenant",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="auto",
        menu_items={
            'Get Help': 'https://www.linkedin.com/in/cristian-ferreira-carlos-256b19161/',
            'Report a bug': "mailto:cristianfc2015@hotmail.com",
            'About': """
            ## SEGMA-SIS | Sistema de Gestão Inteligente
            
            Versão 2.0.0 (Multi-Tenant)
            """
        }
    )

def main():
    configurar_pagina()

    if show_login_page():
        # Após o login do Streamlit ser bem-sucedido, autenticamos no nosso sistema.
        if authenticate_user():
            show_user_header()
            show_logout_button()

            # Se o usuário for um admin global, não mostramos a página principal.
            # O Super_Admin.py será a sua "homepage".
            if is_admin() and st.session_state.get('unit_name') == 'Global':
                st.title("Painel de Super Administração")
                st.info("Selecione uma das páginas de administração na barra lateral.")
                st.warning("Você está logado como Administrador Global. As páginas de operação de tenant não estão disponíveis.")
            else:
                # Usuários normais e admins de unidade veem a página principal.
                front_page()
        else:
            # Se a autenticação falhar (usuário não encontrado, etc.), o auth_utils já mostrou o erro.
            # A execução é interrompida aqui.
            pass


if __name__ == "__main__":
    main()
    st.caption('Copyright 2025, Cristian Ferreira Carlos, Todos os direitos reservados.')
    st.caption('https://www.linkedin.com/in/cristian-ferreira-carlos-256b19161/')