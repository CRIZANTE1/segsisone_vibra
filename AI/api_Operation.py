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
        self.model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')

   
    #----------------- Função para fazer perguntas ao modelo Gemini----------------------
    def ask_gemini(self, pdf_files, question):
        try:
            progress_bar = st.progress(0)
            
            # Preparar os inputs para o modelo
            inputs = []
            progress_bar.progress(20)
            
            # Adicionar os PDFs
            for pdf_file in pdf_files:
                if hasattr(pdf_file, 'read'):  # Se for um objeto de arquivo (como UploadedFile)
                    pdf_bytes = pdf_file.read()
                    pdf_file.seek(0)  # Resetar o ponteiro do arquivo para o início
                else:  # Se for um caminho de arquivo
                    with open(pdf_file, 'rb') as f:
                        pdf_bytes = f.read()
                
                # Criar parte do conteúdo com o PDF
                part = {
                    "mime_type": "application/pdf",
                    "data": pdf_bytes
                }
                inputs.append(part)
            
            progress_bar.progress(40)
            
            # Adicionar a pergunta como texto
            inputs.append({"text": question})
            
            # Gerar resposta usando o modelo multimodal
            progress_bar.progress(60)
            response = self.model.generate_content(inputs)
            progress_bar.progress(100)
            st.success("Resposta gerada com sucesso!")
            return response.text
            
        except Exception as e:
            st.error(f"Erro ao obter resposta do modelo Gemini: {str(e)}")
            return None

    # -------------------Função principal para responder perguntas---------------
    def answer_question(self, pdf_files, question):
        start_time = time.time()

        try:
            answer = self.ask_gemini(pdf_files, question)
            if answer:
                return answer, time.time() - start_time
            else:
                st.error("Não foi possível obter uma resposta do modelo.")
                return None, 0
        except Exception as e:
            st.error(f"Erro inesperado ao processar a pergunta: {str(e)}")
            st.exception(e)
            return None, 0





   






   





   




   



