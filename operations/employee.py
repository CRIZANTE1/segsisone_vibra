import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, date
from gdrive.gdrive_upload import GoogleDriveUploader
from AI.api_Operation import PDFQA
from operations.sheet import SheetOperations
import tempfile
import os
import re
import locale

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    st.warning("Locale 'pt_BR.UTF-8' não encontrado. A extração de datas por extenso pode falhar.")

gdrive_uploader = GoogleDriveUploader()

@st.cache_resource
def get_sheet_operations():
    return SheetOperations()

@st.cache_data(ttl=30)
def load_sheet_data(sheet_name):
    sheet_ops = get_sheet_operations()
    return sheet_ops.carregar_dados_aba(sheet_name)

class EmployeeManager:
    # ... (__init__ e _parse_flexible_date sem alterações) ...
    def _parse_flexible_date(self, date_string: str) -> date | None:
        if not date_string: return None
        match = re.search(r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})|(\d{1,2} de \w+ de \d{4})|(\d{4}[/\-]\d{1,2}[/\-]\d{1,2})', date_string, re.IGNORECASE)
        if not match: return None
        clean_date_string = match.group(0)
        formats = ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y', '%d de %B de %Y', '%Y-%m-%d']
        for fmt in formats:
            try: return datetime.strptime(clean_date_string, fmt).date()
            except ValueError: continue
        return None

    def __init__(self):
        self.sheet_ops = get_sheet_operations()
        if not self.initialize_sheets(): st.error("Erro ao inicializar as abas da planilha.")
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
        if self._pdf_analyzer is None: self._pdf_analyzer = PDFQA()
        return self._pdf_analyzer

    def load_data(self):
        try:
            from gdrive.config import ASO_SHEET_NAME, EMPLOYEE_SHEET_NAME, EMPLOYEE_DATA_SHEET_NAME, TRAINING_SHEET_NAME
            company_columns = ['id', 'nome', 'cnpj']
            employee_columns = ['id', 'nome', 'empresa_id', 'cargo', 'data_admissao']
            aso_columns = ['id', 'funcionario_id', 'data_aso', 'vencimento', 'arquivo_id', 'riscos', 'cargo', 'tipo_aso']
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
            self.companies_df, self.employees_df, self.aso_df, self.training_df = (pd.DataFrame() for _ in range(4))

    def initialize_sheets(self):
        try:
            from gdrive.config import ASO_SHEET_NAME, EMPLOYEE_SHEET_NAME, EMPLOYEE_DATA_SHEET_NAME, TRAINING_SHEET_NAME
            sheets_structure = {
                EMPLOYEE_SHEET_NAME: ['id', 'nome', 'cnpj'],
                EMPLOYEE_DATA_SHEET_NAME: ['id', 'nome', 'empresa_id', 'cargo', 'data_admissao'],
                ASO_SHEET_NAME: ['id', 'funcionario_id', 'data_aso', 'vencimento', 'arquivo_id', 'riscos', 'cargo', 'tipo_aso'],
                TRAINING_SHEET_NAME: ['id', 'funcionario_id', 'data', 'vencimento', 'norma', 'modulo', 'status', 'arquivo_id', 'tipo_treinamento', 'carga_horaria']
            }
            for sheet_name, columns in sheets_structure.items():
                data = self.sheet_ops.carregar_dados_aba(sheet_name)
                if not data: self.sheet_ops.criar_aba(sheet_name, columns)
                else:
                    header = data[0]
                    if sheet_name == ASO_SHEET_NAME and 'tipo_aso' not in header:
                         st.warning(f"A coluna 'tipo_aso' não foi encontrada na aba {ASO_SHEET_NAME} e será adicionada. Verifique sua planilha.")
                         self.sheet_ops.limpar_e_recriar_aba(sheet_name, columns)
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
                # --- CORREÇÃO APLICADA AQUI ---
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
                 # --- CORREÇÃO APLICADA AQUI ---
                 training_docs['vencimento'] = pd.to_datetime(training_docs['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        return training_docs

    def analyze_training_pdf(self, pdf_file):
        # ... (código de análise de treinamento sem alterações) ...
        return {}

    def analyze_aso_pdf(self, pdf_file):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name
            
            combined_question = "..."
            answer, _ = self.pdf_analyzer.answer_question([temp_path], combined_question)
            os.unlink(temp_path)
            if not answer: return None
            
            lines = answer.strip().split('\n')
            results = {int(line.split('.', 1)[0]): line.split('.', 1)[1].strip() for line in lines if '.' in line}
            
            data_aso = self._parse_flexible_date(results.get(1, ''))
            if not data_aso:
                st.error(f"Não foi possível extrair uma data de realização válida da resposta: '{results.get(1, '')}'")
                return None
            
            vencimento = self._parse_flexible_date(results.get(2, ''))
            
            tipo_aso_str = results.get(5, '').lower()
            tipo_aso = "Não identificado"
            if any(term in tipo_aso_str for term in ['admissional', 'admissão']): tipo_aso = 'Admissional'
            elif 'periódico' in tipo_aso_str: tipo_aso = 'Periódico'
            elif 'demissional' in tipo_aso_str: tipo_aso = 'Demissional'
            elif any(term in tipo_aso_str for term in ['mudança', 'função', 'cargo']): tipo_aso = 'Mudança de Risco'
            elif 'retorno' in tipo_aso_str: tipo_aso = 'Retorno ao Trabalho'
            elif any(term in tipo_aso_str for term in ['monitoramento', 'pontual']): tipo_aso = 'Monitoramento Pontual'

            if not vencimento and tipo_aso != 'Demissional':
                st.info(f"Vencimento não encontrado. Calculando com base no tipo '{tipo_aso}'...")
                if tipo_aso in ['Admissional', 'Periódico', 'Mudança de Risco', 'Retorno ao Trabalho']:
                    vencimento = data_aso + timedelta(days=365)
                elif tipo_aso == 'Monitoramento Pontual':
                    vencimento = data_aso + timedelta(days=180)
                else:
                    vencimento = data_aso + timedelta(days=365)
                    st.warning("Tipo de ASO não identificado, assumindo validade de 1 ano.")
            
            return {
                'data_aso': data_aso, 'vencimento': vencimento, 
                'riscos': results.get(3, ""), 'cargo': results.get(4, ""),
                'tipo_aso': tipo_aso
            }
        except Exception as e:
            st.error(f"Erro ao analisar o PDF do ASO: {str(e)}")
            return None

    # O resto do código (add_company, add_employee, etc.) permanece igual
    def add_company(self, nome, cnpj):
        if not self.companies_df.empty and cnpj in self.companies_df['cnpj'].values:
            return None, "CNPJ já cadastrado"
        new_data = [nome, cnpj]
        try:
            company_id = self.sheet_ops.adc_dados_aba(EMPLOYEE_SHEET_NAME, new_data)
            if company_id:
                st.cache_data.clear(); self.load_data()
                return company_id, "Empresa cadastrada com sucesso"
            return None, "Falha ao obter ID da empresa."
        except Exception as e:
            return None, f"Erro ao cadastrar empresa: {str(e)}"
    
    def add_employee(self, nome, cargo, data_admissao, empresa_id):
        new_data = [nome, empresa_id, cargo, data_admissao.strftime("%d/%m/%Y")]
        try:
            employee_id = self.sheet_ops.adc_dados_aba(EMPLOYEE_DATA_SHEET_NAME, new_data)
            if employee_id:
                st.cache_data.clear(); self.load_data()
                return employee_id, "Funcionário adicionado com sucesso"
            return None, "Erro ao adicionar funcionário na planilha"
        except Exception as e:
            return None, f"Erro ao adicionar funcionário: {str(e)}"

    def add_aso(self, id, data_aso, vencimento, arquivo_id, riscos, cargo, tipo_aso="Não identificado"):
        if not all([id, data_aso, arquivo_id, cargo]):
            st.error("Dados essenciais para o ASO (ID, Data, Arquivo, Cargo) estão faltando.")
            return None
        vencimento_str = vencimento.strftime("%d/%m/%Y") if vencimento else "N/A"
        new_data = [str(id), data_aso.strftime("%d/%m/%Y"), vencimento_str, str(arquivo_id), str(riscos), str(cargo), str(tipo_aso)]
        try:
            aso_id = self.sheet_ops.adc_dados_aba(ASO_SHEET_NAME, new_data)
            if aso_id:
                st.cache_data.clear(); self.load_data()
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
                st.cache_data.clear(); self.load_data()
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

    def calcular_vencimento_treinamento(self, data, norma, modulo=None, tipo_treinamento='formação'):
        if not isinstance(data, date): return None
        norma_padronizada = self._padronizar_norma(norma)
        if not norma_padronizada: return None
        
        config = self.nr20_config.get(modulo) if norma_padronizada == "NR-20" else self.nr_config.get(norma_padronizada)
        if config:
            anos_validade = config.get('reciclagem_anos', 1)
            return data + timedelta(days=anos_validade * 365)
        return None

    def validar_treinamento(self, norma, modulo, tipo_treinamento, carga_horaria):
        return True, ""



