import google.generativeai as genai
from google.generativeai.types import content_types
from AI.api_load import load_api
import time
import numpy as np
import streamlit as st
import re
import pandas as pd



class PDFQA:
    def __init__(self):
        load_api()  # Carrega a API
        self.model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')

    


    #-----------------Função para limpar o texto-------------------------
    def clean_text(self, text):
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s,.!?\'\"-]', '', text)
        return text.strip()

    #----------------- Função para fazer perguntas ao modelo Gemini----------------------
    def ask_gemini(self, pdf_files, question):
        try:
            st.info("Enviando pergunta para o modelo Gemini...")
            
            # Preparar os inputs para o modelo
            inputs = []
            
            # Adicionar os PDFs como FileData
            for pdf_file in pdf_files:
                if hasattr(pdf_file, 'read'):  # Se for um objeto de arquivo (como UploadedFile)
                    pdf_bytes = pdf_file.read()
                    pdf_file.seek(0)  # Resetar o ponteiro do arquivo para o início
                else:  # Se for um caminho de arquivo
                    with open(pdf_file, 'rb') as f:
                        pdf_bytes = f.read()
                
                inputs.append(
                    content_types.FileData(
                        mime_type="application/pdf",
                        data=pdf_bytes
                    )
                )
            
            # Adicionar a pergunta
            inputs.append(question)
            
            # Gerar resposta usando o modelo multimodal
            response = self.model.generate_content(inputs)
            st.success("Resposta recebida do modelo Gemini.")
            return response.text
            
        except Exception as e:
            st.error(f"Erro ao obter resposta do modelo Gemini: {str(e)}")
            return None

    # -------------------Função principal para responder perguntas---------------
    def answer_question(self, pdf_files, question):
        start_time = time.time()

        try:

            with st.spinner("Gerando resposta com o modelo Gemini..."):
                answer = self.ask_gemini(pdf_files, question)
                st.info("Resposta gerada com sucesso.")
            st.success("Resposta gerada com sucesso.")

            end_time = time.time()
            elapsed_time = end_time - start_time

            return answer, elapsed_time
        except Exception as e:
            st.error(f"Erro inesperado ao processar a pergunta: {str(e)}")
            st.exception(e)
            return f"Ocorreu um erro ao processar a pergunta: {str(e)}", 0





   




   



