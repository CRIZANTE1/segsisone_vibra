import streamlit as st
import pandas as pd
import json
import re
import logging 
from operations.sheet import SheetOperations
from AI.api_Operation import PDFQA
from fuzzywuzzy import process 

logger = logging.getLogger('segsisone_app.training_matrix_manager')

class MatrixManager:
    def __init__(self, spreadsheet_id: str):
        """
        Inicializa o gerenciador da Matriz de Treinamentos para uma unidade específica.
        
        Args:
            spreadsheet_id (str): O ID da planilha da unidade (tenant).
        """
        self.sheet_ops = SheetOperations(spreadsheet_id)
        self.columns_functions = ['id', 'nome_funcao', 'descricao']
        self.columns_matrix = ['id', 'id_funcao', 'norma_obrigatoria']
        self._initialize_sheets()
        self._functions_df = None
        self._matrix_df = None
        self.pdf_analyzer = PDFQA()

    @property
    def functions_df(self):
        """Carrega o DataFrame de funções sob demanda."""
        if self._functions_df is None:
            self._load_functions_data()
        return self._functions_df

    @property
    def matrix_df(self):
        """Carrega o DataFrame da matriz sob demanda."""
        if self._matrix_df is None:
            self._load_matrix_data()
        return self._matrix_df

    def _initialize_sheets(self):
        """
        Verifica se as abas 'funcoes' e 'matriz_treinamentos' existem na planilha da unidade.
        Nota: A criação das abas deve ser feita durante o provisionamento da unidade.
        """
        funcoes_sheet_name = "funcoes"
        matrix_sheet_name = "matriz_treinamentos"
        
        # Verifica se as abas existem carregando os dados
        funcoes_data = self.sheet_ops.carregar_dados_aba(funcoes_sheet_name)
        matrix_data = self.sheet_ops.carregar_dados_aba(matrix_sheet_name)
        
        # Loga avisos se as abas não forem encontradas
        if not funcoes_data:
            logger.warning(
                f"Aba '{funcoes_sheet_name}' não foi encontrada ou está vazia. "
                f"Certifique-se de que o template da unidade foi criado corretamente."
            )
        
        if not matrix_data:
            logger.warning(
                f"Aba '{matrix_sheet_name}' não foi encontrada ou está vazia. "
                f"Certifique-se de que o template da unidade foi criado corretamente."
            )

    def _load_functions_data(self):
        """Carrega os dados da aba 'funcoes' da planilha da unidade."""
        functions_data = self.sheet_ops.carregar_dados_aba("funcoes")
        self._functions_df = pd.DataFrame(functions_data[1:], columns=functions_data[0]) if functions_data and len(functions_data) > 1 else pd.DataFrame(columns=self.columns_functions)
        
    def _load_matrix_data(self):
        """Carrega os dados da aba 'matriz_treinamentos' da planilha da unidade."""
        matrix_data = self.sheet_ops.carregar_dados_aba("matriz_treinamentos")
        self._matrix_df = pd.DataFrame(matrix_data[1:], columns=matrix_data[0]) if matrix_data and len(matrix_data) > 1 else pd.DataFrame(columns=self.columns_matrix)

    def add_function(self, name, description):
        if not self.functions_df.empty and name.lower() in self.functions_df['nome_funcao'].str.lower().values:
            return None, f"A função '{name}' já existe."
        new_id = self.sheet_ops.adc_dados_aba("funcoes", [name, description])
        if new_id:
            self._functions_df = None # Invalida o cache para forçar recarga
            return new_id, "Função adicionada com sucesso."
        return None, "Falha ao adicionar função."

    def add_training_to_function(self, function_id, required_norm):
        if not self.matrix_df.empty and not self.matrix_df[(self.matrix_df['id_funcao'] == str(function_id)) & (self.matrix_df['norma_obrigatoria'] == required_norm)].empty:
            return None, "Este treinamento já está mapeado para esta função."
        new_id = self.sheet_ops.adc_dados_aba("matriz_treinamentos", [str(function_id), required_norm])
        if new_id:
            self._matrix_df = None # Invalida o cache
            return new_id, "Treinamento mapeado com sucesso."
        return None, "Falha ao mapear treinamento."

    def get_required_trainings_for_function(self, function_name: str) -> list:
        if self.functions_df.empty or self.matrix_df.empty:
            return []
        function = self.functions_df[self.functions_df['nome_funcao'].str.lower() == function_name.lower()]
        if function.empty:
            return []
        function_id = function.iloc[0]['id']
        required_df = self.matrix_df[self.matrix_df['id_funcao'] == function_id]
        if required_df.empty:
            return []
        return required_df['norma_obrigatoria'].dropna().tolist()

    def analyze_matrix_pdf(self, pdf_file):
        prompt = """
        **Persona:** Você é um especialista em RH e Segurança do Trabalho...
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
        
        current_functions_df = self.functions_df.copy()
        current_matrix_df = self.matrix_df.copy()
        new_functions_to_add = []
        new_mappings_to_add = []

        for item in extracted_data:
            function_name = item.get("funcao")
            if function_name and function_name.lower() not in current_functions_df['nome_funcao'].str.lower().values:
                if function_name not in [f[0] for f in new_functions_to_add]:
                    new_functions_to_add.append([function_name, "Importado via IA"])
        
        if new_functions_to_add:
            self.sheet_ops.adc_dados_aba_em_lote("funcoes", new_functions_to_add)
            self._functions_df = None

        updated_functions_df = self.functions_df.copy()
        
        for item in extracted_data:
            function_name = item.get("funcao")
            required_norms = item.get("normas_obrigatorias", [])
            if not function_name or not required_norms:
                continue
            
            function_entry = updated_functions_df[updated_functions_df['nome_funcao'].str.lower() == function_name.lower()]
            if function_entry.empty:
                continue
            function_id = function_entry.iloc[0]['id']

            for norm in required_norms:
                is_duplicate = not current_matrix_df[(current_matrix_df['id_funcao'] == str(function_id)) & (current_matrix_df['norma_obrigatoria'] == norm)].empty
                if not is_duplicate:
                    new_mappings_to_add.append([str(function_id), norm])
                    new_map_data = {'id_funcao': str(function_id), 'norma_obrigatoria': norm}
                    current_matrix_df = pd.concat([current_matrix_df, pd.DataFrame([new_map_data])], ignore_index=True)

        if new_mappings_to_add:
            self.sheet_ops.adc_dados_aba_em_lote("matriz_treinamentos", new_mappings_to_add)
            self._matrix_df = None

        return len(new_functions_to_add), len(new_mappings_to_add)

    def update_function_mappings(self, function_id, new_required_norms: list):
        try:
            function_name = self.functions_df.loc[self.functions_df['id'] == function_id, 'nome_funcao'].iloc[0]
            current_mappings = self.get_required_trainings_for_function(function_name)
    
            to_add = [norm for norm in new_required_norms if norm not in current_mappings]
            to_remove = [norm for norm in current_mappings if norm not in new_required_norms]
    
            added_count, removed_count = 0, 0
    
            for norm in to_add:
                if self.add_training_to_function(function_id, norm)[0]:
                    added_count += 1
            
            for norm in to_remove:
                mapping_to_delete = self.matrix_df[(self.matrix_df['id_funcao'] == str(function_id)) & (self.matrix_df['norma_obrigatoria'] == norm)]
                if not mapping_to_delete.empty:
                    mapping_id = mapping_to_delete.iloc[0]['id']
                    if self.sheet_ops.excluir_dados_aba("matriz_treinamentos", mapping_id):
                        removed_count += 1
    
            self._matrix_df = None
            return True, f"Mapeamentos atualizados! {added_count} adicionado(s), {removed_count} removido(s)."
            
        except Exception as e:
            return False, f"Erro ao atualizar mapeamentos: {e}"

    def find_closest_function(self, employee_cargo: str, score_cutoff: int = 90) -> str | None:
        """
        Encontra a função mais próxima na matriz de treinamentos usando fuzzy matching,
        mas apenas se a pontuação de similaridade for alta o suficiente.

        Args:
            employee_cargo (str): O cargo do funcionário a ser verificado.
            score_cutoff (int): O limiar de similaridade (0-100). Padrão é 90.

        Returns:
            str | None: O nome da função correspondente se encontrada, senão None.
        """
        if self.functions_df.empty or not employee_cargo:
            return None
            
        function_names = self.functions_df['nome_funcao'].dropna().tolist()
        if not function_names:
            return None

        best_match = process.extractOne(employee_cargo, function_names)
        

        if best_match:
            match_name, score = best_match
            logger.info(f"Fuzzy match para '{employee_cargo}': Melhor correspondência é '{match_name}' com pontuação {score}.")
            

            if score >= score_cutoff:
                logger.info(f"Pontuação {score} >= {score_cutoff}. Aceitando a correspondência.")
                return match_name
            else:
                logger.info(f"Pontuação {score} < {score_cutoff}. Rejeitando a correspondência.")
                return None
        
        return None
        
    def get_training_recommendations_for_function(self, function_name: str, nr_analyzer):
        prompt_template = """
        **Persona:** Você é um Engenheiro de Segurança do Trabalho Sênior...
        **Estrutura JSON de Saída Obrigatória:**
        ```json
        [
          {{
            "treinamento_recomendado": "NR-10 BÁSICO",
            "justificativa_normativa": "A função envolve interação com instalações elétricas, conforme NR-10."
          }}
        ]
        ```
        **Importante:** Responda APENAS com o bloco de código JSON...
        """
        try:
            query = f"Riscos, atividades e treinamentos de segurança obrigatórios para a função de {function_name}"
            relevant_knowledge = nr_analyzer._find_semantically_relevant_chunks(query, top_k=10)
            final_prompt = prompt_template.format(function_name=function_name, relevant_knowledge=relevant_knowledge)
            response_text, _ = self.pdf_analyzer.answer_question([], final_prompt, task_type='audit')
            
            if not response_text:
                return None, "A IA não retornou uma resposta."
    
            try:
                match = re.search(r'```json\s*(\[.*\])\s*```', response_text, re.DOTALL)
                json_str = match.group(1) if match else re.search(r'(\[.*\])', response_text, re.DOTALL).group(0)
                recommendations = json.loads(json_str)
                return recommendations, "Recomendações geradas com sucesso."
    
            except (json.JSONDecodeError, AttributeError):
                return None, f"A resposta da IA não era um JSON válido. Resposta: '{response_text}'"
    
        except Exception as e:
            return None, f"Ocorreu um erro ao obter recomendações: {e}"
            
