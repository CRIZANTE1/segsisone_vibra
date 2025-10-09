import streamlit as st
import google.generativeai as genai
import logging

logging.basicConfig(level=logging.INFO)

def load_models():
    """
    Carrega e configura dois modelos Gemini distintos, um para extração e outro para auditoria,
    usando chaves de API separadas dos secrets do Streamlit.
    """
    extraction_model = None
    audit_model = None

    try:
        extraction_key = st.secrets.get("general", {}).get("GEMINI_EXTRACTION_KEY")
        if extraction_key:
            genai.configure(api_key=extraction_key)
            extraction_model = genai.GenerativeModel('gemini-2.5-flash') 
            logging.info("Modelo de EXTRAÇÃO carregado com sucesso.")
        else:
            st.warning("Chave 'GEMINI_EXTRACTION_KEY' não encontrada nos secrets. Funções de extração de dados serão desativadas.")

        audit_key = st.secrets.get("general", {}).get("GEMINI_AUDIT_KEY")
        if audit_key:
            genai.configure(api_key=audit_key)
            audit_model = genai.GenerativeModel('gemini-2.5-pro')
            logging.info("Modelo de AUDITORIA carregado com sucesso.")
        else:
            st.warning("Chave 'GEMINI_AUDIT_KEY' não encontrada nos secrets. Funções de auditoria serão desativadas.")

        return extraction_model, audit_model

    except Exception as e:
        st.error(f"Erro crítico ao carregar os modelos de IA: {e}")
        return None, None








