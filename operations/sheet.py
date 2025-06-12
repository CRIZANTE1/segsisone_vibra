import streamlit as st
import pandas as pd
import logging
import random
from gdrive.connection import connect_sheet
from gdrive.config import EMPLOYEE_DATA_SHEET_NAME
from datetime import datetime


class SheetOperations:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SheetOperations, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """
        Inicializa a conexão com o Google Sheets.
        """
        if not self._initialized:
            self.credentials, self.my_archive_google_sheets = connect_sheet()
            if not self.credentials or not self.my_archive_google_sheets:
                logging.error("Credenciais ou URL do Google Sheets inválidos.")
            self._initialized = True
            self._cache = {}
            self._cache_timestamp = {}
            self._cache_ttl = 30  # Tempo de vida do cache em segundos

    def _is_cache_valid(self, key):
        """
        Verifica se o cache para uma chave específica ainda é válido.
        """
        if key not in self._cache_timestamp:
            return False
        return (datetime.now() - self._cache_timestamp[key]).total_seconds() < self._cache_ttl

    def carregar_dados_aba(self, aba_name):
        """
        Carrega os dados de uma aba específica do Google Sheets.
        
        Args:
            aba_name (str): Nome da aba para carregar os dados
            
        Returns:
            list: Lista com os dados da aba, onde o primeiro item são os cabeçalhos
                 e os demais são os dados de cada linha.
        """
        if not self.credentials or not self.my_archive_google_sheets:
            return None

        # Verifica se os dados estão em cache e são válidos
        if aba_name in self._cache and self._is_cache_valid(aba_name):
            return self._cache[aba_name]

        try:
            logging.info(f"Tentando ler dados da aba '{aba_name}'...")
            
            archive = self.credentials.open_by_url(self.my_archive_google_sheets)
            
            if aba_name not in [sheet.title for sheet in archive.worksheets()]:
                logging.error(f"A aba '{aba_name}' não existe no Google Sheets.")
                st.error(f"A aba '{aba_name}' não foi encontrada na planilha.")
                return None
            
            aba = archive.worksheet_by_title(aba_name)
            data = aba.get_all_values()
            
            # Atualiza o cache
            self._cache[aba_name] = data
            self._cache_timestamp[aba_name] = datetime.now()
            
            logging.info(f"Dados da aba '{aba_name}' lidos com sucesso.")
            return data
        
        except Exception as e:
            logging.error(f"Erro ao ler dados da aba '{aba_name}': {e}")
            st.error(f"Erro ao ler dados da aba '{aba_name}': {e}")
            return None
            
    def adc_dados_aba(self, aba_name, new_data):
        """
        Adiciona dados em uma aba específica do Google Sheets.
        
        Args:
            aba_name (str): Nome da aba onde os dados serão adicionados
            new_data (list): Lista com os dados a serem adicionados
            
        Returns:
            int: ID gerado para o novo registro ou None em caso de erro
        """
        if not self.credentials or not self.my_archive_google_sheets:
            return None
        try:
            logging.info(f"Tentando adicionar dados na aba '{aba_name}': {new_data}")
            archive = self.credentials.open_by_url(self.my_archive_google_sheets)
            
            if aba_name not in [sheet.title for sheet in archive.worksheets()]:
                logging.error(f"A aba '{aba_name}' não existe no Google Sheets.")
                st.error(f"A aba '{aba_name}' não foi encontrada na planilha.")
                return None
                
            aba = archive.worksheet_by_title(aba_name)
            
            # Gera um ID único para os novos dados
            existing_ids = [row[0] for row in aba.get_all_values()[1:]]
            while True:
                new_id = random.randint(1000, 9999)
                if str(new_id) not in existing_ids:
                    break
            
            # Insere o ID no início da lista de dados
            new_data.insert(0, new_id)
            
            # Adiciona os dados na planilha
            aba.append_table(values=[new_data])
            
            logging.info(f"Dados adicionados com sucesso na aba '{aba_name}'.")
            return new_id
            
        except Exception as e:
            logging.error(f"Erro ao adicionar dados na aba '{aba_name}': {e}", exc_info=True)
            st.error(f"Erro ao adicionar dados: {e}")
            return None

    def editar_dados_aba(self, aba_name, id, updated_data):
        """
        Edita dados em uma aba específica do Google Sheets.
        
        Args:
            aba_name (str): Nome da aba onde os dados serão editados
            id (str): ID do registro a ser editado
            updated_data (list): Lista com os novos dados
            
        Returns:
            bool: True se a edição foi bem sucedida, False caso contrário
        """
        if not self.credentials or not self.my_archive_google_sheets:
            return False
        try:
            logging.info(f"Tentando editar dados do ID {id} na aba '{aba_name}'")
            archive = self.credentials.open_by_url(self.my_archive_google_sheets)
            
            if aba_name not in [sheet.title for sheet in archive.worksheets()]:
                logging.error(f"A aba '{aba_name}' não existe no Google Sheets.")
                st.error(f"A aba '{aba_name}' não foi encontrada na planilha.")
                return False
                
            aba = archive.worksheet_by_title(aba_name)
            data = aba.get_all_values()
            
            # Procurar a linha com o ID correspondente
            for i, row in enumerate(data):
                if row[0] == str(id):  # ID está na primeira coluna
                    # Atualizar a linha com os novos dados, mantendo o ID original
                    updated_row = [str(id)] + updated_data
                    aba.update_row(i + 1, updated_row)  # +1 porque as linhas começam em 1
                    logging.info(f"Dados editados com sucesso na aba '{aba_name}'.")
                    return True
                    
            logging.error(f"ID {id} não encontrado na aba '{aba_name}'.")
            return False
            
        except Exception as e:
            logging.error(f"Erro ao editar dados na aba '{aba_name}': {e}", exc_info=True)
            return False

    def excluir_dados_aba(self, aba_name, id):
        """
        Exclui dados em uma aba específica do Google Sheets.
        
        Args:
            aba_name (str): Nome da aba onde os dados serão excluídos
            id (str): ID do registro a ser excluído
            
        Returns:
            bool: True se a exclusão foi bem sucedida, False caso contrário
        """
        if not self.credentials or not self.my_archive_google_sheets:
            return False
        try:
            logging.info(f"Tentando excluir dados do ID {id} na aba '{aba_name}'")
            archive = self.credentials.open_by_url(self.my_archive_google_sheets)
            
            if aba_name not in [sheet.title for sheet in archive.worksheets()]:
                logging.error(f"A aba '{aba_name}' não existe no Google Sheets.")
                st.error(f"A aba '{aba_name}' não foi encontrada na planilha.")
                return False
                
            aba = archive.worksheet_by_title(aba_name)
            data = aba.get_all_values()
            
            # Procurar a linha com o ID correspondente
            for i, row in enumerate(data):
                if row[0] == str(id):  # ID está na primeira coluna
                    aba.delete_rows(i + 1)  # +1 porque as linhas começam em 1
                    logging.info(f"Dados excluídos com sucesso na aba '{aba_name}'.")
                    return True
                    
            logging.error(f"ID {id} não encontrado na aba '{aba_name}'.")
            return False
            
        except Exception as e:
            logging.error(f"Erro ao excluir dados na aba '{aba_name}': {e}", exc_info=True)
            return False

    def carregar_dados(self):
        return self.carregar_dados_aba('control_stock')
    
    def carregar_dados_funcionarios(self):
        """
        Carrega os dados dos funcionários da aba definida em EMPLOYEE_DATA_SHEET_NAME do Google Sheets.
        
        Returns:
            list: Lista com os dados dos funcionários, onde o primeiro item são os cabeçalhos
                 e os demais são os dados de cada funcionário.
        """
        return self.carregar_dados_aba(EMPLOYEE_DATA_SHEET_NAME)

    def adc_dados(self, new_data):
        if not self.credentials or not self.my_archive_google_sheets:
            return
        try:
            logging.info(f"Tentando adicionar dados: {new_data}")
            archive = self.credentials.open_by_url(self.my_archive_google_sheets)
            aba_name = 'control_stock'
            if aba_name not in [sheet.title for sheet in archive.worksheets()]:
                logging.error(f"A aba '{aba_name}' não existe no Google Sheets.")
                st.error(f"A aba '{aba_name}' não foi encontrada na planilha.")
                return
            aba = archive.worksheet_by_title(aba_name)

            # Esta parte do código está gerando um novo ID único para os dados a serem adicionados ao
            # Google Sheets. O ID é um número aleatório de 4 dígitos que não pode ser repetido.
            existing_ids = [row[0] for row in aba.get_all_values()[1:]]  #
            while True:
                new_id = random.randint(1000, 9999)
                if str(new_id) not in existing_ids:
                    break

            new_data.insert(0, new_id)  # Insere o novo ID no início da lista new_data
            aba.append_table(values=new_data)  # Adiciona a linha à tabela dinamicamente
            logging.info("Dados adicionados com sucesso.")
            st.success("Dados adicionados com sucesso!")
        except Exception as e:
            logging.error(f"Erro ao adicionar dados: {e}", exc_info=True)
            st.error(f"Erro ao adicionar dados: {e}")

    def editar_dados(self, id, updated_data):
        if not self.credentials or not self.my_archive_google_sheets:
            return False
        try:
            logging.info(f"Tentando editar dados do ID {id}")
            archive = self.credentials.open_by_url(self.my_archive_google_sheets)
            aba = archive.worksheet_by_title('control_stock')
            data = aba.get_all_values()
            
            # Procurar a linha com o ID correspondente
            for i, row in enumerate(data):
                if row[0] == str(id):  # ID está na primeira coluna
                    # Atualizar a linha com os novos dados, mantendo o ID original
                    updated_row = [str(id)] + updated_data
                    aba.update_row(i + 1, updated_row)  # +1 porque as linhas começam em 1
                    logging.info("Dados editados com sucesso.")
                    return True
                    
            logging.error(f"ID {id} não encontrado.")
            return False
            
        except Exception as e:
            logging.error(f"Erro ao editar dados: {e}", exc_info=True)
            return False

    def excluir_dados(self, id):
        if not self.credentials or not self.my_archive_google_sheets:
            return False
        try:
            logging.info(f"Tentando excluir dados do ID {id}")
            archive = self.credentials.open_by_url(self.my_archive_google_sheets)
            aba = archive.worksheet_by_title('control_stock')
            data = aba.get_all_values()
            
            # Procurar a linha com o ID correspondente
            for i, row in enumerate(data):
                if row[0] == str(id):  # ID está na primeira coluna
                    aba.delete_rows(i + 1)  # +1 porque as linhas começam em 1
                    logging.info("Dados excluídos com sucesso.")
                    return True
                    
            logging.error(f"ID {id} não encontrado.")
            return False
            
        except Exception as e:
            logging.error(f"Erro ao excluir dados: {e}", exc_info=True)
            return False
        
