import streamlit as st
import pandas as pd
import logging
import random
from gdrive.google_api_manager import GoogleApiManager
from gspread.exceptions import WorksheetNotFound
import gspread

# Configuração do logger para este módulo
logger = logging.getLogger('segsisone_app.sheet_operations')

class SheetOperations:
    def __init__(self, spreadsheet_id: str):
        """
        Inicializa a conexão com uma Planilha Google específica.
        Args:
            spreadsheet_id (str): O ID da planilha do tenant.
        """
        if not spreadsheet_id:
            st.error("ID da Planilha não fornecido. A aplicação não pode funcionar.")
            logger.error("SheetOperations foi inicializado sem um spreadsheet_id.")
            self.spreadsheet = None
            return

        logger.info(f"Inicializando SheetOperations para spreadsheet_id: ...{spreadsheet_id[-6:]}")
        api_manager = GoogleApiManager()
        self.spreadsheet = api_manager.open_spreadsheet(spreadsheet_id)
        if not self.spreadsheet:
            st.error(f"Erro: Não foi possível abrir ou encontrar a planilha. Verifique o ID na Planilha Matriz e as permissões.")
            logger.error(f"Falha ao abrir a planilha com ID: {spreadsheet_id}")

    def _get_worksheet(self, aba_name: str) -> gspread.Worksheet | None:
        """Helper interno para obter um objeto de worksheet de forma segura."""
        if not self.spreadsheet:
            logger.warning(f"_get_worksheet chamado para '{aba_name}' mas a planilha não foi inicializada.")
            return None
        try:
            logger.debug(f"Acessando aba '{aba_name}' na planilha '{self.spreadsheet.title}'.")
            return self.spreadsheet.worksheet(aba_name)
        except WorksheetNotFound:
            st.error(f"Erro Crítico: A aba '{aba_name}' não foi encontrada na planilha. Verifique se o template da unidade está correto.")
            logger.warning(f"A aba '{aba_name}' não foi encontrada na planilha ID {self.spreadsheet.id}.")
            return None
        except Exception as e:
            st.error(f"Erro inesperado ao acessar a aba '{aba_name}': {e}")
            logger.error(f"Erro inesperado ao acessar a aba '{aba_name}': {e}", exc_info=True)
            return None

    @st.cache_data(ttl=60)
    def carregar_dados_aba(_self, aba_name: str) -> list | None:
        """
        Carrega todos os dados de uma aba específica usando gspread.
        Adiciona logging detalhado para monitorar o processo.
        """
        logger.info(f"Iniciando carregamento de dados para a aba: '{aba_name}'.")
        worksheet = _self._get_worksheet(aba_name)
        if not worksheet:
            logger.error(f"Não foi possível carregar dados porque a aba '{aba_name}' não foi encontrada ou acessada.")
            return None 
        try:
            logger.info(f"CACHE MISS: Lendo dados da API para a aba '{aba_name}'...")
            all_values = worksheet.get_all_values()
            
            if not all_values:
                logger.warning(f"A aba '{aba_name}' foi lida com sucesso, mas está completamente vazia.")
            elif len(all_values) == 1:
                logger.info(f"A aba '{aba_name}' contém apenas um cabeçalho: {all_values[0]}")
            else:
                logger.info(f"Sucesso. {len(all_values)} linhas (incluindo cabeçalho) carregadas da aba '{aba_name}'.")
            
            return all_values
            
        except Exception as e:
            st.error(f"Erro ao ler dados da aba '{aba_name}': {e}")
            logger.error(f"FALHA CRÍTICA ao ler dados da aba '{aba_name}' com gspread: {e}", exc_info=True)
            return None
            
    def adc_dados_aba(self, aba_name: str, new_data: list) -> int | None:
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return None
        try:
            logger.info(f"Tentando adicionar dados na aba '{aba_name}'...")
            
            # Gera um ID único
            existing_ids = worksheet.col_values(1)[1:]
            while True:
                new_id = random.randint(10000, 99999)
                if str(new_id) not in existing_ids:
                    break
            
            full_row_to_add = [new_id] + new_data
            worksheet.append_row(full_row_to_add, value_input_option='USER_ENTERED')
            
            st.cache_data.clear()
            
            logger.info(f"Dados adicionados com sucesso na aba '{aba_name}'. ID gerado: {new_id}")
            return new_id
            
        except Exception as e:
            logger.error(f"Erro ao adicionar dados na aba '{aba_name}': {e}", exc_info=True)
            st.error(f"Erro ao adicionar dados na planilha: {e}")
            return None

    def update_row_by_id(self, aba_name: str, row_id: str, new_values_dict: dict) -> bool:
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return False
        try:
            header = worksheet.row_values(1)
            col_indices = {col_name: i + 1 for i, col_name in enumerate(header)}
            id_column_data = worksheet.col_values(1)
            if str(row_id) not in id_column_data:
                logger.error(f"ID {row_id} não encontrado na aba '{aba_name}'.")
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
            logger.info(f"Linha com ID {row_id} na aba '{aba_name}' atualizada com sucesso.")
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar linha na aba '{aba_name}': {e}", exc_info=True)
            return False

    def excluir_dados_aba(self, aba_name: str, row_id: str) -> bool:
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return False
        try:
            id_column_data = worksheet.col_values(1)
            if str(row_id) not in id_column_data:
                logger.error(f"ID {row_id} não encontrado para exclusão na aba '{aba_name}'.")
                return False
            row_number_to_delete = id_column_data.index(str(row_id)) + 1
            worksheet.delete_rows(row_number_to_delete)
            st.cache_data.clear()
            logger.info(f"Linha com ID {row_id} da aba '{aba_name}' excluída com sucesso.")
            return True
        except Exception as e:
            logger.error(f"Erro ao excluir dados da aba '{aba_name}': {e}", exc_info=True)
            return False
            
    def adc_dados_aba_em_lote(self, aba_name: str, new_data_list: list):
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return None
        if not new_data_list: return []
    
        try:
            logger.info(f"Tentando adicionar {len(new_data_list)} linhas em lote na aba '{aba_name}'...")
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
            
            logger.info(f"{len(rows_to_append)} linhas adicionadas com sucesso.")
            return True
    
        except Exception as e:
            logger.error(f"Erro ao adicionar dados em lote na aba '{aba_name}': {e}", exc_info=True)
            st.error(f"Erro ao adicionar dados em lote: {e}")
            return False
            
    def adc_dados_aba_sem_id(self, aba_name: str, new_data: list) -> bool:
        """
        Adiciona uma linha de dados a uma aba sem gerar um ID na primeira coluna.
        Ideal para planilhas de log.
        """
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return False
        try:
            worksheet.append_row(new_data, value_input_option='USER_ENTERED')
            logger.info(f"Linha de log adicionada com sucesso na aba '{aba_name}'.")
            return True
        except Exception as e:
            logger.error(f"Erro ao adicionar log na aba '{aba_name}': {e}", exc_info=True)
            return False
            
    def adc_linha_simples(self, aba_name: str, new_data_row: list) -> bool:
        """
        Adiciona uma única linha de dados a uma aba, sem gerar ou manipular IDs.
        Ideal para abas como 'unidades' ou 'usuarios' na Planilha Matriz.
        """
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return False
        try:
            worksheet.append_row(new_data_row, value_input_option='USER_ENTERED')
            # Não limpamos o cache aqui para evitar recargas desnecessárias
            # A função que chama este método é responsável por limpar o cache se precisar.
            logger.info(f"Linha adicionada com sucesso na aba '{aba_name}'.")
            return True
        except Exception as e:
            logger.error(f"Erro ao adicionar linha na aba '{aba_name}': {e}", exc_info=True)
            st.error(f"Erro ao adicionar dados: {e}")
            return False

  
    def excluir_linha_por_indice(self, aba_name: str, row_index: int) -> bool:
        """Exclui uma linha de uma aba pelo seu número de índice."""
        worksheet = self._get_worksheet(aba_name)
        if not worksheet: return False
        try:
            worksheet.delete_rows(row_index)
            st.cache_data.clear() # Limpa o cache de dados do Streamlit
            logger.info(f"Linha {row_index} da aba '{aba_name}' excluída com sucesso.")
            return True
        except Exception as e:
            logger.error(f"Erro ao excluir linha {row_index} da aba '{aba_name}': {e}", exc_info=True)
            return False

    def get_df_from_worksheet(self, aba_name: str) -> pd.DataFrame:
        """
        Carrega dados de uma aba e os retorna diretamente como um DataFrame do Pandas.
        Retorna um DataFrame vazio se a aba não tiver dados ou não for encontrada.
        """
        logger.info(f"Tentando obter DataFrame para a aba: '{aba_name}'.")
        data = self.carregar_dados_aba(aba_name)
        if data and len(data) > 1:
            header = data[0]
            df = pd.DataFrame(data[1:], columns=header)
            logger.info(f"DataFrame para '{aba_name}' criado com sucesso com {len(df)} linhas.")
            return df
        
        logger.warning(f"Não foi possível criar DataFrame para a aba '{aba_name}'. Retornando DataFrame vazio.")
        return pd.DataFrame()

    
