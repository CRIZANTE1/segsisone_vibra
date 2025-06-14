import os
import json
import streamlit as st

# ID da pasta no Google Drive onde os arquivos serão salvos
GDRIVE_FOLDER_ID = "1DWXCSH9G1vIfrgUIEOPWRxaHsFuhSgcs"

# ID da planilha 
GDRIVE_SHEETS_ID = "1Sw5EfdPIgAsPddCoHY-bO-91JyWAZpK4xW7FjZIz4Vw"


# Nome das abas na planilha
ASO_SHEET_NAME = "asos"  # Aba para ASOs
EMPLOYEE_SHEET_NAME = "empresas"  # Aba para empresas
EMPLOYEE_DATA_SHEET_NAME = "funcionarios"  # Aba para funcionários
TRAINING_SHEET_NAME = "treinamento"  # Aba para treinamentos
ADM_SHEET_NAME = "ADM"  # Aba para administradores
COMPANY_DOCS_SHEET_NAME = "documentos_empresa"

def get_credentials_dict():
    """Retorna as credenciais do serviço do Google, seja do arquivo local ou do Streamlit Cloud."""
    if st.runtime.exists():
        # Se estiver rodando no Streamlit Cloud ou com secrets configurados
        try:
            return {
                "type": st.secrets.connections.gsheets.type,
                "project_id": st.secrets.connections.gsheets.project_id,
                "private_key_id": st.secrets.connections.gsheets.private_key_id,
                "private_key": st.secrets.connections.gsheets.private_key,
                "client_email": st.secrets.connections.gsheets.client_email,
                "client_id": st.secrets.connections.gsheets.client_id,
                "auth_uri": st.secrets.connections.gsheets.auth_uri,
                "token_uri": st.secrets.connections.gsheets.token_uri,
                "auth_provider_x509_cert_url": st.secrets.connections.gsheets.auth_provider_x509_cert_url,
                "client_x509_cert_url": st.secrets.connections.gsheets.client_x509_cert_url,
                "universe_domain": st.secrets.connections.gsheets.universe_domain
            }
        except Exception as e:
            st.error("Erro ao carregar credenciais do Google do Streamlit Secrets. Certifique-se de que as credenciais estão configuradas corretamente em [connections.gsheets].")
            raise e
    else:
        # Se estiver rodando localmente
        credentials_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
        try:
            with open(credentials_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Erro ao carregar credenciais do arquivo local: {str(e)}")
            raise e

