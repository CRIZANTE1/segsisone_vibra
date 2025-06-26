import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import streamlit as st
from gdrive.config import get_credentials_dict, GDRIVE_FOLDER_ID, GDRIVE_SHEETS_ID
import tempfile # Importar o módulo tempfile
from google.auth.transport.requests import Request

class GoogleDriveUploader:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GoogleDriveUploader, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.SCOPES = [
                'https://www.googleapis.com/auth/drive.file',
                'https://www.googleapis.com/auth/spreadsheets'
            ]
            self.credentials = None
            self.drive_service = None
            self.sheets_service = None
            self.initialize_services()
            self._initialized = True

    def initialize_services(self):
        """Inicializa os serviços do Google Drive e Google Sheets"""
        try:
            credentials_dict = get_credentials_dict()
            self.credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=self.SCOPES
            )
            # Desabilita o cache de arquivos
            self.drive_service = build('drive', 'v3', credentials=self.credentials, cache_discovery=False)
            self.sheets_service = build('sheets', 'v4', credentials=self.credentials, cache_discovery=False)
        except Exception as e:
            st.error(f"Erro ao inicializar serviços do Google: {str(e)}")
            raise

    def upload_file(self, arquivo, novo_nome=None):
        """
        Faz upload do arquivo para o Google Drive
        
        Args:
            arquivo: StreamlitUploadedFile object
            novo_nome (str, optional): Nome a ser dado ao arquivo no Drive. Se None, usa o nome original.
        
        Returns:
            str: URL de visualização do arquivo
        """
        progress_bar = st.progress(0)
        temp_file = None
        try:
            # Criar arquivo temporário
            progress_bar.progress(10)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(arquivo.name)[1])
            temp_file.write(arquivo.getbuffer())
            temp_file.close()

            temp_path = temp_file.name
            progress_bar.progress(30)

            # Preparar metadata
            file_metadata = {
                'name': novo_nome if novo_nome else arquivo.name,
                'parents': [GDRIVE_FOLDER_ID]
            }
            progress_bar.progress(50)

            # Preparar upload
            media = MediaFileUpload(
                temp_path,
                mimetype=arquivo.type,
                resumable=True
            )
            progress_bar.progress(70)

            # Fazer upload
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink'
            ).execute()
            progress_bar.progress(100)
            st.success("Upload concluído com sucesso!")

            return file.get('webViewLink')

        except Exception as e:
            if "HttpError 404" in str(e) and GDRIVE_FOLDER_ID in str(e):
                st.error(f"Erro: A pasta do Google Drive com ID '{GDRIVE_FOLDER_ID}' não foi encontrada ou as permissões estão incorretas. Por favor, verifique se o ID da pasta está correto em 'gdrive/config.py' e se a conta de serviço tem permissão de 'Editor' ou 'Colaborador' para esta pasta.")
            else:
                st.error(f"Erro ao fazer upload do arquivo: {str(e)}")
            raise
        finally:
            if temp_file and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e_remove:
                    st.error(f"Erro ao remover arquivo temporário '{temp_path}': {str(e_remove)}")

    def append_data_to_sheet(self, sheet_name, data_row):
        """
        Adiciona uma nova linha de dados à planilha do Google Sheets.
        
        Args:
            sheet_name (str): Nome da aba na planilha (ex: 'Dados_Icamento', 'Info_Guindauto').
            data_row (list): Uma lista de valores a serem adicionados como uma nova linha.
        
        Returns:
            dict: Resposta da API do Google Sheets.
        """
        try:
            range_name = f"{sheet_name}!A:Z" # Define o range para adicionar a linha
            body = {
                'values': [data_row]
            }
            result = self.sheets_service.spreadsheets().values().append( # Usar self.sheets_service
                spreadsheetId=GDRIVE_SHEETS_ID,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            return result
        except Exception as e:
            st.error(f"Erro ao adicionar dados à planilha '{sheet_name}': {str(e)}")
            raise

    def get_data_from_sheet(self, sheet_name):
        """
        Lê todos os dados de uma aba específica da planilha do Google Sheets.
        
        Args:
            sheet_name (str): Nome da aba na planilha.
        
        Returns:
            list: Uma lista de listas, representando as linhas e colunas da planilha.
        """
        try:
            range_name = f"{sheet_name}!A:Z" # Lê todas as colunas
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=GDRIVE_SHEETS_ID,
                range=range_name
            ).execute()
            values = result.get('values', [])
            return values
        except Exception as e:
            st.error(f"Erro ao ler dados da planilha '{sheet_name}': {str(e)}")
            raise
#----------------------teste----------------------------------  
    def delete_file_by_url(self, file_url: str):
        """
        Deleta um arquivo do Google Drive usando sua URL de visualização.
        
        Args:
            file_url (str): A URL 'webViewLink' do arquivo.
        
        Returns:
            bool: True se a exclusão foi bem-sucedida, False caso contrário.
        """
        if not file_url:
            return False
            
        # Extrai o ID do arquivo da URL
        try:
            file_id = file_url.split('/d/')[1].split('/')[0]
        except IndexError:
            st.error(f"URL do Google Drive inválida: {file_url}")
            return False
            
        try:
            print(f"Tentando deletar o arquivo com ID: {file_id}")
            self.drive_service.files().delete(fileId=file_id).execute()
            print(f"Arquivo com ID {file_id} deletado com sucesso.")
            return True
        except Exception as e:
            st.error(f"Erro ao deletar arquivo do Google Drive: {e}")
            return False
    
    
