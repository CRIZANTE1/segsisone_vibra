import streamlit as st
from datetime import datetime
import json
from operations.sheet import SheetOperations
from gdrive.config import MATRIX_SPREADSHEET_ID, CENTRAL_LOG_SHEET_NAME
from auth.auth_utils import get_user_email

def log_action(action: str, details: dict):
    """
    Registra uma ação do usuário na aba de log central da Planilha Matriz.
    
    Args:
        action (str): A ação realizada (ex: "DELETE_ASO", "CREATE_COMPANY").
        details (dict): Um dicionário com detalhes relevantes sobre a ação.
    """
    try:
        # Coleta informações do contexto da sessão
        user_email = get_user_email() or "system"
        user_role = st.session_state.get('role', 'N/A')
        target_unit = st.session_state.get('unit_name', 'N/A')
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Converte o dicionário de detalhes para uma string JSON
        details_str = json.dumps(details, ensure_ascii=False)

        # Monta a linha de log
        log_row = [timestamp, user_email, user_role, action, details_str, target_unit]

        matrix_sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        matrix_sheet_ops.adc_dados_aba_sem_id(CENTRAL_LOG_SHEET_NAME, log_row)
        
        print(f"LOG SUCCESS: Action '{action}' by '{user_email}' logged successfully.")

    except Exception as e:
        print(f"LOG FAILED: Could not log action '{action}'. Reason: {e}")
        # Opcional: mostrar um aviso discreto na UI se o log falhar
        # st.toast(f"Aviso: Não foi possível registrar a ação '{action}' no log de auditoria.", icon="⚠️")
