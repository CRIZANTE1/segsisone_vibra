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
        if self._pdf_analyzer is None: self._pdf_analyzer = PDFQA()
        return self._pdf_analyzer
    def initialize_sheet(self):
        try:
            columns = ['id', 'empresa_id', 'tipo_documento', 'data_emissao', 'vencimento', 'arquivo_id']
            data = self.sheet_ops.carregar_dados_aba(COMPANY_DOCS_SHEET_NAME)
            if not data: return self.sheet_ops.criar_aba(COMPANY_DOCS_SHEET_NAME, columns)
            return True
        except Exception as e:
            st.error(f"Erro ao inicializar aba de documentos da empresa: {e}"); return False
    def load_company_docs_data(self):
        try:
            docs_data = self.sheet_ops.carregar_dados_aba(COMPANY_DOCS_SHEET_NAME)
            columns = ['id', 'empresa_id', 'tipo_documento', 'data_emissao', 'vencimento', 'arquivo_id']
            self.docs_df = pd.DataFrame(docs_data[1:], columns=docs_data[0]) if docs_data and len(docs_data) > 0 else pd.DataFrame(columns=columns)
        except Exception as e:
            st.error(f"Erro ao carregar documentos da empresa: {e}"); self.docs_df = pd.DataFrame()
    def get_docs_by_company(self, company_id):
        if self.docs_df.empty: return pd.DataFrame()
        return self.docs_df[self.docs_df['empresa_id'] == str(company_id)]
    def _parse_flexible_date(self, date_string: str) -> date | None:
        if not date_string or date_string.lower() == 'n/a': return None
        match = re.search(r'(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})|(\d{1,2} de \w+ de \d{4})|(\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2})', date_string, re.IGNORECASE)
        if not match: return None
        clean_date_string = match.group(0).replace('.', '/')
        formats = ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y', '%d de %B de %Y', '%Y-%m-%d']
        for fmt in formats:
            try: return datetime.strptime(clean_date_string, fmt).date()
            except ValueError: continue
        return None

    def analyze_company_doc_pdf(self, pdf_file):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue()); temp_path = temp_file.name
            
            # Prompt atualizado para incluir os novos tipos de documento
            combined_question = """
            Por favor, analise o documento e responda as seguintes perguntas, uma por linha:
            1. Qual o tipo deste documento? Responda 'PGR', 'PCMSO', 'PPR', 'PCA' ou 'Outro'.
            2. Qual a data de emissão, vigência ou elaboração do documento? Responda a data no formato DD/MM/AAAA.
            """
            answer, _ = self.pdf_analyzer.answer_question([temp_path], combined_question); os.unlink(temp_path)
            
            if not answer: return None
            
            lines = answer.strip().split('\n'); results = {}
            for line in lines:
                match = re.match(r'\s*\*?\s*(\d+)\s*\.?\s*(.*)', line)
                if match:
                    key = int(match.group(1)); value = match.group(2).strip()
                    results[key] = value

            doc_type_str = results.get(1, "Outro").upper()
            data_emissao = self._parse_flexible_date(results.get(2, ''))

            if not data_emissao:
                st.error("Não foi possível extrair a data de emissão do documento.")
                return None

            # Lógica de identificação de tipo aprimorada
            if "PGR" in doc_type_str:
                doc_type = "PGR"
            elif "PCMSO" in doc_type_str:
                doc_type = "PCMSO"
            elif "PPR" in doc_type_str:
                doc_type = "PPR"
            elif "PCA" in doc_type_str:
                doc_type = "PCA"
            else:
                doc_type = "Outro"
            
            # Lógica de cálculo de vencimento aprimorada
            if doc_type == "PGR":
                vencimento = data_emissao + timedelta(days=2*365)
                st.info("Documento identificado como PGR. Vencimento calculado para 2 anos.")
            else: # PCMSO, PPR, PCA e Outros terão 1 ano de validade
                vencimento = data_emissao + timedelta(days=365)
                st.info(f"Documento identificado como {doc_type}. Vencimento calculado para 1 ano.")
            
            return {
                'tipo_documento': doc_type,
                'data_emissao': data_emissao, 
                'vencimento': vencimento
            }
        except Exception as e:
            st.error(f"Erro ao analisar o PDF do documento: {e}")
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
