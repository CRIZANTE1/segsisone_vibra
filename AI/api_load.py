from dotenv import load_dotenv
import os
import google.generativeai as genai
import streamlit as st
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_api():
    try:
        # Tentar carregar a chave API de múltiplas fontes
        api_key = None
        
        # 1. Tentar carregar de Streamlit secrets (produção)
        try:
            api_key = st.secrets["general"]["GOOGLE_API_KEY"]
            logging.info("API key loaded from Streamlit secrets.")
        except (KeyError, TypeError, AttributeError):
            logging.info("API key not found in Streamlit secrets, trying environment variables.")
        
        # 2. Se não encontrou nos secrets, tentar carregar do arquivo .env (desenvolvimento)
        if not api_key:
            # Load environment variables from .env file
            load_dotenv()
            api_key = os.getenv('GOOGLE_API_KEY')
            if api_key:
                logging.info("API key loaded from .env file.")

        # 3. Verificar se uma chave foi encontrada
        if not api_key:
            error_msg = "Google API key not found. Please set the GOOGLE_API_KEY environment variable or in Streamlit secrets."
            logging.error(error_msg)
            st.error(error_msg)
            return None

        # Configurar a API Gemini com a chave encontrada
        genai.configure(api_key=api_key)
        logging.info("API loaded successfully.")
        return genai

    except Exception as e:
        error_msg = f"Error loading API: {str(e)}"
        logging.exception(error_msg)
        st.error(error_msg)
        return None
