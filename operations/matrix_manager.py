import streamlit as st
import pandas as pd
from operations.sheet import SheetOperations
from gdrive.config import FUNCTION_SHEET_NAME, TRAINING_MATRIX_SHEET_NAME
from AI.api_Operation import PDFQA 

class MatrixManager:
    def __init__(self):
        self.sheet_ops = SheetOperations()
        self.pdf_analyzer = PDFQA()
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


    def process_matrix_pdf(self, pdf_file):
        prompt = """
        **Persona:** Você é um especialista em RH e Segurança do Trabalho, focado em organização de dados. Sua tarefa é analisar um documento de Matriz de Treinamento e extrair a relação entre Funções e os Treinamentos de Normas Regulamentadoras (NRs) obrigatórios para cada uma.

        **Sua Tarefa (em 2 etapas):**
        1.  **Extração de Dados:** Leia o documento (que pode ser uma tabela, lista, etc.) e identifique todas as Funções (Cargos) e os treinamentos de NR associados a cada uma. Ignore qualquer outra informação que não seja essa relação.
        2.  **Formatação da Resposta:** Apresente os dados extraídos em um formato JSON ESTRITO. A estrutura deve ser uma lista de objetos, onde cada objeto representa uma Função e contém uma lista de suas normas obrigatórias.

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
          },
          {
            "funcao": "Operador de Empilhadeira",
            "normas_obrigatorias": ["NR-11"]
          }
        ]
        ```
        **Importante:**
        *   Responda APENAS com o bloco de código JSON.
        *   Se uma função não tiver nenhuma NR associada, não a inclua na lista.
        *   Padronize os nomes das normas para o formato "NR-XX" ou "NR-XX Básico" sempre que possível.
        """
        
        try:
            # Chama a IA para análise (usando o modelo de extração, mais rápido)
            response_text, _ = self.pdf_analyzer.answer_question([pdf_file], prompt, task_type='extraction')
            
            if not response_text:
                return False, "A IA não retornou uma resposta para a matriz."

            # Extrai o JSON da resposta
            match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if not match:
                return False, "A resposta da IA não estava no formato JSON esperado."
            
            matrix_data = json.loads(match.group(0))

            # --- LÓGICA PARA POPULAR AS PLANILHAS ---
            added_functions = 0
            added_mappings = 0
            
            for item in matrix_data:
                function_name = item.get("funcao")
                required_norms = item.get("normas_obrigatorias", [])
                
                if not function_name or not required_norms:
                    continue

                # Adiciona a função se ela não existir
                if self.functions_df.empty or function_name.lower() not in self.functions_df['nome_funcao'].str.lower().values:
                    func_id, _ = self.add_function(function_name, "Importado via IA")
                    added_functions += 1
                
                # Pega o ID da função (a recém-criada ou a que já existia)
                self.load_data() # Recarrega os dados para pegar o novo ID
                function_id = self.functions_df[self.functions_df['nome_funcao'].lower() == function_name.lower()].iloc[0]['id']
                
                # Adiciona o mapeamento para cada norma
                for norm in required_norms:
                    map_id, _ = self.add_training_to_function(function_id, norm)
                    if map_id:
                        added_mappings += 1

            self.load_data() # Recarrega os dados finais
            return True, f"Matriz processada com sucesso! {added_functions} novas funções e {added_mappings} novos mapeamentos foram adicionados."

        except (json.JSONDecodeError, AttributeError, Exception) as e:
            return False, f"Ocorreu um erro ao processar a matriz: {e}" 
