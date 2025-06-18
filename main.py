import streamlit as st
import sys
import os


root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

def configurar_pagina():
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

a
configurar_pagina()


st.title("Bem-vindo ao SSO AI 🛡️")
st.write("Navegue pelas páginas na barra lateral para começar.")
st.info("O login é necessário para acessar as funcionalidades.")



