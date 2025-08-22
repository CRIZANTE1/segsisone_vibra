import streamlit as st
import os
import tempfile
import yaml
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from .config import get_credentials_dict

class GoogleApiManager:
    """
    Classe centralizada para interagir com as APIs do Google Drive e Google Sheets.
    Esta classe é "burra" e não conhece o st.session_state. Ela opera apenas
    com os IDs que recebe como argumentos.
    """
    def __init__(self):
        self.SCOPES = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
        try:
            credentials_dict = get_credentials_dict()
            self.credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=self.SCOPES
            )
            self.drive_service = build('drive', 'v3', credentials=self.credentials, cache_discovery=False)
            self.sheets_service = build('sheets', 'v4', credentials=self.credentials, cache_discovery=False)
        except Exception as e:
            st.error(f"Erro crítico ao inicializar os serviços do Google: {str(e)}")
            raise

    # --- Métodos do Google Drive ---

    def upload_file(self, folder_id: str, arquivo, novo_nome: str = None):
        """Faz upload de um arquivo para uma pasta específica no Google Drive."""
        if not folder_id:
            st.error("Erro de programação: ID da pasta não foi fornecido para o upload.")
            return None
        
        temp_file_path = None
        try:
            # Cria um arquivo temporário para garantir que o buffer seja lido corretamente
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(arquivo.name)[1]) as temp_file:
                temp_file.write(arquivo.getvalue())
                temp_file_path = temp_file.name

            file_metadata = {
                'name': novo_nome if novo_nome else arquivo.name,
                'parents': [folder_id]
            }
            media = MediaFileUpload(temp_file_path, mimetype=arquivo.type, resumable=True)
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink'
            ).execute()
            
            return file.get('webViewLink')

        except Exception as e:
            if "HttpError 404" in str(e):
                st.error(f"Erro no upload: A pasta do Google Drive com ID '{folder_id}' não foi encontrada ou a conta de serviço não tem permissão.")
            else:
                st.error(f"Erro ao fazer upload do arquivo: {str(e)}")
            return None
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def create_folder(self, name: str, parent_folder_id: str = None):
        """Cria uma nova pasta no Google Drive e retorna seu ID."""
        try:
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_folder_id:
                file_metadata['parents'] = [parent_folder_id]
            
            folder = self.drive_service.files().create(body=file_metadata, fields='id').execute()
            return folder.get('id')
        except Exception as e:
            st.error(f"Erro ao criar pasta no Google Drive: {e}")
            return None

    def move_file_to_folder(self, file_id: str, folder_id: str):
        """Move um arquivo para uma pasta específica no Google Drive."""
        try:
            file = self.drive_service.files().get(fileId=file_id, fields='parents').execute()
            previous_parents = ",".join(file.get('parents'))
            self.drive_service.files().update(
                fileId=file_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
        except Exception as e:
            st.error(f"Erro ao mover o arquivo para a pasta designada: {e}")

    # --- Métodos do Google Sheets ---

    def create_spreadsheet(self, name: str):
        """Cria uma nova Planilha Google e retorna seu ID."""
        try:
            spreadsheet_body = {'properties': {'title': name}}
            spreadsheet = self.sheets_service.spreadsheets().create(body=spreadsheet_body, fields='spreadsheetId').execute()
            return spreadsheet.get('spreadsheetId')
        except Exception as e:
            st.error(f"Erro ao criar nova planilha: {e}")
            return None

    def setup_sheets_from_config(self, spreadsheet_id: str, config_path: str = "sheets_config.yaml"):
        """Cria abas e cabeçalhos em uma nova planilha a partir de um arquivo YAML."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                sheets_config = yaml.safe_load(f)

            requests = []
            # Deleta a aba padrão "Página1" (sheetId 0)
            requests.append({'deleteSheet': {'sheetId': 0}})
            # Prepara a criação de todas as novas abas
            for sheet_name in sheets_config.keys():
                requests.append({'addSheet': {'properties': {'title': sheet_name}}})

            body = {'requests': requests}
            self.sheets_service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()

            # Adiciona os cabeçalhos em cada nova aba
            data_to_write = []
            for sheet_name, headers in sheets_config.items():
                data_to_write.append({
                    'range': f"{sheet_name}!A1",
                    'values': [headers]
                })

            body = {'valueInputOption': 'USER_ENTERED', 'data': data_to_write}
            self.sheets_service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
            return True

        except Exception as e:
            st.error(f"Erro ao configurar as abas da nova planilha: {e}")
            return False
