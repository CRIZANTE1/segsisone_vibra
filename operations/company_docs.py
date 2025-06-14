import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, date
import re
from operations.sheet import SheetOperations
from gdrive.config import COMPANY_DOCS_SHEET_NAME
from AI.api_Operation import PDFQA
import tempfile
import os

@st.cache_resource
def get_sheet_ops_docs():
    # Usando uma função de cache diferente para não conflitar
    return SheetOperations()

class CompanyDocsManager:
    def __init__(self):
        self.sheet_ops = get_sheet_ops_docs()
        if not self.initialize_sheet():
            st.error("Erro ao inicializar a aba de documentos da empresa.")
        self.load_company_docs_data()
        self._pdf_analyzer = None

    @property
    def pdf_analyzer(self):
        if self._pdf_analyzer is None:
            self._pdf_analyzer = PDFQA()
        return self._pdf_analyzer

    def initialize_sheet(self):
        try:
            columns = ['id', 'empresa_id', 'tipo_documento', 'data_emissao', 'vencimento', 'arquivo_id']
            data = self.sheet_ops.carregar_dados_aba(COMPANY_DOCS_SHEET_NAME)
            if not data:
                return self.sheet_ops.criar_aba(COMPANY_DOCS_SHEET_NAME, columns)
            return True
        except Exception as e:
            st.error(f"Erro ao inicializar aba de documentos da empresa: {e}")
            return False

    def load_company_docs_data(self):
        try:
            docs_data = self.sheet_ops.carregar_dados_aba(COMPANY_DOCS_SHEET_NAME)
            columns = ['id', 'empresa_id', 'tipo_documento', 'data_emissao', 'vencimento', 'arquivo_id']
            self.docs_df = pd.DataFrame(docs_data[1:], columns=docs_data[0]) if docs_data and len(docs_data) > 0 else pd.DataFrame(columns=columns)
        except Exception as e:
            st.error(f"Erro ao carregar documentos da empresa: {e}")
            self.docs_df = pd.DataFrame()

    def get_docs_by_company(self, company_id):
        if self.docs_df.empty:
            return pd.DataFrame()
        return self.docs_df[self.docs_df['empresa_id'] == str(company_id)]

    def analyze_pgr_pdf(self, pdf_file):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name
            
            combined_question = "Qual é a data de emissão ou vigência deste PGR? Responda a data no formato DD/MM/AAAA."
            answer, _ = self.pdf_analyzer.answer_question([temp_path], combined_question)
            os.unlink(temp_path)
            
            if not answer: return None
            
            match = re.search(r'\d{2}/\d{2}/\d{4}', answer)
            if match:
                data_emissao = datetime.strptime(match.group(0), "%d/%m/%Y").date()
                # PGR geralmente tem validade de 2 anos, mas pode variar. Vamos assumir 2 anos.
                vencimento = data_emissao + timedelta(days=2*365)
                return {'data_emissao': data_emissao, 'vencimento': vencimento}
            return None
        except Exception as e:
            st.error(f"Erro ao analisar o PDF do PGR: {e}")
            return None

    def add_company_document(self, empresa_id, tipo_documento, data_emissao, vencimento, arquivo_id):
        new_data = [
            str(empresa_id), str(tipo_documento), 
            data_emissao.strftime("%d/%m/%Y"), 
            vencimento.strftime("%d/%m/%Y"), 
            str(arquivo_id)
        ]
        try:
            doc_id = self.sheet_ops.adc_dados_aba(COMPANY_DOCS_SHEET_NAME, new_data)
            if doc_id:
                st.cache_data.clear()
                self.load_company_docs_data()
                return doc_id
            return None
        except Exception as e:
            st.error(f"Erro ao adicionar documento da empresa: {e}")
            return None
