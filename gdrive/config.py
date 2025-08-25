# gdrive/config.py

import os
import json
import streamlit as st

# ID da Planilha Matriz que controla todos os tenants (unidades).
MATRIX_SPREADSHEET_ID = "15DCVTsjERd2_LyXMVla6V2BeO1g_uZbvLHzecT-eZts"

# ID da Pasta Raiz no Google Drive onde todas as pastas das unidades serão criadas.
CENTRAL_DRIVE_FOLDER_ID = "1klJot9630Hxo2vWLSDGQH-QC3yux5KT5"

# Nome da aba na planilha matriz para registrar os logs centralizados.
CENTRAL_LOG_SHEET_NAME = "log_auditoria"

def get_credentials_dict():
    """
    Retorna as credenciais do serviço do Google, seja do Streamlit Cloud,
    do GitHub Actions ou de um arquivo local.
    """
 
    if hasattr(st, 'runtime') and st.runtime.exists():
        try:
           
            return dict(st.secrets.connections.gsheets)
        except (AttributeError, KeyError) as e:
            st.error("Erro: As credenciais [connections.gsheets] não foram encontradas nos Secrets do Streamlit.")
            raise
    
    
    else:
        gcp_credentials_json = os.getenv("GCP_SERVICE_ACCOUNT_CREDENTIALS")
        if gcp_credentials_json:
            print("INFO: Credenciais encontradas na variável de ambiente (modo GitHub Actions).")
            try:
                return json.loads(gcp_credentials_json)
            except json.JSONDecodeError:
               
                print("ERRO: A variável de ambiente GCP_SERVICE_ACCOUNT_CREDENTIALS não contém um JSON válido.")
                raise

        print("INFO: Tentando carregar credenciais do arquivo local 'credentials.json' (modo de desenvolvimento).")
        credentials_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
        try:
            with open(credentials_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            
            raise FileNotFoundError(
                "Credenciais não encontradas. Para rodar fora do Streamlit Cloud, "
                "configure a variável de ambiente 'GCP_SERVICE_ACCOUNT_CREDENTIALS' "
                "ou coloque um arquivo 'credentials.json' na pasta 'gdrive/'."
            )
        except Exception as e:
           
            print(f"Erro ao carregar credenciais do arquivo local: {str(e)}")
            raise