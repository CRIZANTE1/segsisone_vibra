import pandas as pd
import streamlit as st
from datetime import datetime, date
from gdrive.google_api_manager import GoogleApiManager
from AI.api_Operation import PDFQA
from operations.sheet import SheetOperations
import tempfile
import os
import re
import locale
import json
from dateutil.relativedelta import relativedelta
from auth.auth_utils import get_user_email
from fuzzywuzzy import process
import logging

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    # Fallback para o locale padrão se pt_BR não estiver disponível
    pass

logger = logging.getLogger('segsisone_app.employee_manager')

class EmployeeManager:
    def __init__(self, spreadsheet_id: str, folder_id: str):
        logger.info(f"Inicializando EmployeeManager para spreadsheet_id: ...{spreadsheet_id[-6:]}")
        self.sheet_ops = SheetOperations(spreadsheet_id)
        self.folder_id = folder_id
        self.api_manager = GoogleApiManager()
        self._pdf_analyzer = None
        
        # Dicionários de configuração movidos para o __init__ para clareza
        self.nr20_config = {
            'Básico': {'reciclagem_anos': 3}, 'Intermediário': {'reciclagem_anos': 2},
            'Avançado I': {'reciclagem_anos': 2}, 'Avançado II': {'reciclagem_anos': 1}
        }
        self.nr_config = {
            'NR-35': {'reciclagem_anos': 2}, 'NR-10': {'reciclagem_anos': 2}, 'NR-18': {'reciclagem_anos': 1},
            'NR-06': {'reciclagem_anos': 10}, 'NR-12': {'reciclagem_anos': 5}, 'NR-34': {'reciclagem_anos': 1},
            'NR-33': {'reciclagem_anos': 1}, 'BRIGADA DE INCÊNDIO': {'reciclagem_anos': 1},
            'NR-11': {'reciclagem_anos': 3}, 'NBR-16710 RESGATE TÉCNICO': {'reciclagem_anos': 1},
            'PERMISSÃO DE TRABALHO (PT)': {'reciclagem_anos': 1}
        }
        
        # Inicializa os DataFrames vazios para evitar erros se o carregamento falhar
        self.companies_df = pd.DataFrame()
        self.employees_df = pd.DataFrame()
        self.aso_df = pd.DataFrame()
        self.training_df = pd.DataFrame()
        self.training_matrix_df = pd.DataFrame()
        
        self.data_loaded_successfully = False
        self.load_data()

    @property
    def pdf_analyzer(self):
        if self._pdf_analyzer is None: self._pdf_analyzer = PDFQA()
        return self._pdf_analyzer

    def load_data(self):
        """Carrega todos os DataFrames da unidade, garantindo que as colunas essenciais sempre existam."""
        logger.info("Iniciando o carregamento de todos os DataFrames para EmployeeManager.")
        
        # Define as colunas esperadas para cada DataFrame para garantir consistência
        expected_company_cols = ['id', 'nome', 'cnpj', 'status']
        expected_employee_cols = ['id', 'nome', 'empresa_id', 'cargo', 'data_admissao', 'status']
        expected_aso_cols = ['id', 'funcionario_id', 'data_aso', 'vencimento', 'arquivo_id', 'riscos', 'cargo', 'tipo_aso']
        expected_training_cols = ['id', 'funcionario_id', 'data', 'vencimento', 'norma', 'modulo', 'status', 'anexo', 'tipo_treinamento', 'carga_horaria']
        expected_matrix_cols = ['funcao', 'treinamentos_obrigatorios']

        try:
            # --- EMPRESAS ---
            companies_data = self.sheet_ops.carregar_dados_aba("empresas")
            if companies_data and len(companies_data) > 1:
                self.companies_df = pd.DataFrame(companies_data[1:], columns=companies_data[0])
            else:
                self.companies_df = pd.DataFrame(columns=expected_company_cols)

            # --- FUNCIONÁRIOS ---
            employees_data = self.sheet_ops.carregar_dados_aba("funcionarios")
            if employees_data and len(employees_data) > 1:
                self.employees_df = pd.DataFrame(employees_data[1:], columns=employees_data[0])
            else:
                self.employees_df = pd.DataFrame(columns=expected_employee_cols)

            # --- ASOS ---
            aso_data = self.sheet_ops.carregar_dados_aba("asos")
            if aso_data and len(aso_data) > 1:
                self.aso_df = pd.DataFrame(aso_data[1:], columns=aso_data[0])
            else:
                self.aso_df = pd.DataFrame(columns=expected_aso_cols)

            # --- TREINAMENTOS ---
            training_data = self.sheet_ops.carregar_dados_aba("treinamentos")
            if training_data and len(training_data) > 1:
                self.training_df = pd.DataFrame(training_data[1:], columns=training_data[0])
            else:
                self.training_df = pd.DataFrame(columns=expected_training_cols)

            # --- MATRIZ DE TREINAMENTOS ---
            matrix_data = self.sheet_ops.carregar_dados_aba("matriz_treinamentos")
            if matrix_data and len(matrix_data) > 1:
                self.training_matrix_df = pd.DataFrame(matrix_data[1:], columns=matrix_data[0])
            else:
                self.training_matrix_df = pd.DataFrame(columns=expected_matrix_cols)
            
            self.data_loaded_successfully = True
            logger.info("Todos os DataFrames para EmployeeManager carregados com sucesso.")

        except Exception as e:
            logger.error(f"FALHA CRÍTICA ao carregar dados da unidade para EmployeeManager: {str(e)}", exc_info=True)
            st.error(f"Erro crítico ao carregar dados essenciais da unidade: {str(e)}")
            # Em caso de erro, garante que todos os DFs sejam inicializados como vazios
            self.companies_df = pd.DataFrame(columns=expected_company_cols)
            self.employees_df = pd.DataFrame(columns=expected_employee_cols)
            self.aso_df = pd.DataFrame(columns=expected_aso_cols)
            self.training_df = pd.DataFrame(columns=expected_training_cols)
            self.training_matrix_df = pd.DataFrame(columns=expected_matrix_cols)

    def upload_documento_e_obter_link(self, arquivo, novo_nome):
        """Usa o api_manager para fazer upload de um arquivo na pasta da unidade."""
        if not self.folder_id:
            st.error("O ID da pasta desta unidade não está definido. Não é possível fazer o upload.")
            return None
        return self.api_manager.upload_file(self.folder_id, arquivo, novo_nome)

    def add_company(self, nome, cnpj):
        if not self.companies_df.empty and cnpj in self.companies_df['cnpj'].values:
            return None, "CNPJ já cadastrado."
        new_data = [nome, cnpj, "Ativo"]
        company_id = self.sheet_ops.adc_dados_aba("empresas", new_data)
        if company_id:
            self.load_data() # Recarrega os dados após a adição
            return company_id, "Empresa cadastrada com sucesso"
        return None, "Falha ao obter ID da empresa."

    def add_employee(self, nome, cargo, data_admissao, empresa_id):
        new_data = [nome, str(empresa_id), cargo, data_admissao.strftime("%d/%m/%Y"), "Ativo"]
        employee_id = self.sheet_ops.adc_dados_aba("funcionarios", new_data)
        if employee_id:
            self.load_data() # Recarrega os dados após a adição
            return employee_id, "Funcionário adicionado com sucesso"
        return None, "Erro ao adicionar funcionário."

    def add_aso(self, aso_data: dict):
        new_data = [
            str(aso_data.get('funcionario_id')),
            aso_data.get('data_aso').strftime("%d/%m/%Y"),
            aso_data.get('vencimento').strftime("%d/%m/%Y") if aso_data.get('vencimento') else "N/A",
            str(aso_data.get('arquivo_id')),
            aso_data.get('riscos', 'N/A'),
            aso_data.get('cargo', 'N/A'),
            aso_data.get('tipo_aso', 'N/A')
        ]
        aso_id = self.sheet_ops.adc_dados_aba("asos", new_data)
        if aso_id:
            self.load_data()
        return aso_id

    def add_training(self, training_data: dict):
        new_data = [
            str(training_data.get('funcionario_id')),
            training_data.get('data').strftime("%d/%m/%Y"),
            training_data.get('vencimento').strftime("%d/%m/%Y"),
            self._padronizar_norma(training_data.get('norma')),
            str(training_data.get('modulo', 'N/A')),
            str(training_data.get('status', 'Válido')),
            str(training_data.get('anexo')),
            str(training_data.get('tipo_treinamento', 'N/A')),
            str(training_data.get('carga_horaria', '0'))
        ]
        training_id = self.sheet_ops.adc_dados_aba("treinamentos", new_data)
        if training_id:
            self.load_data()
        return training_id
    
    def _parse_flexible_date(self, date_string: str) -> date | None:
        if not date_string or not isinstance(date_string, str) or date_string.lower() == 'n/a': return None
        match = re.search(r'(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})|(\d{1,2} de \w+ de \d{4})|(\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2})', date_string, re.IGNORECASE)
        if not match: return None
        clean_date_string = match.group(0).replace('.', '/')
        formats = ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y', '%d de %B de %Y', '%Y-%m-%d']
        for fmt in formats:
            try: return datetime.strptime(clean_date_string, fmt).date()
            except ValueError: continue
        return None

    def _set_status(self, sheet_name: str, item_id: str, status: str):
        success = self.sheet_ops.update_row_by_id(sheet_name, item_id, {'status': status})
        if success:
            self.load_data()
        return success

    def archive_company(self, company_id: str): 
        return self._set_status("empresas", company_id, "Arquivado")

    def unarchive_company(self, company_id: str): 
        return self._set_status("empresas", company_id, "Ativo")

    def archive_employee(self, employee_id: str): 
        return self._set_status("funcionarios", employee_id, "Arquivado")

    def unarchive_employee(self, employee_id: str): 
        return self._set_status("funcionarios", employee_id, "Ativo")

    def get_latest_aso_by_employee(self, employee_id):
        """
        Retorna o ASO de aptidão (não demissional) mais recente para um funcionário.
        Retorna uma Series do Pandas se encontrado, ou None se não encontrado.
        """
        if self.aso_df.empty:
            return None
            
        asos_funcionario = self.aso_df[self.aso_df['funcionario_id'] == str(employee_id)].copy()
        if asos_funcionario.empty:
            return None

        if 'tipo_aso' not in asos_funcionario.columns:
            asos_funcionario['tipo_aso'] = 'N/A'
        asos_funcionario['tipo_aso'] = asos_funcionario['tipo_aso'].fillna('N/A')
        
        asos_aptidao = asos_funcionario[~asos_funcionario['tipo_aso'].str.lower().isin(['demissional'])].copy()
        if asos_aptidao.empty:
            return None

        asos_aptidao['data_aso_dt'] = pd.to_datetime(asos_aptidao['data_aso'], format='%d/%m/%Y', errors='coerce')
        asos_aptidao.dropna(subset=['data_aso_dt'], inplace=True)
        if asos_aptidao.empty:
            return None
            
        latest_aso_row = asos_aptidao.sort_values('data_aso_dt', ascending=False).iloc[0].copy()
        
        vencimento_str = latest_aso_row.get('vencimento')
        if vencimento_str and isinstance(vencimento_str, str):
            latest_aso_row['vencimento'] = pd.to_datetime(vencimento_str, format='%d/%m/%Y', errors='coerce').date()
        
        return latest_aso_row

    def get_all_trainings_by_employee(self, employee_id):
        if self.training_df.empty:
            return pd.DataFrame()
        training_docs = self.training_df[self.training_df['funcionario_id'] == str(employee_id)].copy()
        if training_docs.empty:
            return pd.DataFrame()
        
        for col in ['norma', 'modulo', 'tipo_treinamento']:
            if col not in training_docs.columns: 
                training_docs[col] = 'N/A'
            training_docs[col] = training_docs[col].fillna('N/A').astype(str).str.strip()
        
        training_docs['data_dt'] = pd.to_datetime(training_docs['data'], format='%d/%m/%Y', errors='coerce')
        training_docs.dropna(subset=['data_dt'], inplace=True)
        
        if training_docs.empty: return pd.DataFrame()
        latest_trainings = training_docs.sort_values('data_dt', ascending=False).groupby('norma').head(1).copy()
        latest_trainings['data'] = latest_trainings['data_dt'].dt.date
        
        latest_trainings['vencimento'] = pd.to_datetime(latest_trainings['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date

        return latest_trainings.drop(columns=['data_dt']).sort_values('data', ascending=False)

    def get_company_name(self, company_id):
        if self.companies_df.empty: 
            return f"ID {company_id}"
        company = self.companies_df[self.companies_df['id'] == str(company_id)]
        if not company.empty:
            return company.iloc[0]['nome']
        return f"ID {company_id}"

    def get_employee_name(self, employee_id):
        if self.employees_df.empty:
            return f"ID {employee_id}"
        employee = self.employees_df[self.employees_df['id'] == str(employee_id)]
        if not employee.empty:
            return employee.iloc[0]['nome']
        return f"ID {employee_id}"

    def get_employees_by_company(self, company_id: str, include_archived: bool = False):
        if self.employees_df.empty:
            return pd.DataFrame()
        company_employees = self.employees_df[self.employees_df['empresa_id'] == str(company_id)]
        if include_archived or 'status' not in company_employees.columns:
            return company_employees
        return company_employees[company_employees['status'].str.lower() == 'ativo']

    def _padronizar_norma(self, norma):
        if not norma: 
            return "N/A"
        norma_upper = str(norma).strip().upper()
        if any(term in norma_upper for term in ["BRIGADA", "INCÊNDIO", "IT-17", "NR-23"]): return "BRIGADA DE INCÊNDIO"
        if "16710" in norma_upper or "RESGATE TÉCNICO" in norma_upper: return "NBR-16710 RESGATE TÉCNICO"
        if "PERMISSÃO" in norma_upper or re.search(r'\bPT\b', norma_upper): return "PERMISSÃO DE TRABALHO (PT)"
        match = re.search(r'NR\s?-?(\d+)', norma_upper)
        if match: return f"NR-{int(match.group(1)):02d}"
        return norma_upper

    def calcular_vencimento_treinamento(self, data, norma, modulo=None, tipo_treinamento='formação'):
        if not isinstance(data, date): 
            return None
        norma_padronizada = self._padronizar_norma(norma)
        anos_validade = None
        if norma_padronizada == "NR-20" and modulo:
            config = self.nr20_config.get(modulo.strip().title())
            if config: anos_validade = config.get('reciclagem_anos')
        else:
            config = self.nr_config.get(norma_padronizada)
            if config: anos_validade = config.get('reciclagem_anos')
        
        if anos_validade:
            return data + relativedelta(years=int(anos_validade))
        
        st.warning(f"Regras de vencimento não encontradas para '{norma_padronizada}'. O vencimento não foi calculado.")
        return None

    def find_closest_function(self, cargo: str, score_cutoff: int = 80) -> str | None:
        if self.training_matrix_df.empty or 'funcao' not in self.training_matrix_df.columns: 
            return None
        available_functions = self.training_matrix_df['funcao'].dropna().unique().tolist()
        if not available_functions: 
            return None
        best_match = process.extractOne(cargo, available_functions, score_cutoff=score_cutoff)
        if best_match:
            return best_match[0]
        return None

    def get_required_trainings_for_function(self, function_name: str) -> list:
        if self.training_matrix_df.empty or not function_name: 
            return []
        row = self.training_matrix_df[self.training_matrix_df['funcao'] == function_name]
        if row.empty: 
            return []
        trainings_str = row.iloc[0].get('treinamentos_obrigatorios', '')
        if trainings_str and isinstance(trainings_str, str):
            return [training.strip() for training in trainings_str.split(',') if training.strip()]
        return []
