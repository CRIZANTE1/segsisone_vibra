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
        """
        Helper interno para obter um objeto de worksheet de forma segura.
        """
        if not self.spreadsheet:
            st.error("Conexão com a planilha não estabelecida.")
            return None
        try:
            return self.spreadsheet.worksheet(aba_name)
        except WorksheetNotFound:
            logging.warning(f"A aba '{aba_name}' não foi encontrada na planilha. Ela pode ser criada se necessário.")
            return None
        except Exception as e:
            logging.error(f"Erro inesperado ao acessar a aba '{aba_name}': {e}")
            st.error(f"Erro ao acessar a aba '{aba_name}'.")
            return None

    def carregar_dados_aba(self, aba_name: str) -> list | None:
        """
        Carrega todos os dados de uma aba específica usando gspread.
        """
        worksheet = self._get_worksheet(aba_name)
        if not worksheet:
            return None # Retorna None se a aba não existe
        try:
            logging.info(f"Tentando ler dados da aba '{aba_name}' com gspread...")
            return worksheet.get_all_values()
        except Exception as e:
            logging.error(f"Erro ao ler dados da aba '{aba_name}' com gspread: {e}")
            st.error(f"Erro ao ler dados da aba '{aba_name}': {e}")
            return None
            
    def adc_dados_aba(self, aba_name: str, new_data: list) -> int | None:
        """
        Adiciona uma nova linha de dados a uma aba específica usando gspread.
        """
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return None
        try:
            logging.info(f"Tentando adicionar dados na aba '{aba_name}' com gspread...")
            
            # Gera um ID único para os novos dados
            existing_ids = worksheet.col_values(1)[1:] # Pega todos os IDs da coluna 1, exceto o cabeçalho
            while True:
                new_id = random.randint(10000, 99999) # Aumentado para 5 dígitos para menos colisões
                if str(new_id) not in existing_ids:
                    break
            
            full_row_to_add = [new_id] + new_data
            
            # Adiciona os dados na planilha
            worksheet.append_row(full_row_to_add, value_input_option='USER_ENTERED')
            
            logging.info(f"Dados adicionados com sucesso na aba '{aba_name}'. ID gerado: {new_id}")
            return new_id
        except Exception as e:
            logging.error(f"Erro ao adicionar dados na aba '{aba_name}': {e}", exc_info=True)
            st.error(f"Erro ao adicionar dados: {e}")
            return None

    def update_row_by_id(self, aba_name: str, row_id: str, new_values_dict: dict) -> bool:
        """
        Atualiza células específicas de uma linha baseada em seu ID usando gspread.
        """
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
                else:
                    logging.warning(f"Coluna '{col_name}' não encontrada no cabeçalho da aba '{aba_name}'.")
    
            if cell_updates:
                worksheet.update_cells(cell_updates, value_input_option='USER_ENTERED')
    
            logging.info(f"Linha com ID {row_id} na aba '{aba_name}' atualizada com sucesso.")
            return True
        except Exception as e:
            logging.error(f"Erro ao atualizar linha na aba '{aba_name}': {e}", exc_info=True)
            return False

    def excluir_dados_aba(self, aba_name: str, row_id: str) -> bool:
        """
        Exclui uma linha de uma aba específica baseada em seu ID.
        """
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
        """
        Cria uma nova aba na planilha com as colunas especificadas.
        """
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
            else:
                logging.error(f"Erro de API ao criar aba '{aba_name}': {e}", exc_info=True)
                st.error(f"Erro de API ao criar aba: {e}")
                return False
        except Exception as e:
            logging.error(f"Erro inesperado ao criar aba '{aba_name}': {e}", exc_info=True)
            st.error(f"Erro ao criar aba: {e}")
            return False

            

            

