import gspread
import yaml
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from .config import get_credentials_dict

class GoogleApiManager:
    """
    Centraliza a comunicação com as APIs do Google (Sheets e Drive).
    """
    def __init__(self):
        """
        Inicializa os serviços gspread e drive usando as credenciais.
        """
        creds_dict = get_credentials_dict()
        self.creds = Credentials.from_service_account_info(creds_dict)
        self.gspread_client = gspread.authorize(self.creds)
        self.drive_service = build('drive', 'v3', credentials=self.creds)

    def open_spreadsheet(self, spreadsheet_id):
        """
        Abre uma Planilha Google pelo seu ID.
        """
        try:
            return self.gspread_client.open_by_key(spreadsheet_id)
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"ERRO: Planilha com ID '{spreadsheet_id}' não encontrada.")
            return None

    def create_spreadsheet(self, name, folder_id):
        """
        Cria uma nova Planilha Google e a move para uma pasta específica.
        Retorna o objeto da planilha criada.
        """
        file_metadata = {
            'name': name,
            'parents': [folder_id],
            'mimeType': 'application/vnd.google-apps.spreadsheet'
        }
        spreadsheet_file = self.drive_service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()
        spreadsheet_id = spreadsheet_file.get('id')
        print(f"INFO: Planilha '{name}' criada com ID: {spreadsheet_id}")
        return self.open_spreadsheet(spreadsheet_id)

    def create_folder(self, name, parent_id):
        """
        Cria uma nova pasta no Google Drive dentro de uma pasta pai.
        Retorna o ID da nova pasta.
        """
        file_metadata = {
            'name': name,
            'parents': [parent_id],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = self.drive_service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()
        folder_id = folder.get('id')
        print(f"INFO: Pasta '{name}' criada com ID: {folder_id}")
        return folder_id

    def setup_sheets_from_config(self, spreadsheet, config_path="sheets_config.yaml"):
        """
        Lê um arquivo de configuração YAML e cria as abas e cabeçalhos
        em uma planilha fornecida.
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"ERRO: Arquivo de configuração '{config_path}' não encontrado.")
            return

        sheets_config = config.get('sheets', [])
        for sheet_info in sheets_config:
            sheet_name = sheet_info.get('name')
            columns = sheet_info.get('columns', [])
            if not sheet_name or not columns:
                continue

            try:
                worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols=len(columns))
                worksheet.append_row(columns)
                print(f"INFO: Aba '{sheet_name}' criada e cabeçalhos inseridos.")
            except gspread.exceptions.APIError as e:
                if "already exists" in str(e):
                    print(f"AVISO: A aba '{sheet_name}' já existe. Pulando a criação.")
                else:
                    print(f"ERRO: Falha ao criar a aba '{sheet_name}': {e}")