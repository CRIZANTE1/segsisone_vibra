import streamlit as st
import pandas as pd
import logging
import random
from gdrive.google_api_manager import GoogleApiManager # Import the new manager
from gspread.exceptions import WorksheetNotFound
import gspread

class SheetOperations:
    def __init__(self, spreadsheet_id: str):
        """
        Inicializa a conexão com uma Planilha Google específica.
        Args:
            spreadsheet_id (str): O ID da planilha do tenant.
        """
        if not spreadsheet_id:
            st.error("ID da Planilha não fornecido. A aplicação não pode funcionar.")
            self.spreadsheet = None
            return

        api_manager = GoogleApiManager()
        self.spreadsheet = api_manager.open_spreadsheet(spreadsheet_id)
        if not self.spreadsheet:
            st.error(f"Erro: Não foi possível abrir ou encontrar a planilha com o ID '{spreadsheet_id}'. Verifique o ID e as permissões de acesso.")

    def _get_worksheet(self, aba_name: str) -> gspread.Worksheet | None:
        """Helper interno para obter um objeto de worksheet de forma segura."""
        if not self.spreadsheet:
            st.error("Conexão com a planilha não estabelecida.")
            return None
        try:
            return self.spreadsheet.worksheet(aba_name)
        except WorksheetNotFound:
            logging.warning(f"A aba '{aba_name}' não foi encontrada na planilha.")
            st.error(f"Erro: A aba '{aba_name}' não foi encontrada na planilha. Verifique o nome da aba.")
            return None
        except Exception as e:
            logging.error(f"Erro inesperado ao acessar a aba '{aba_name}': {e}")
            st.error(f"Erro ao acessar a aba '{aba_name}'.")
            return None

    @st.cache_data(ttl=60)
    def carregar_dados_aba(_self, aba_name: str) -> list | None:
        """
        Carrega todos os dados de uma aba específica usando gspread.
        """
        worksheet = _self._get_worksheet(aba_name)
        if not worksheet:
            return None
        try:
            logging.info(f"CACHE MISS: Lendo dados da API para a aba '{aba_name}'...")
            return worksheet.get_all_values()
        except Exception as e:
            logging.error(f"Erro ao ler dados da aba '{aba_name}' com gspread: {e}")
            st.error(f"Erro: Não foi possível ler os dados da aba '{aba_name}'. Detalhes: {e}")
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
            st.cache_data.clear()
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
                st.cache_data.clear()
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
            st.cache_data.clear()
            logging.info(f"Linha com ID {row_id} da aba '{aba_name}' excluída com sucesso.")
            return True
        except Exception as e:
            logging.error(f"Erro ao excluir dados da aba '{aba_name}': {e}", exc_info=True)
            return False
            
    def adc_dados_aba_em_lote(self, aba_name: str, new_data_list: list):
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return None
        if not new_data_list: return []
    
        try:
            logging.info(f"Tentando adicionar {len(new_data_list)} linhas em lote na aba '{aba_name}'...")
            rows_to_append = []
            existing_ids = worksheet.col_values(1)[1:]
            
            for row_data in new_data_list:
                while True:
                    new_id = random.randint(10000, 99999)
                    if str(new_id) not in existing_ids:
                        existing_ids.append(str(new_id))
                        break
                rows_to_append.append([new_id] + row_data)
            
            worksheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')
            
            logging.info(f"{len(rows_to_append)} linhas adicionadas com sucesso.")
            return True
    
        except Exception as e:
            logging.error(f"Erro ao adicionar dados em lote na aba '{aba_name}': {e}", exc_info=True)
            st.error(f"Erro ao adicionar dados em lote: {e}")
            return False