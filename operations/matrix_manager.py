import streamlit as st
import pandas as pd
import json
import re
from operations.sheet import SheetOperations
from gdrive.config import FUNCTION_SHEET_NAME, TRAINING_MATRIX_SHEET_NAME
from AI.api_Operation import PDFQA

class MatrixManager:
    def __init__(self):
        self.sheet_ops = SheetOperations()
        self.columns_functions = ['id', 'nome_funcao', 'descricao']
        self.columns_matrix = ['id', 'id_funcao', 'norma_obrigatoria']
        self._initialize_sheets()
        self.load_data()
        self.pdf_analyzer = PDFQA() 

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
        new_id = self.sheet_ops.adc_dados_aba(FUNCTION_SHEET_NAME, [name, description])
        if new_id:
            # Força o recarregamento dos dados após a adição
            self.load_data()
            return new_id, "Função adicionada com sucesso."
        return None, "Falha ao adicionar função."


    def add_training_to_function(self, function_id, required_norm):
        if not self.matrix_df.empty and not self.matrix_df[(self.matrix_df['id_funcao'] == function_id) & (self.matrix_df['norma_obrigatoria'] == required_norm)].empty:
            return None, "Este treinamento já está mapeado para esta função."
        new_id = self.sheet_ops.adc_dados_aba(TRAINING_MATRIX_SHEET_NAME, [function_id, required_norm])
        if new_id:
            # Força o recarregamento dos dados após a adição
            self.load_data()
            return new_id, "Treinamento mapeado com sucesso."
        return None, "Falha ao mapear treinamento."

    def get_required_trainings_for_function(self, function_name: str):
        if self.functions_df.empty or self.matrix_df.empty:
            return []
        
        function = self.functions_df[self.functions_df['nome_funcao'].str.lower() == function_name.lower()]
        if function.empty:
            return []
            
        function_id = function.iloc[0]['id']
        required = self.matrix_df[self.matrix_df['id_funcao'] == function_id]
        
        return required['norma_obrigatoria'].tolist()

    def process_matrix_pdf(self, pdf_file):
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
        """
        Recebe os dados já validados pelo usuário e os salva na planilha de forma otimizada.
        """
        if not extracted_data:
            return 0, 0
            
        added_functions = 0
        added_mappings = 0

        # Para evitar múltiplas leituras, trabalhamos com os DataFrames em memória
        current_functions_df = self.functions_df.copy()
        current_matrix_df = self.matrix_df.copy()

        for item in extracted_data:
            function_name = item.get("funcao")
            required_norms = item.get("normas_obrigatorias", [])
            
            if not function_name or not required_norms:
                continue

            # Verifica se a função já existe no DataFrame em memória
            existing_function = current_functions_df[current_functions_df['nome_funcao'].str.lower() == function_name.lower()]
            
            if existing_function.empty:
                # Adiciona a função na planilha
                func_id, _ = self.add_function(function_name, "Importado via IA")
                if func_id:
                    added_functions += 1
                    # Adiciona a nova função ao DataFrame em memória para futuras verificações no mesmo loop
                    new_func_data = {'id': str(func_id), 'nome_funcao': function_name, 'descricao': "Importado via IA"}
                    current_functions_df = pd.concat([current_functions_df, pd.DataFrame([new_func_data])], ignore_index=True)
                    function_id_to_use = str(func_id)
                else:
                    continue # Pula se falhou ao adicionar a função
            else:
                function_id_to_use = existing_function.iloc[0]['id']

            # Adiciona os mapeamentos
            for norm in required_norms:
                # Evita duplicatas verificando no DataFrame em memória
                is_duplicate = not current_matrix_df[(current_matrix_df['id_funcao'] == function_id_to_use) & (current_matrix_df['norma_obrigatoria'] == norm)].empty
                if not is_duplicate:
                    map_id, _ = self.add_training_to_function(function_id_to_use, norm)
                    if map_id:
                        added_mappings += 1
                        # Adiciona o novo mapeamento ao DF em memória
                        new_map_data = {'id': str(map_id), 'id_funcao': function_id_to_use, 'norma_obrigatoria': norm}
                        current_matrix_df = pd.concat([current_matrix_df, pd.DataFrame([new_map_data])], ignore_index=True)

        # Recarrega todos os dados da planilha uma única vez no final
        self.load_data()
        st.cache_resource.clear() # Limpa o cache para garantir que outras páginas vejam as mudanças
        
        return added_functions, added_mappings
         
