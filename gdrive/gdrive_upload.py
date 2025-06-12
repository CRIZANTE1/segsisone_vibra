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

    def upload_file(self, arquivo, novo_nome=None): # Adicionado novo_nome como parâmetro
        """
        Faz upload do arquivo para o Google Drive
        
        Args:
            arquivo: StreamlitUploadedFile object
            novo_nome (str, optional): Nome a ser dado ao arquivo no Drive. Se None, usa o nome original.
        
        Returns:
            str: URL de visualização do arquivo
        """
        st.info("Iniciando processo de upload do arquivo.") # Log adicionado
        temp_file = None # Inicializa temp_file como None
        try:
            st.info("Criando arquivo temporário.") # Log adicionado
            # Criar arquivo temporário usando tempfile
            # delete=False para que o arquivo não seja excluído automaticamente ao fechar
            # e possamos passá-lo para MediaFileUpload
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(arquivo.name)[1])
            temp_file.write(arquivo.getbuffer())
            temp_file.close() # Fechar o arquivo para liberar o handle

            temp_path = temp_file.name # Obter o caminho do arquivo temporário
            st.info(f"Arquivo temporário criado em: {temp_path}") # Log adicionado

            # Preparar metadata
            st.info("Preparando metadados do arquivo.") # Log adicionado
            file_metadata = {
                'name': novo_nome if novo_nome else arquivo.name, # Usa novo_nome se fornecido
                'parents': [GDRIVE_FOLDER_ID]
            }
            st.info(f"Metadados: {file_metadata}") # Log adicionado

            # Preparar upload
            st.info("Preparando upload de mídia.") # Log adicionado
            media = MediaFileUpload(
                temp_path,
                mimetype=arquivo.type,
                resumable=True
            )
            st.info(f"Tipo MIME do arquivo: {arquivo.type}") # Log adicionado

            # Fazer upload
            st.info("Executando upload para o Google Drive.") # Log adicionado
            file = self.drive_service.files().create( # Usar self.drive_service
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink'
            ).execute()
            st.info("Upload concluído com sucesso.") # Log adicionado

            return file.get('webViewLink')

        except Exception as e:
            if "HttpError 404" in str(e) and GDRIVE_FOLDER_ID in str(e):
                st.error(f"Erro: A pasta do Google Drive com ID '{GDRIVE_FOLDER_ID}' não foi encontrada ou as permissões estão incorretas. Por favor, verifique se o ID da pasta está correto em 'gdrive/config.py' e se a conta de serviço tem permissão de 'Editor' ou 'Colaborador' para esta pasta.")
            else:
                st.error(f"Erro ao fazer upload do arquivo: {str(e)}")
            raise
        finally: # Garante que o arquivo temporário seja removido
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


