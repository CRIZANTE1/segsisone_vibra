import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, date
from gdrive.gdrive_upload import GoogleDriveUploader
from AI.api_Operation import PDFQA
from operations.sheet import SheetOperations
import tempfile
import os
import re # <-- ADICIONADO: Importa o módulo de expressões regulares
from gdrive.config import (
    ASO_SHEET_NAME,
    EMPLOYEE_SHEET_NAME,
    EMPLOYEE_DATA_SHEET_NAME,
    TRAINING_SHEET_NAME
)

# ... (o resto dos imports e inicializações globais permanecem iguais) ...
gdrive_uploader = GoogleDriveUploader()

@st.cache_resource
def get_sheet_operations():
    return SheetOperations()

@st.cache_data(ttl=30)
def load_sheet_data(sheet_name):
    sheet_ops = get_sheet_operations()
    return sheet_ops.carregar_dados_aba(sheet_name)


class EmployeeManager:
    # ... (__init__, pdf_analyzer, load_data, initialize_sheets permanecem iguais) ...
    def __init__(self):
        self.sheet_ops = get_sheet_operations()
        if not self.initialize_sheets():
            st.error("Erro ao inicializar as abas da planilha. Algumas funcionalidades podem não funcionar corretamente.")
        self.load_data()
        self._pdf_analyzer = None
        self.nr20_config = {
            'Básico': {'reciclagem_anos': 3, 'reciclagem_horas': 4, 'inicial_horas': 8},
            'Intermediário': {'reciclagem_anos': 2, 'reciclagem_horas': 4, 'inicial_horas': 16},
            'Avançado I': {'reciclagem_anos': 1, 'reciclagem_horas': 4, 'inicial_horas': 32},
            'Avançado II': {'reciclagem_anos': 1, 'reciclagem_horas': 4, 'inicial_horas': 40}
        }
        self.nr_config = {
            'NR-35': {'inicial_horas': 8, 'reciclagem_horas': 8, 'reciclagem_anos': 2},
            'NR-10': {'inicial_horas': 40, 'reciclagem_horas': 40, 'reciclagem_anos': 2},
            'NR-18': {'inicial_horas': 8, 'reciclagem_horas': 8, 'reciclagem_anos': 1},
            'NR-06': {'inicial_horas': 3, 'reciclagem_horas': 3, 'reciclagem_anos': 3},
            'NR-6': {'inicial_horas': 3, 'reciclagem_horas': 3, 'reciclagem_anos': 3},
            'NR-12': {'inicial_horas': 8, 'reciclagem_horas': 8, 'reciclagem_anos': 2},
            'NR-34': {'inicial_horas': 8, 'reciclagem_horas': 8, 'reciclagem_anos': 1}
        }

    @property
    def pdf_analyzer(self):
        if self._pdf_analyzer is None:
            self._pdf_analyzer = PDFQA()
        return self._pdf_analyzer

    def load_data(self):
        try:
            company_columns = ['id', 'nome', 'cnpj']
            employee_columns = ['id', 'nome', 'empresa_id', 'cargo', 'data_admissao']
            aso_columns = ['id', 'funcionario_id', 'data_aso', 'vencimento', 'arquivo_id', 'riscos', 'cargo']
            training_columns = ['id', 'funcionario_id', 'data', 'vencimento', 'norma', 'modulo', 'status', 'arquivo_id', 'tipo_treinamento', 'carga_horaria']
            
            companies_data = load_sheet_data(EMPLOYEE_SHEET_NAME)
            self.companies_df = pd.DataFrame(companies_data[1:], columns=companies_data[0]) if companies_data and len(companies_data) > 0 else pd.DataFrame(columns=company_columns)
            
            employees_data = load_sheet_data(EMPLOYEE_DATA_SHEET_NAME)
            self.employees_df = pd.DataFrame(employees_data[1:], columns=employees_data[0]) if employees_data and len(employees_data) > 0 else pd.DataFrame(columns=employee_columns)

            aso_data = load_sheet_data(ASO_SHEET_NAME)
            self.aso_df = pd.DataFrame(aso_data[1:], columns=aso_data[0]) if aso_data and len(aso_data) > 0 else pd.DataFrame(columns=aso_columns)
            
            training_data = load_sheet_data(TRAINING_SHEET_NAME)
            self.training_df = pd.DataFrame(training_data[1:], columns=training_data[0]) if training_data and len(training_data) > 0 else pd.DataFrame(columns=training_columns)

        except Exception as e:
            st.error(f"Erro ao carregar dados: {str(e)}")
            self.companies_df, self.employees_df, self.aso_df, self.training_df = (pd.DataFrame(columns=c) for c in [company_columns, employee_columns, aso_columns, training_columns])

    def initialize_sheets(self):
        try:
            sheets_structure = {
                EMPLOYEE_SHEET_NAME: ['id', 'nome', 'cnpj'],
                EMPLOYEE_DATA_SHEET_NAME: ['id', 'nome', 'empresa_id', 'cargo', 'data_admissao'],
                ASO_SHEET_NAME: ['id', 'funcionario_id', 'data_aso', 'vencimento', 'arquivo_id', 'riscos', 'cargo'],
                TRAINING_SHEET_NAME: ['id', 'funcionario_id', 'data', 'vencimento', 'norma', 'modulo', 'status', 'arquivo_id', 'tipo_treinamento', 'carga_horaria']
            }
            for sheet_name, columns in sheets_structure.items():
                if not self.sheet_ops.carregar_dados_aba(sheet_name):
                    self.sheet_ops.criar_aba(sheet_name, columns)
            return True
        except Exception as e:
            st.error(f"Erro ao inicializar as abas: {str(e)}")
            return False

    def get_latest_aso_by_employee(self, employee_id):
        if self.aso_df.empty: return pd.DataFrame()
        aso_docs = self.aso_df[self.aso_df['funcionario_id'] == str(employee_id)].copy()
        if not aso_docs.empty:
            aso_docs['data_aso'] = pd.to_datetime(aso_docs['data_aso'], format='%d/%m/%Y', errors='coerce')
            aso_docs = aso_docs.dropna(subset=['data_aso']).sort_values('data_aso', ascending=False).head(1)
            if not aso_docs.empty:
                aso_docs['data_aso'] = aso_docs['data_aso'].dt.date
                aso_docs['vencimento'] = pd.to_datetime(aso_docs['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        return aso_docs

    def get_all_trainings_by_employee(self, employee_id):
        if self.training_df.empty: return pd.DataFrame()
        training_docs = self.training_df[self.training_df['funcionario_id'] == str(employee_id)].copy()
        if not training_docs.empty:
             training_docs['data'] = pd.to_datetime(training_docs['data'], format='%d/%m/%Y', errors='coerce')
             training_docs = training_docs.dropna(subset=['data']).sort_values('data', ascending=False)
             if not training_docs.empty:
                 training_docs['data'] = training_docs['data'].dt.date
                 training_docs['vencimento'] = pd.to_datetime(training_docs['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        return training_docs
    
    # --- CORREÇÃO APLICADA AQUI ---
    def analyze_training_pdf(self, pdf_file):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name
            
            combined_question = """
            Por favor, analise o documento e responda as seguintes perguntas, uma por linha:
            1. Qual é a norma regulamentadora (NR) do treinamento? (ex: NR-10)
            2. Qual é o módulo do treinamento? (ex: Básico, Intermediário, Avançado I, Avançado II, ou 'Não se aplica')
            3. Qual é a data de realização do treinamento? Responda APENAS a data no formato DD/MM/AAAA.
            4. Este documento é um certificado de reciclagem? Responda 'sim' ou 'não'.
            5. Qual é a carga horária total do treinamento em horas? Responda APENAS o número.
            """
            answer, _ = self.pdf_analyzer.answer_question([temp_path], combined_question)
            os.unlink(temp_path)
            if not answer: return None

            lines = answer.strip().split('\n')
            results = {int(line.split('.', 1)[0]): line.split('.', 1)[1].strip() for line in lines if '.' in line}
            
            data = None
            # Usa regex para encontrar a data na resposta da pergunta 3
            if 3 in results:
                match = re.search(r'\d{2}/\d{2}/\d{4}', results[3])
                if match:
                    data = datetime.strptime(match.group(0), "%d/%m/%Y").date()

            norma = self._padronizar_norma(results.get(1))
            
            if not data or not norma:
                st.warning("Não foi possível extrair a data ou a norma do PDF.")
                return None

            return {
                'data': data,
                'norma': norma,
                'modulo': results.get(2, ""),
                'tipo_treinamento': 'reciclagem' if 'sim' in results.get(4, '').lower() else 'formação',
                'carga_horaria': int(''.join(filter(str.isdigit, results.get(5, '0'))))
            }
        except Exception as e:
            st.error(f"Erro ao analisar o PDF de treinamento: {e}")
            return None

    # --- CORREÇÃO APLICADA AQUI ---
    def analyze_aso_pdf(self, pdf_file):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name
            
            combined_question = """
            Por favor, analise o documento e responda as seguintes perguntas, uma por linha:
            1. Qual é a data de realização do ASO? Responda APENAS a data no formato DD/MM/AAAA.
            2. Qual é a data de vencimento do ASO? Responda APENAS a data no formato DD/MM/AAAA. Se não houver, não responda.
            3. Quais são os riscos ocupacionais identificados? Liste apenas os riscos.
            4. Qual é o cargo do funcionário conforme consta no ASO? Responda apenas o cargo.
            """
            answer, _ = self.pdf_analyzer.answer_question([temp_path], combined_question)
            os.unlink(temp_path)
            if not answer: return None
            
            lines = answer.strip().split('\n')
            results = {int(line.split('.', 1)[0]): line.split('.', 1)[1].strip() for line in lines if '.' in line}
            
            data_aso = None
            vencimento = None

            # Usa regex para encontrar a data de realização
            if 1 in results:
                match = re.search(r'\d{2}/\d{2}/\d{4}', results[1])
                if match:
                    data_aso = datetime.strptime(match.group(0), "%d/%m/%Y").date()
            
            # Usa regex para encontrar a data de vencimento
            if 2 in results:
                match = re.search(r'\d{2}/\d{2}/\d{4}', results[2])
                if match:
                    vencimento = datetime.strptime(match.group(0), "%d/%m/%Y").date()
            
            if data_aso and not vencimento:
                vencimento = data_aso + timedelta(days=365)
            
            if not data_aso:
                st.warning("Não foi possível extrair a data de realização do ASO.")
                return None

            return {'data_aso': data_aso, 'vencimento': vencimento, 'riscos': results.get(3, ""), 'cargo': results.get(4, "")}
        except Exception as e:
            st.error(f"Erro ao analisar o PDF do ASO: {e}")
            return None

    # --- O RESTANTE DO CÓDIGO PERMANECE IGUAL ---
    def add_company(self, nome, cnpj):
        if not self.companies_df.empty and cnpj in self.companies_df['cnpj'].values:
            return None, "CNPJ já cadastrado"
        new_data = [nome, cnpj]
        try:
            company_id = self.sheet_ops.adc_dados_aba(EMPLOYEE_SHEET_NAME, new_data)
            if company_id:
                st.cache_data.clear()
                self.load_data()
                return company_id, "Empresa cadastrada com sucesso"
            return None, "Falha ao obter ID da empresa."
        except Exception as e:
            return None, f"Erro ao cadastrar empresa: {str(e)}"
    
    def add_employee(self, nome, cargo, data_admissao, empresa_id):
        new_data = [nome, empresa_id, cargo, data_admissao.strftime("%d/%m/%Y")]
        try:
            employee_id = self.sheet_ops.adc_dados_aba(EMPLOYEE_DATA_SHEET_NAME, new_data)
            if employee_id:
                st.cache_data.clear()
                self.load_data()
                return employee_id, "Funcionário adicionado com sucesso"
            return None, "Erro ao adicionar funcionário na planilha"
        except Exception as e:
            return None, f"Erro ao adicionar funcionário: {str(e)}"

    def add_aso(self, id, data_aso, vencimento, arquivo_id, riscos, cargo):
        if not all([id, data_aso, vencimento, arquivo_id, cargo]):
            st.error("Dados essenciais para o ASO estão faltando.")
            return None
        new_data = [str(id), data_aso.strftime("%d/%m/%Y"), vencimento.strftime("%d/%m/%Y"), str(arquivo_id), str(riscos), str(cargo)]
        try:
            aso_id = self.sheet_ops.adc_dados_aba(ASO_SHEET_NAME, new_data)
            if aso_id:
                st.cache_data.clear()
                self.load_data()
                return aso_id
            return None
        except Exception as e:
            st.error(f"Erro ao adicionar ASO: {str(e)}")
            return None

    def _padronizar_norma(self, norma):
        if not norma: return None
        norma = str(norma).strip().upper().replace("NR ", "NR-")
        parts = norma.split('-')
        if len(parts) == 2 and parts[0] == "NR" and parts[1].isdigit() and len(parts[1]) == 1:
            return f"NR-0{parts[1]}"
        return norma

    def add_training(self, id, data, vencimento, norma, modulo, status, anexo, tipo_treinamento, carga_horaria):
        if not all([data, norma, vencimento]):
            st.error("Dados essenciais (data, norma, vencimento) para o treinamento estão faltando.")
            return None
        new_data = [
            str(id), data.strftime("%d/%m/%Y"), vencimento.strftime("%d/%m/%Y"), self._padronizar_norma(norma),
            str(modulo), str(status), str(anexo), str(tipo_treinamento), str(carga_horaria)
        ]
        try:
            training_id = self.sheet_ops.adc_dados_aba(TRAINING_SHEET_NAME, new_data)
            if training_id:
                st.cache_data.clear()
                self.load_data()
                return training_id
            return None
        except Exception as e:
            st.error(f"Erro ao adicionar treinamento: {str(e)}")
            return None

    def get_company_name(self, company_id):
        if self.companies_df.empty: return None
        company = self.companies_df[self.companies_df['id'] == str(company_id)]
        return company.iloc[0]['nome'] if not company.empty else None
    
    def get_employee_name(self, employee_id):
        if self.employees_df.empty: return None
        employee = self.employees_df[self.employees_df['id'] == str(employee_id)]
        return employee.iloc[0]['nome'] if not employee.empty else None
    
    def get_employees_by_company(self, company_id):
        if self.employees_df.empty or 'empresa_id' not in self.employees_df.columns:
            return pd.DataFrame()
        return self.employees_df[self.employees_df['empresa_id'] == str(company_id)]
    
    def get_employee_docs(self, employee_id):
        latest_aso = self.get_latest_aso_by_employee(employee_id)
        all_trainings = self.get_all_trainings_by_employee(employee_id)
        return latest_aso, all_trainings

    def calcular_vencimento_treinamento(self, data_realizacao, norma, modulo=None, tipo_treinamento='formação'):
        if not isinstance(data_realizacao, date): return None
        norma_padronizada = self._padronizar_norma(norma)
        if not norma_padronizada: return None
        
        config = self.nr20_config.get(modulo) if norma_padronizada == "NR-20" else self.nr_config.get(norma_padronizada)
        if config:
            anos_validade = config.get('reciclagem_anos', 1)
            return data_realizacao + timedelta(days=anos_validade * 365)
        return None

    def validar_treinamento(self, norma, modulo, tipo_treinamento, carga_horaria):
        return True, ""







