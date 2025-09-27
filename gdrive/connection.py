import gspread
import streamlit as st
from gdrive.config import get_credentials_dict, MATRIX_SPREADSHEET_ID  
import logging

def connect_sheet():
    """
    Estabelece conexão com o Google Sheets usando gspread.
    
    Returns:
        tuple: (gspread_client, sheet_url)
    """
    try:
        credentials_dict = get_credentials_dict()
        
        gc = gspread.service_account_from_dict(credentials_dict)
        
        sheet_url = f"https://docs.google.com/spreadsheets/d/{MATRIX_SPREADSHEET_ID}"
        
        logging.info("Conexão com Google Sheets (gspread) estabelecida com sucesso.")
        return gc, sheet_url
            
    except Exception as e:
        logging.error(f"Erro ao conectar com Google Sheets via gspread: {e}")
        st.error(f"Erro ao conectar com Google Sheets: {e}")
        return None, None

