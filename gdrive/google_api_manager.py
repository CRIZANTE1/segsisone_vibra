import gspread
import yaml
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from .config import get_credentials_dict

class GoogleApiManager:
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

    def __init__(self):
        creds_dict = get_credentials_dict()
        self.creds = Credentials.from_service_account_info(creds_dict, scopes=self.SCOPES)
        self.gspread_client = gspread.authorize(self.creds)
        self.drive_service = build('drive', 'v3', credentials=self.creds)

    def open_spreadsheet(self, spreadsheet_id):
        try:
            return self.gspread_client.open_by_key(spreadsheet_id)
        except gspread.exceptions.SpreadsheetNotFound:
            return None

    def create_spreadsheet(self, name, folder_id):
        file_metadata = {'name': name, 'parents': [folder_id], 'mimeType': 'application/vnd.google-apps.spreadsheet'}
        spreadsheet_file = self.drive_service.files().create(body=file_metadata, fields='id').execute()
        return self.open_spreadsheet(spreadsheet_file.get('id'))

    def create_folder(self, name, parent_id):
        file_metadata = {'name': name, 'parents': [parent_id], 'mimeType': 'application/vnd.google-apps.folder'}
        folder = self.drive_service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

    def setup_sheets_from_config(self, spreadsheet, config_path="sheets_config.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            sheets_config = yaml.safe_load(f)
        
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
