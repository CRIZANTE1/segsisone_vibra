import streamlit as st
import pandas as pd
from operations.sheet import SheetOperations
from gdrive.config import FUNCTION_SHEET_NAME, TRAINING_MATRIX_SHEET_NAME

class MatrixManager:
    def __init__(self):
        self.sheet_ops = SheetOperations()
        self.columns_functions = ['id', 'nome_funcao', 'descricao']
        self.columns_matrix = ['id', 'id_funcao', 'norma_obrigatoria']
        self._initialize_sheets()
        self.load_data()

    def _initialize_sheets(self):
        if not self.sheet_ops.carregar_dados_aba(FUNCTION_SHEET_NAME):
            self.sheet_ops.criar_aba(FUNCTION_SHEET_NAME, self.columns_functions)
        if not self.sheet_ops.carregar_dados_aba(TRAINING_MATRIX_SHEET_NAME):
            self.sheet_ops.criar_aba(TRAINING_MATRIX_SHEET_NAME, self.columns_matrix)

    def load_data(self):
        functions_data = self.sheet_ops.carregar_dados_aba(FUNCTION_SHEET_NAME)
        self.functions_df = pd.DataFrame(functions_data[1:], columns=functions_data[0]) if functions_data and len(functions_data) > 1 else pd.DataFrame(columns=self.columns_functions)
        
        matrix_data = self.sheet_ops.carregar_dados_aba(TRAINING_MATRIX_SHEET_NAME)
        self.matrix_df = pd.DataFrame(matrix_data[1:], columns=matrix_data[0]) if matrix_data and len(matrix_data) > 1 else pd.DataFrame(columns=self.columns_matrix)

    def add_function(self, name, description):
        if not self.functions_df.empty and name.lower() in self.functions_df['nome_funcao'].str.lower().values:
            return None, f"A função '{name}' já existe."
        return self.sheet_ops.adc_dados_aba(FUNCTION_SHEET_NAME, [name, description]), "Função adicionada com sucesso."

    def add_training_to_function(self, function_id, required_norm):
        # Evita duplicatas
        if not self.matrix_df.empty and self.matrix_df[(self.matrix_df['id_funcao'] == function_id) & (self.matrix_df['norma_obrigatoria'] == required_norm)].shape[0] > 0:
            return None, "Este treinamento já está mapeado para esta função."
        return self.sheet_ops.adc_dados_aba(TRAINING_MATRIX_SHEET_NAME, [function_id, required_norm]), "Treinamento mapeado com sucesso."

    def get_required_trainings_for_function(self, function_name: str):
        if self.functions_df.empty or self.matrix_df.empty:
            return []
        
        function = self.functions_df[self.functions_df['nome_funcao'].str.lower() == function_name.lower()]
        if function.empty:
            return []
            
        function_id = function.iloc[0]['id']
        required = self.matrix_df[self.matrix_df['id_funcao'] == function_id]
        
        return required['norma_obrigatoria'].tolist()
