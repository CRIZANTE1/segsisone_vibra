import streamlit as st
import sys
import os


root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)


from auth.login_page import show_login_page, is_user_logged_in


st.set_page_config(
    page_title="SSO AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="auto", # A sidebar será exibida
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

if is_user_logged_in():
   
    st.switch_page("pages/1_Visão_Geral.py")
else:
    show_login_page()


