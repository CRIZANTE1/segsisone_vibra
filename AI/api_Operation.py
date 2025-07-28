import streamlit as st
import time
from AI.api_load import load_models  

class PDFQA:
    def __init__(self):
        """
        Inicializa a classe carregando os dois modelos de IA (extração e auditoria)
        usando a função load_models().
        """
        self.extraction_model, self.audit_model = load_models()

    def answer_question(self, pdf_files, question, task_type='extraction'):
        """
        Função principal para responder a uma pergunta, selecionando o modelo apropriado.
        Atua como um "roteador" para o modelo de IA correto.
        
        Args:
            pdf_files (list): Lista de caminhos ou objetos de arquivo PDF.
            question (str): A pergunta ou prompt.
            task_type (str): 'extraction' para tarefas simples (padrão), 'audit' para tarefas complexas.
        
        Returns:
            tuple: (response_text, duration) ou (None, 0) em caso de erro.
        """
        start_time = time.time()
        
        model_to_use = None
        if task_type == 'audit':
            model_to_use = self.audit_model
            if not model_to_use:
                st.error("O modelo de AUDITORIA não está disponível. Verifique sua chave 'GEMINI_AUDIT_KEY' nos secrets.")
                return None, 0
        else:  # O padrão é 'extraction'
            model_to_use = self.extraction_model
            if not model_to_use:
                st.error("O modelo de EXTRAÇÃO não está disponível. Verifique sua chave 'GEMINI_EXTRACTION_KEY' nos secrets.")
                return None, 0

        try:
            answer = self._generate_response(model_to_use, pdf_files, question)
            if answer is not None:
                return answer, time.time() - start_time
            else:
                st.warning("Não foi possível obter uma resposta do modelo.")
                return None, 0
        except Exception as e:
            st.error(f"Erro inesperado ao processar a pergunta para a tarefa '{task_type}': {e}")
            st.exception(e)
            return None, 0

    def _generate_response(self, model, pdf_files, question):
        """
        Função interna que prepara e envia a requisição para um modelo Gemini específico.
        """
        try:
            # Preparar os inputs para o modelo
            inputs = []
            
            for pdf_file in pdf_files:
                if hasattr(pdf_file, 'read'):  # Se for um objeto de arquivo (como st.UploadedFile)
                    pdf_bytes = pdf_file.getvalue() # Use getvalue() que é mais seguro
                else:  # Se for um caminho de arquivo (string)
                    with open(pdf_file, 'rb') as f:
                        pdf_bytes = f.read()
                
                part = {"mime_type": "application/pdf", "data": pdf_bytes}
                inputs.append(part)
            
            # Adicionar a pergunta como texto
            inputs.append({"text": question})
            
            # Gerar resposta usando o modelo multimodal fornecido
            response = model.generate_content(inputs)
            
            return response.text
            
        except Exception as e:
            st.error(f"Erro na comunicação com a API Gemini: {str(e)}")
            return None


   






   





   




   



