import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import streamlit as st
from gdrive.config import get_credentials_dict
import tempfile
from google.auth.transport.requests import Request

class GoogleDriveUploader:
    def __init__(self, folder_id: str):
        """
        Inicializa o uploader para uma pasta específica do Google Drive.
        Args:
            folder_id (str): O ID da pasta do tenant no Google Drive.
        """
        self.folder_id = folder_id
        self.SCOPES = [
            'https://www.googleapis.com/auth/drive.file',
        ]
        self.credentials = None
        self.drive_service = None
        self.initialize_services()

    def initialize_services(self):
        """Inicializa os serviços do Google Drive."""
        try:
            credentials_dict = get_credentials_dict()
            self.credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=self.SCOPES
            )
            self.drive_service = build('drive', 'v3', credentials=self.credentials, cache_discovery=False)
        except Exception as e:
            st.error(f"Erro ao inicializar serviços do Google: {str(e)}")
            raise

    def upload_file(self, arquivo, novo_nome=None):
        """
        Faz upload do arquivo para a pasta do tenant no Google Drive.
        """
        progress_bar = st.progress(0)
        temp_file = None
        try:
            progress_bar.progress(10)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(arquivo.name)[1])
            temp_file.write(arquivo.getbuffer())
            temp_file.close()

            temp_path = temp_file.name
            progress_bar.progress(30)

            file_metadata = {
                'name': novo_nome if novo_nome else arquivo.name,
                'parents': [self.folder_id]
            }
            progress_bar.progress(50)

            media = MediaFileUpload(
                temp_path,
                mimetype=arquivo.type,
                resumable=True
            )
            progress_bar.progress(70)

            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink'
            ).execute()
            progress_bar.progress(100)
            st.success("Upload concluído com sucesso!")

            return file.get('webViewLink')

        except Exception as e:
            if "HttpError 404" in str(e) and self.folder_id in str(e):
                st.error(f"Erro: A pasta do Google Drive com ID '{self.folder_id}' não foi encontrada ou as permissões estão incorretas.")
            else:
                st.error(f"Erro ao fazer upload do arquivo: {str(e)}")
            raise
        finally:
            if temp_file and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e_remove:
                    st.error(f"Erro ao remover arquivo temporário '{temp_path}': {str(e_remove)}")

    def delete_file_by_url(self, file_url: str):
        """
        Deleta um arquivo do Google Drive usando sua URL de visualização.
        """
        if not file_url:
            return False
            
        try:
            file_id = file_url.split('/d/')[1].split('/')[0]
        except IndexError:
            st.error(f"URL do Google Drive inválida: {file_url}")
            return False
            
        try:
            self.drive_service.files().delete(fileId=file_id).execute()
            return True
        except Exception as e:
            st.error(f"Erro ao deletar arquivo do Google Drive: {e}")
            return False