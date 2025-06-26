import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, date
import re
from operations.sheet import SheetOperations
from gdrive.config import COMPANY_DOCS_SHEET_NAME, AUDIT_RESULTS_SHEET_NAME
from AI.api_Operation import PDFQA
import tempfile
import os

@st.cache_resource
def get_sheet_ops_docs():
    return SheetOperations()

class CompanyDocsManager:
    def __init__(self):
        self.sheet_ops = get_sheet_ops_docs()
        if not self.initialize_sheets():
            st.error("Erro ao inicializar as abas da empresa.")
        self.load_company_data()
        self._pdf_analyzer = None

    @property
    def pdf_analyzer(self):
        if self._pdf_analyzer is None:
            self._pdf_analyzer = PDFQA()
        return self._pdf_analyzer

    def initialize_sheets(self):
        try:
            docs_columns = ['id', 'empresa_id', 'tipo_documento', 'data_emissao', 'vencimento', 'arquivo_id']
            
            # Usa os nomes exatos que você especificou
            audit_columns = ["id", "id_auditoria", "data_auditoria", "id_empresa", "id_documento_original", 
                             "id_funcionario", "tipo_documento", "norma_auditada", 
                             "item_de_verificacao", "Status", "observacao"]
            
            if not self.sheet_ops.carregar_dados_aba(COMPANY_DOCS_SHEET_NAME):
                self.sheet_ops.criar_aba(COMPANY_DOCS_SHEET_NAME, docs_columns)
            
            data_audit = self.sheet_ops.carregar_dados_aba(AUDIT_RESULTS_SHEET_NAME)
            if not data_audit:
                self.sheet_ops.criar_aba(AUDIT_RESULTS_SHEET_NAME, audit_columns)
            elif data_audit and 'id_auditoria' not in data_audit[0]:
                st.warning(f"A coluna 'id_auditoria' não foi encontrada na aba {AUDIT_RESULTS_SHEET_NAME}. A funcionalidade pode ser limitada.")
            
            return True
        except Exception as e:
            st.error(f"Erro ao inicializar abas: {e}"); return False

    def load_company_data(self):
        try:
            docs_data = self.sheet_ops.carregar_dados_aba(COMPANY_DOCS_SHEET_NAME)
            # Define as colunas que você REALMENTE espera ter
            expected_cols = ['id', 'empresa_id', 'tipo_documento', 'data_emissao', 'vencimento', 'arquivo_id', 'status']
            
            if docs_data and len(docs_data) > 0:
                # Pega o cabeçalho real da planilha
                header = docs_data[0]
                # Filtra o cabeçalho para remover colunas vazias
                cleaned_header = [col for col in header if col]
                
                # Pega os dados e ajusta cada linha para ter o mesmo número de colunas do cabeçalho limpo
                num_cols = len(cleaned_header)
                cleaned_data = [row[:num_cols] for row in docs_data[1:]]
    
                # Cria o DataFrame com os dados e cabeçalho limpos
                self.docs_df = pd.DataFrame(cleaned_data, columns=cleaned_header)
            else:
                # Se não houver dados, cria um DataFrame vazio com as colunas esperadas
                self.docs_df = pd.DataFrame(columns=expected_cols)
    
            # Garante que todas as colunas esperadas existam no DataFrame, preenchendo com N/A se faltarem
            for col in expected_cols:
                if col not in self.docs_df.columns:
                    self.docs_df[col] = pd.NA
    
            # Converte as colunas de data após o carregamento e limpeza
            if not self.docs_df.empty:
                self.docs_df['data_emissao'] = pd.to_datetime(self.docs_df['data_emissao'], format='%d/%m/%Y', errors='coerce')
                self.docs_df['vencimento'] = pd.to_datetime(self.docs_df['vencimento'], format='%d/%m/%Y', errors='coerce')

    def get_docs_by_company(self, company_id):
        if self.docs_df.empty: return pd.DataFrame()
        return self.docs_df[self.docs_df['empresa_id'] == str(company_id)]
        
    def get_audits_by_company(self, company_id):
        if self.audit_df.empty:
            return pd.DataFrame()
        if 'id_empresa' in self.audit_df.columns:
            return self.audit_df[self.audit_df['id_empresa'] == str(company_id)]
        return pd.DataFrame()
        
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
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name
            
            combined_question = """
            Por favor, analise o documento e responda as seguintes perguntas, uma por linha:
            1. Qual o tipo deste documento? Responda 'PGR', 'PCMSO', 'PPR', 'PCA' ou 'Outro'.
            2. Qual a data de emissão, vigência ou elaboração do documento? Responda a data no formato DD/MM/AAAA.
            """
            answer, _ = self.pdf_analyzer.answer_question([temp_path], combined_question)
            os.unlink(temp_path)
            
            if not answer: return None
            
            lines = answer.strip().split('\n')
            results = {}
            for line in lines:
                match = re.match(r'\s*\*?\s*(\d+)\s*\.?\s*(.*)', line)
                if match:
                    key = int(match.group(1))
                    value = match.group(2).strip()
                    results[key] = value

            doc_type_str = results.get(1, "Outro").upper()
            data_emissao = self._parse_flexible_date(results.get(2, ''))

            if not data_emissao:
                st.error("Não foi possível extrair a data de emissão do documento.")
                return None

            if "PGR" in doc_type_str: doc_type = "PGR"
            elif "PCMSO" in doc_type_str: doc_type = "PCMSO"
            elif "PPR" in doc_type_str: doc_type = "PPR"
            elif "PCA" in doc_type_str: doc_type = "PCA"
            else: doc_type = "Outro"
            
            if doc_type == "PGR":
                vencimento = data_emissao + timedelta(days=2*365)
                st.info("Documento identificado como PGR. Vencimento calculado para 2 anos.")
            else:
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
                self.load_company_data()
                return doc_id
            return None
        except Exception as e:
            st.error(f"Erro ao adicionar documento da empresa: {e}")
            return None
