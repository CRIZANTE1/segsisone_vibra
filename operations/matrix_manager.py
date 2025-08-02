import streamlit as st
import pandas as pd
import json
import re
from operations.sheet import SheetOperations
from gdrive.config import FUNCTION_SHEET_NAME, TRAINING_MATRIX_SHEET_NAME
from AI.api_Operation import PDFQA
from fuzzywuzzy import process 


class MatrixManager:
    def __init__(self):
        self.sheet_ops = SheetOperations()
        self.columns_functions = ['id', 'nome_funcao', 'descricao']
        self.columns_matrix = ['id', 'id_funcao', 'norma_obrigatoria']
        self._initialize_sheets()
        #self.load_data()
        self._functions_df = None
        self._matrix_df = None
        self.pdf_analyzer = PDFQA()



    @property
    def functions_df(self):
        """Carrega o DataFrame de funções apenas quando for acessado pela primeira vez."""
        if self._functions_df is None:
            self._load_functions_data()
        return self._functions_df

    @property
    def matrix_df(self):
        """Carrega o DataFrame da matriz apenas quando for acessado pela primeira vez."""
        if self._matrix_df is None:
            self._load_matrix_data()
        return self._matrix_df

    
    def _initialize_sheets(self):
        if not self.sheet_ops.carregar_dados_aba(FUNCTION_SHEET_NAME):
            self.sheet_ops.criar_aba(FUNCTION_SHEET_NAME, self.columns_functions)
        if not self.sheet_ops.carregar_dados_aba(TRAINING_MATRIX_SHEET_NAME):
            self.sheet_ops.criar_aba(TRAINING_MATRIX_SHEET_NAME, self.columns_matrix)

    def _load_functions_data(self):
        """Função interna para carregar os dados da aba 'funcoes'."""
        functions_data = self.sheet_ops.carregar_dados_aba(FUNCTION_SHEET_NAME)
        self._functions_df = pd.DataFrame(functions_data[1:], columns=functions_data[0]) if functions_data and len(functions_data) > 1 else pd.DataFrame(columns=self.columns_functions)
        
    def _load_matrix_data(self):
        """Função interna para carregar os dados da aba 'matriz_treinamentos'."""
        matrix_data = self.sheet_ops.carregar_dados_aba(TRAINING_MATRIX_SHEET_NAME)
        self._matrix_df = pd.DataFrame(matrix_data[1:], columns=matrix_data[0]) if matrix_data and len(matrix_data) > 1 else pd.DataFrame(columns=self.columns_matrix)

    def add_function(self, name, description):
        if not self.functions_df.empty and name.lower() in self.functions_df['nome_funcao'].str.lower().values:
            return None, f"A função '{name}' já existe."
        new_id = self.sheet_ops.adc_dados_aba(FUNCTION_SHEET_NAME, [name, description])
        if new_id:
            self._functions_df = None # Invalida o cache para forçar recarga na próxima vez
            return new_id, "Função adicionada com sucesso."
        return None, "Falha ao adicionar função."

    def add_training_to_function(self, function_id, required_norm):
        if not self.matrix_df.empty and not self.matrix_df[(self.matrix_df['id_funcao'] == str(function_id)) & (self.matrix_df['norma_obrigatoria'] == required_norm)].empty:
            return None, "Este treinamento já está mapeado para esta função."
        new_id = self.sheet_ops.adc_dados_aba(TRAINING_MATRIX_SHEET_NAME, [str(function_id), required_norm])
        if new_id:
            self._matrix_df = None # Invalida o cache
            return new_id, "Treinamento mapeado com sucesso."
        return None, "Falha ao mapear treinamento."

    def get_required_trainings_for_function(self, employee_function: str, score_cutoff=90):
        """
        Encontra os treinamentos obrigatórios para uma função usando correspondência
        aproximada (fuzzy matching) para encontrar a função mais similar na matriz.
        """
        if self.functions_df.empty or self.matrix_df.empty:
            return []
        
        all_functions = self.functions_df['nome_funcao'].tolist()
        best_match = process.extractOne(employee_function, all_functions, score_cutoff=score_cutoff)        
        if not best_match:
            return []

        matched_function_name = best_match[0]        
        function_id = self.functions_df[self.functions_df['nome_funcao'] == matched_function_name].iloc[0]['id']        
        required = self.matrix_df[self.matrix_df['id_funcao'] == function_id]        
        return required['norma_obrigatoria'].tolist()

    
    def analyze_matrix_pdf(self, pdf_file):
        """
        Apenas analisa o PDF e retorna os dados extraídos pela IA.
        """
        prompt = """
        **Persona:** Você é um especialista em RH e Segurança do Trabalho, focado em organização de dados. Sua tarefa é analisar um documento de Matriz de Treinamento e extrair a relação entre Funções e os Treinamentos de Normas Regulamentadoras (NRs) obrigatórios para cada uma.

        **Sua Tarefa (em 2 etapas):**
        1.  **Extração de Dados:** Leia o documento e identifique todas as Funções (Cargos) e os treinamentos de NR associados a cada uma.
        2.  **Formatação da Resposta:** Apresente os dados extraídos em um formato JSON ESTRITO, como uma lista de objetos.

        **Estrutura JSON de Saída Obrigatória:**
        ```json
        [
          {
            "funcao": "Eletricista de Manutenção",
            "normas_obrigatorias": ["NR-10", "NR-35"]
          },
          {
            "funcao": "Soldador",
            "normas_obrigatorias": ["NR-34", "NR-33", "NR-18"]
          }
        ]
        ```
        **Importante:** Responda APENAS com o bloco de código JSON.
        """
        try:
            response_text, _ = self.pdf_analyzer.answer_question([pdf_file], prompt, task_type='extraction')
            if not response_text:
                return None, "A IA não retornou uma resposta."

            match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if not match:
                return None, "A resposta da IA não estava no formato JSON esperado."
            
            matrix_data = json.loads(match.group(0))
            return matrix_data, "Dados extraídos com sucesso."

        except (json.JSONDecodeError, Exception) as e:
            return None, f"Ocorreu um erro ao analisar o PDF: {e}"

    def save_extracted_matrix(self, extracted_data: list):
        if not extracted_data:
            return 0, 0
        
        # Garante que temos os dados mais recentes antes de começar
        current_functions_df = self.functions_df.copy()
        current_matrix_df = self.matrix_df.copy()

        new_functions_to_add = []
        new_mappings_to_add = []

        # ETAPA 1: Coleta todas as novas funções
        for item in extracted_data:
            function_name = item.get("funcao")
            if function_name and function_name.lower() not in current_functions_df['nome_funcao'].str.lower().values:
                # Evita adicionar a mesma nova função duas vezes no mesmo lote
                if function_name not in [f[0] for f in new_functions_to_add]:
                    new_functions_to_add.append([function_name, "Importado via IA"])
        
        # ETAPA 2: Adiciona as novas funções em UMA ÚNICA chamada de API
        if new_functions_to_add:
            # A função adc_dados_aba_em_lote precisa ser criada em SheetOperations
            self.sheet_ops.adc_dados_aba_em_lote(FUNCTION_SHEET_NAME, new_functions_to_add)
            self._functions_df = None # Invalida o cache

        # Recarrega o DataFrame de funções para ter os IDs das novas funções
        updated_functions_df = self.functions_df.copy()
        
        # ETAPA 3: Coleta todos os novos mapeamentos
        for item in extracted_data:
            function_name = item.get("funcao")
            required_norms = item.get("normas_obrigatorias", [])
            if not function_name or not required_norms:
                continue
            
            # Pega o ID da função do DataFrame atualizado
            function_entry = updated_functions_df[updated_functions_df['nome_funcao'].str.lower() == function_name.lower()]
            if function_entry.empty:
                continue
            function_id = function_entry.iloc[0]['id']

            for norm in required_norms:
                is_duplicate = not current_matrix_df[(current_matrix_df['id_funcao'] == str(function_id)) & (current_matrix_df['norma_obrigatoria'] == norm)].empty
                if not is_duplicate:
                    new_mappings_to_add.append([str(function_id), norm])
                    # Adiciona ao DF em memória para evitar duplicatas no mesmo lote
                    new_map_data = {'id_funcao': str(function_id), 'norma_obrigatoria': norm}
                    current_matrix_df = pd.concat([current_matrix_df, pd.DataFrame([new_map_data])], ignore_index=True)

        # ETAPA 4: Adiciona os novos mapeamentos em UMA ÚNICA chamada de API
        if new_mappings_to_add:
            self.sheet_ops.adc_dados_aba_em_lote(TRAINING_MATRIX_SHEET_NAME, new_mappings_to_add)
            self._matrix_df = None # Invalida o cache

        st.cache_resource.clear()
        return len(new_functions_to_add), len(new_mappings_to_add)
