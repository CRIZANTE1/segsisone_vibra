import streamlit as st
import sys
import os

# Adiciona o diretório raiz ao PYTHONPATH
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from operations.front import front_page
from auth.login_page import show_login_page, show_user_header, show_logout_button

def configurar_pagina():
    st.set_page_config(
        page_title="Gestão de Documentação de Contratada",
        page_icon=":clipboard:",
        layout="wide",
        initial_sidebar_state="auto",
        menu_items={
            'Get Help': 'https://www.streamlit.io/community',
            'Report a bug': "mailto:cristianfc2015@hotmail.com",
            'About': """
            ## Gestão de documentação de contratada
            
            Versão 1.0.0
            """
        }
    )

def main():
    configurar_pagina()
    if show_login_page():
        st.session_state.user = st.session_state.user if 'user' in st.session_state else None
        show_user_header()
        show_logout_button()
        
        # Adiciona navegação por abas para as diferentes páginas
        tab_empresas, tab_aso, tab_treinamentos = st.tabs(["Empresas", "ASO", "Treinamentos"])

        with tab_empresas:
            front_page()
        
        with tab_aso:
            st.header("Gestão de ASO")
            # Aqui será implementada a gestão de ASO
        
        with tab_treinamentos:
            st.header("Gestão de Treinamentos")
            # Aqui será implementada a gestão de treinamentos

if __name__ == "__main__":
    main()
    st.caption('Copyright 2024, Cristian Ferreira Carlos, Todos os direitos reservados.')
    st.caption('https://www.linkedin.com/in/cristian-ferreira-carlos-256b19161/')


