import pygsheets
import streamlit as st
from gdrive.config import get_credentials_dict, GDRIVE_SHEETS_ID
import json
import tempfile
import os
import logging

def connect_sheet():
    """
    Estabelece conexão com o Google Sheets usando as credenciais fornecidas.
    
    Returns:
        tuple: (credentials, sheet_url) onde credentials é o objeto de autenticação
               e sheet_url é a URL da planilha
    """
    try:
        # Obter as credenciais
        credentials_dict = get_credentials_dict()
        
        # Criar um arquivo temporário para as credenciais
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(credentials_dict, f)
            temp_credentials_path = f.name
        
        try:
            # Autorizar usando o arquivo temporário
            gc = pygsheets.authorize(service_file=temp_credentials_path)
            
            # Construir a URL da planilha
            sheet_url = f"https://docs.google.com/spreadsheets/d/{GDRIVE_SHEETS_ID}"
            
            logging.info("Conexão com Google Sheets estabelecida com sucesso.")
            return gc, sheet_url
            
        finally:
            # Sempre remover o arquivo temporário
            try:
                os.unlink(temp_credentials_path)
            except Exception as e:
                logging.warning(f"Erro ao remover arquivo temporário de credenciais: {e}")
                
    except Exception as e:
        logging.error(f"Erro ao conectar com Google Sheets: {e}")
        st.error(f"Erro ao conectar com Google Sheets: {e}")
        return None, None 