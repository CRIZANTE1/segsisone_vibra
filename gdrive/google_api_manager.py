# gdrive/google_api_manager.py (VERSÃO CORRIGIDA E COMPLETA)

import streamlit as st
import os
import tempfile
import yaml
import gspread  # <-- IMPORTAÇÃO NECESSÁRIA
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from .config import get_credentials_dict

class GoogleApiManager:
    """
    Classe centralizada para interagir com as APIs do Google Drive e Google Sheets.
    Usa tanto a biblioteca googleapiclient (para Drive e uploads) quanto gspread
    (para operações convenientes em planilhas).
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
            # Cliente de baixo nível para Drive e Sheets API
            self.drive_service = build('drive', 'v3', credentials=self.credentials, cache_discovery=False)
            self.sheets_service = build('sheets', 'v4', credentials=self.credentials, cache_discovery=False)
            
            # --- CLIENTE GSPREAD ADICIONADO AQUI ---
            # Cliente de alto nível (gspread) para operações de planilha mais fáceis
            self.gspread_client = gspread.authorize(self.credentials)

        except Exception as e:
            st.error(f"Erro crítico ao inicializar os serviços do Google: {str(e)}")
            raise

    # --- MÉTODO GSPREAD (ESTAVA FALTANDO) ---
    def open_spreadsheet(self, spreadsheet_id: str):
        """Abre uma planilha usando gspread pelo seu ID."""
        try:
            return self.gspread_client.open_by_key(spreadsheet_id)
        except gspread.exceptions.SpreadsheetNotFound:
            st.error(f"A planilha com ID '{spreadsheet_id}' não foi encontrada.")
            return None
        except Exception as e:
            st.error(f"Erro ao abrir a planilha com gspread: {e}")
            return None

    # --- Métodos do Google Drive ---

    def upload_file(self, folder_id: str, arquivo, novo_nome: str = None):
        """Faz upload de um arquivo para uma pasta específica no Google Drive."""
        if not folder_id:
            st.error("Erro de programação: ID da pasta não foi fornecido para o upload.")
            return None
        
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(arquivo.name)[1]) as temp_file:
                temp_file.write(arquivo.getvalue())
                temp_file_path = temp_file.name

            file_metadata = {
                'name': novo_nome if novo_nome else arquivo.name,
                'parents': [folder_id]
            }
            media = MediaFileUpload(temp_file_path, mimetype=arquivo.type, resumable=True)
            
            file = self.drive_service.files().create(
                body=file_metadata, media_body=media, fields='id,webViewLink'
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
            file_metadata = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
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
                fileId=file_id, addParents=folder_id, removeParents=previous_parents, fields='id, parents'
            ).execute()
        except Exception as e:
            st.error(f"Erro ao mover o arquivo para a pasta designada: {e}")

    # --- Métodos do Google Sheets (API de baixo nível) ---

    def create_spreadsheet(self, name: str, folder_id: str = None):
        """Cria uma nova Planilha Google e retorna seu ID."""
        try:
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.spreadsheet'
            }
            if folder_id:
                file_metadata['parents'] = [folder_id]
                
            spreadsheet_file = self.drive_service.files().create(
                body=file_metadata, fields='id'
            ).execute()
            spreadsheet_id = spreadsheet_file.get('id')
            return spreadsheet_id
        except Exception as e:
            st.error(f"Erro ao criar nova planilha: {e}")
            return None

    def setup_sheets_from_config(self, spreadsheet_id: str, config_path: str = "sheets_config.yaml"):
        """Cria abas e cabeçalhos em uma nova planilha a partir de um arquivo YAML."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                sheets_config = yaml.safe_load(f)

            spreadsheet = self.open_spreadsheet(spreadsheet_id)
            if not spreadsheet:
                return False
                
            default_sheet = spreadsheet.sheet1
            is_first = True
            for sheet_name, columns in sheets_config.items():
                if is_first:
                    worksheet = default_sheet
                    worksheet.update_title(sheet_name)
                    is_first = False
                else:
                    worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1", cols=len(columns))
                worksheet.update('A1', [columns])
            return True

        except Exception as e:
            st.error(f"Erro ao configurar as abas da nova planilha: {e}")
            return False