# Em implemação -----------------------------------------------------------------------------
    def add_user(self, user_data):
        
        """
        O código Python fornecido define métodos para adicionar e remover usuários de um documento Google Sheets,
        tratando erros e mensagens de log de acordo.

        :param user_data: O parâmetro `user_data` provavelmente contém informações sobre um usuário que você deseja
        adicionar a um documento Google Sheets. Essas informações podem incluir detalhes como o nome do usuário,
        e-mail, função ou quaisquer outros dados relevantes que você deseja armazenar na planilha 'users' dentro do
        Google Sheets especificado.
        :return: Tanto nos métodos `add_user` quanto `remove_user`, se as condições `if not
        self.credentials or not self.my_archive_google_sheets` forem atendidas, os métodos retornarão
        sem executar nenhuma ação adicional.
        """
        if not self.credentials or not self.my_archive_google_sheets:
            return
        try:
            logging.info(f"Tentando adicionar usuário: {user_data}")
            archive = self.credentials.open_by_url(self.my_archive_google_sheets)
            aba_name = 'users'
            if aba_name not in [sheet.title for sheet in archive.worksheets()]:
                logging.error(f"A aba '{aba_name}' não existe no Google Sheets.")
                st.error(f"A aba '{aba_name}' não foi encontrada na planilha.")
                return
            aba = archive.worksheet_by_title(aba_name)
            aba.append_table(values=[user_data])
            logging.info("Usuário adicionado com sucesso.")
            st.success("Usuário adicionado com sucesso!")
        except Exception as e:
            logging.error(f"Erro ao adicionar usuário: {e}", exc_info=True)
            st.error(f"Erro ao adicionar usuário: {e}")

    def remove_user(self, user_name):
        if not self.credentials or not self.my_archive_google_sheets:
            return
        try:
            logging.info(f"Tentando remover usuário: {user_name}")
            archive = self.credentials.open_by_url(self.my_archive_google_sheets)
            aba_name = 'users'
            if aba_name not in [sheet.title for sheet in archive.worksheets()]:
                logging.error(f"A aba '{aba_name}' não existe no Google Sheets.")
                st.error(f"A aba '{aba_name}' não foi encontrada na planilha.")
                return
            aba = archive.worksheet_by_title(aba_name)
            data = aba.get_all_values()
            
            # Find the row to delete
            for i, row in enumerate(data):
                if user_name in row:  # Assuming username is a unique identifier
                    aba.delete_rows(i+1)  # i+1 because sheet indices start at 1
                    logging.info("Usuário removido com sucesso.")
                    st.success("Usuário removido com sucesso!")
                    return
            st.error("Usuário não encontrado na aba 'users'.")
        except Exception as e:
            logging.error(f"Erro ao remover usuário: {e}", exc_info=True)
            st.error(f"Erro ao remover usuário: {e}")
            
    def criar_aba(self, aba_name, columns):
        """
        Cria uma nova aba na planilha com as colunas especificadas.
        
        Args:
            aba_name (str): Nome da aba a ser criada
            columns (list): Lista com os nomes das colunas
            
        Returns:
            bool: True se a aba foi criada com sucesso, False caso contrário
        """
        if not self.credentials or not self.my_archive_google_sheets:
            return False
        try:
            logging.info(f"Tentando criar aba '{aba_name}' com colunas: {columns}")
            archive = self.credentials.open_by_url(self.my_archive_google_sheets)
            
            # Verifica se a aba já existe
            if aba_name in [sheet.title for sheet in archive.worksheets()]:
                logging.warning(f"A aba '{aba_name}' já existe.")
                return True
            
            # Cria a nova aba
            aba = archive.add_worksheet(aba_name, rows=1, cols=len(columns))
            
            # Adiciona os cabeçalhos
            aba.update_row(1, columns)
            
            logging.info(f"Aba '{aba_name}' criada com sucesso.")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao criar aba '{aba_name}': {e}", exc_info=True)
            st.error(f"Erro ao criar aba: {e}")
            return False
            
    def limpar_e_recriar_aba(self, aba_name, columns):
        """
        Limpa e recria uma aba com as colunas corretas.
        
        Args:
            aba_name (str): Nome da aba a ser recriada
            columns (list): Lista com os nomes das colunas
            
        Returns:
            bool: True se a aba foi recriada com sucesso, False caso contrário
        """
        if not self.credentials or not self.my_archive_google_sheets:
            return False
        try:
            logging.info(f"Tentando recriar aba '{aba_name}' com colunas: {columns}")
            archive = self.credentials.open_by_url(self.my_archive_google_sheets)
            
            # Remove a aba existente se ela existir
            if aba_name in [sheet.title for sheet in archive.worksheets()]:
                aba_antiga = archive.worksheet_by_title(aba_name)
                archive.del_worksheet(aba_antiga)
            
            # Cria a nova aba
            aba = archive.add_worksheet(aba_name, rows=1, cols=len(columns))
            
            # Adiciona os cabeçalhos
            aba.update_row(1, columns)
            
            logging.info(f"Aba '{aba_name}' recriada com sucesso.")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao recriar aba '{aba_name}': {e}", exc_info=True)
            st.error(f"Erro ao recriar aba: {e}")
            return False
            


            

