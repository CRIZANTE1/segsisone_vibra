import streamlit as st
import sys
import os

# Adiciona o diretório raiz ao PYTHONPATH
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from auth.login_page import show_login_page, is_user_logged_in

# Configuração da página
st.set_page_config(
    page_title="SSO AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        'Get Help': 'https://www.streamlit.io/community',
        'Report a bug': "mailto:cristianfc2015@hotmail.com",
        'About': """
        ## SSO AI
        Sistema de Análise Inteligente de Documentos de SSO.
        Versão 1.0.1
        """
    }
)


hide_main_nav_link_style = """
    <style>
    div[data-testid="stSidebarNav"] > ul > li:first-child {
        display: none;
    }
    </style>
"""
st.markdown(hide_main_nav_link_style, unsafe_allow_html=True)

# Lógica de roteamento
if is_user_logged_in():
    st.switch_page("pages/1_Visão_Geral.py")
else:
    show_login_page()

