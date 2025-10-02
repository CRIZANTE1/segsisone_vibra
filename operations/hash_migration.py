import streamlit as st
import pandas as pd
import logging
from operations.sheet import SheetOperations
from operations.file_hash import calcular_hash_arquivo
from gdrive.google_api_manager import GoogleApiManager
import gspread

logger = logging.getLogger('segsisone_app.hash_migration')

class HashMigration:
    def __init__(self, spreadsheet_id: str):
        self.sheet_ops = SheetOperations(spreadsheet_id)
        self.api_manager = GoogleApiManager()
        self.spreadsheet_id = spreadsheet_id
    
    def verificar_necessidade_migracao(self, aba_name: str) -> bool:
        """
        Verifica se a aba precisa de migração (se tem a coluna arquivo_hash).
        """
        try:
            worksheet = self.sheet_ops._get_worksheet(aba_name)
            if not worksheet:
                return False
            
            headers = worksheet.row_values(1)
            return 'arquivo_hash' not in headers
            
        except Exception as e:
            logger.error(f"Erro ao verificar necessidade de migração em '{aba_name}': {e}")
            return False
    
    def adicionar_coluna_hash(self, aba_name: str, posicao_coluna: int):
        """
        Adiciona a coluna 'arquivo_hash' na posição especificada.
        """
        try:
            worksheet = self.sheet_ops._get_worksheet(aba_name)
            if not worksheet:
                return False
            
            headers = worksheet.row_values(1)
            
            # Verifica se já existe
            if 'arquivo_hash' in headers:
                logger.info(f"Coluna 'arquivo_hash' já existe em '{aba_name}'.")
                return True
            
            # Insere a coluna
            worksheet.insert_cols([[]], col=posicao_coluna)
            
            # Define o cabeçalho
            worksheet.update_cell(1, posicao_coluna, 'arquivo_hash')
            
            logger.info(f"Coluna 'arquivo_hash' adicionada com sucesso em '{aba_name}'.")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao adicionar coluna em '{aba_name}': {e}")
            return False
    
    def executar_migracao_completa(self):
        """
        Executa a migração completa para todas as abas necessárias.
        """
        migracoes = {
            'asos': 6,  # Após 'arquivo_id' (coluna 5)
            'treinamentos': 9,  # Após 'anexo' (coluna 8)
            'documentos_empresa': 7,  # Após 'arquivo_id' (coluna 6)
            'fichas_epi': 8  # Após 'arquivo_id' (coluna 7)
        }
        
        resultados = {}
        
        for aba_name, posicao in migracoes.items():
            logger.info(f"Verificando migração para '{aba_name}'...")
            
            if self.verificar_necessidade_migracao(aba_name):
                logger.info(f"Migrando '{aba_name}'...")
                sucesso = self.adicionar_coluna_hash(aba_name, posicao)
                resultados[aba_name] = "✅ Migrado" if sucesso else "❌ Erro"
            else:
                resultados[aba_name] = "✅ Já atualizado"
                logger.info(f