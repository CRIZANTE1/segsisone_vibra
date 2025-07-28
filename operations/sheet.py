import streamlit as st
import pandas as pd
import logging
import random
from gdrive.connection import connect_sheet
from gspread.exceptions import WorksheetNotFound
import gspread

class SheetOperations:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SheetOperations, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """
        Inicializa a conexão com o Google Sheets usando a biblioteca gspread.
        """
        if not self._initialized:
            self.gspread_client, self.sheet_url = connect_sheet()
            if self.gspread_client and self.sheet_url:
                try:
                    self.spreadsheet = self.gspread_client.open_by_url(self.sheet_url)
                except Exception as e:
                    self.spreadsheet = None
                    logging.error(f"Falha ao abrir a planilha pela URL: {e}")
            else:
                self.spreadsheet = None
                logging.error("Falha ao inicializar. Cliente gspread ou URL da planilha inválidos.")
            self._initialized = True

    def _get_worksheet(self, aba_name: str) -> gspread.Worksheet | None:
        """Helper interno para obter um objeto de worksheet de forma segura."""
        if not self.spreadsheet:
            st.error("Conexão com a planilha não estabelecida.")
            return None
        try:
            return self.spreadsheet.worksheet(aba_name)
        except WorksheetNotFound:
            logging.warning(f"A aba '{aba_name}' não foi encontrada na planilha.")
            return None
        except Exception as e:
            logging.error(f"Erro inesperado ao acessar a aba '{aba_name}': {e}")
            st.error(f"Erro ao acessar a aba '{aba_name}'.")
            return None


    def carregar_dados_aba(self, aba_name: str) -> list | None:
        worksheet = self._get_worksheet(aba_name)
        if not worksheet:
            return None
        try:
            logging.info(f"Tentando ler dados da aba '{aba_name}' com gspread...")
            return worksheet.get_all_values()
        except Exception as e:
            logging.error(f"Erro ao ler dados da aba '{aba_name}' com gspread: {e}")
            st.error(f"Erro ao ler dados da aba '{aba_name}': {e}")
            return None
            
    def adc_dados_aba(self, aba_name: str, new_data: list) -> int | None:
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return None
        try:
            logging.info(f"Tentando adicionar dados na aba '{aba_name}' com gspread...")
            existing_ids = worksheet.col_values(1)[1:]
            while True:
                new_id = random.randint(10000, 99999)
                if str(new_id) not in existing_ids:
                    break
            full_row_to_add = [new_id] + new_data
            worksheet.append_row(full_row_to_add, value_input_option='USER_ENTERED')
            logging.info(f"Dados adicionados com sucesso na aba '{aba_name}'. ID gerado: {new_id}")
            return new_id
        except Exception as e:
            logging.error(f"Erro ao adicionar dados na aba '{aba_name}': {e}", exc_info=True)
            st.error(f"Erro ao adicionar dados: {e}")
            return None

    def update_row_by_id(self, aba_name: str, row_id: str, new_values_dict: dict) -> bool:
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return False
        try:
            header = worksheet.row_values(1)
            col_indices = {col_name: i + 1 for i, col_name in enumerate(header)}
            id_column_data = worksheet.col_values(1)
            if str(row_id) not in id_column_data:
                logging.error(f"ID {row_id} não encontrado na aba '{aba_name}'.")
                return False
            row_number_to_update = id_column_data.index(str(row_id)) + 1
            cell_updates = []
            for col_name, new_value in new_values_dict.items():
                if col_name in col_indices:
                    col_index = col_indices[col_name]
                    cell_updates.append(gspread.Cell(row_number_to_update, col_index, str(new_value)))
            if cell_updates:
                worksheet.update_cells(cell_updates, value_input_option='USER_ENTERED')
            logging.info(f"Linha com ID {row_id} na aba '{aba_name}' atualizada com sucesso.")
            return True
        except Exception as e:
            logging.error(f"Erro ao atualizar linha na aba '{aba_name}': {e}", exc_info=True)
            return False

    def excluir_dados_aba(self, aba_name: str, row_id: str) -> bool:
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return False
        try:
            id_column_data = worksheet.col_values(1)
            if str(row_id) not in id_column_data:
                logging.error(f"ID {row_id} não encontrado para exclusão na aba '{aba_name}'.")
                return False
            row_number_to_delete = id_column_data.index(str(row_id)) + 1
            worksheet.delete_rows(row_number_to_delete)
            logging.info(f"Linha com ID {row_id} da aba '{aba_name}' excluída com sucesso.")
            return True
        except Exception as e:
            logging.error(f"Erro ao excluir dados da aba '{aba_name}': {e}", exc_info=True)
            return False

    def criar_aba(self, aba_name: str, columns: list) -> bool:
        if not self.spreadsheet: return False
        try:
            logging.info(f"Tentando criar aba '{aba_name}' com gspread...")
            worksheet = self.spreadsheet.add_worksheet(title=aba_name, rows="1", cols=str(len(columns)))
            worksheet.update('A1', [columns])
            logging.info(f"Aba '{aba_name}' criada com sucesso.")
            return True
        except gspread.exceptions.APIError as e:
            if 'already exists' in str(e):
                logging.warning(f"A aba '{aba_name}' já existe.")
                return True
            logging.error(f"Erro de API ao criar aba '{aba_name}': {e}", exc_info=True)
            return False
        except Exception as e:
            logging.error(f"Erro inesperado ao criar aba '{aba_name}': {e}", exc_info=True)
            return False

    def add_user(self, user_data: list):
        """Adiciona um usuário à aba 'users'."""
        worksheet = self._get_worksheet('users')
        if not worksheet:
            st.error("A aba 'users' não foi encontrada para adicionar o usuário.")
            return
        try:
            logging.info(f"Tentando adicionar usuário: {user_data}")
            worksheet.append_row(user_data, value_input_option='USER_ENTERED')
            logging.info("Usuário adicionado com sucesso.")
            st.success("Usuário adicionado com sucesso!")
        except Exception as e:
            logging.error(f"Erro ao adicionar usuário: {e}", exc_info=True)
            st.error(f"Erro ao adicionar usuário: {e}")

    def remove_user(self, user_name: str):
        """Remove um usuário da aba 'users' pelo nome."""
        worksheet = self._get_worksheet('users')
        if not worksheet:
            st.error("A aba 'users' não foi encontrada para remover o usuário.")
            return
        try:
            logging.info(f"Tentando remover usuário: {user_name}")
            cell = worksheet.find(user_name)
            if cell:
                worksheet.delete_rows(cell.row)
                logging.info("Usuário removido com sucesso.")
                st.success("Usuário removido com sucesso!")
            else:
                st.error("Usuário não encontrado na aba 'users'.")
        except Exception as e:
            logging.error(f"Erro ao remover usuário: {e}", exc_info=True)
            st.error(f"Erro ao remover usuário: {e}")

    def carregar_dados(self):
        """Wrapper para carregar dados da aba 'control_stock'."""
        return self.carregar_dados_aba('control_stock')

    def adc_dados(self, new_data: list):
        """Wrapper para adicionar dados à aba 'control_stock'."""
        return self.adc_dados_aba('control_stock', new_data)
        
    def editar_dados(self, row_id: str, updated_data: dict):
        """Wrapper para editar dados na aba 'control_stock'."""
        return self.update_row_by_id('control_stock', row_id, updated_data)

    def excluir_dados(self, row_id: str):
        """Wrapper para excluir dados da aba 'control_stock'."""
        return self.excluir_dados_aba('control_stock', row_id)
            

            

