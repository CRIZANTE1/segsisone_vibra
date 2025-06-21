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
AUDIT_RESULTS_SHEET_NAME = "auditorias"
COMPANY_DOCS_SHEET_NAME = "documentos_empresa"

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
