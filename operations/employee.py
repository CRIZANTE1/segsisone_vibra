import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, date
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

# Import the new cached loaders
from operations.cached_loaders import (
    load_companies_df,
    load_employees_df,
    load_asos_df,
    load_trainings_df,
    load_training_matrix_df
)

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    pass

logger = logging.getLogger('segsisone_app.employee_manager')

class EmployeeManager:
    def __init__(self, spreadsheet_id: str, folder_id: str):
        logger.info(f"Inicializando EmployeeManager para spreadsheet_id: ...{spreadsheet_id[-6:]}")
        self.spreadsheet_id = spreadsheet_id
        self.folder_id = folder_id
        self._pdf_analyzer = None
        
        # Load data using cached functions
        self.companies_df = load_companies_df(spreadsheet_id)
        self.employees_df = load_employees_df(spreadsheet_id)
        self.aso_df = load_asos_df(spreadsheet_id)
        self.training_df = load_trainings_df(spreadsheet_id)
        self.training_matrix_df = load_training_matrix_df(spreadsheet_id)

        # Static configs (can be class attributes or global constants if not tenant-specific)
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

    @property
    def pdf_analyzer(self):
        if self._pdf_analyzer is None: self._pdf_analyzer = PDFQA()
        return self._pdf_analyzer

    

    def log_action(self, action: str, details: dict):
        try:
            user_email = get_user_email()
            user_role = st.session_state.get('role', 'N/A')
            target_uo = st.session_state.get('unit_name', 'N/A')
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_data = [timestamp, user_email, user_role, action, json.dumps(details), target_uo]
            logger.info(f"Ação registrada: {action}, Detalhes: {details}")
            # A lógica de escrita do log deve ser gerenciada separadamente, se necessário.
        except Exception as e:
            logger.error(f"Erro ao registrar ação: {e}", exc_info=True)

    def upload_documento_e_obter_link(self, arquivo, novo_nome):
        api_manager = GoogleApiManager()
        if not self.folder_id:
            st.error("O ID da pasta desta unidade não está definido. Não é possível fazer o upload.")
            logger.error("Tentativa de upload sem folder_id definido para a unidade.")
            return None
        logger.info(f"Iniciando upload do documento: {novo_nome}")
        return api_manager.upload_file(self.folder_id, arquivo, novo_nome)

    def add_company(self, nome, cnpj):
        if not self.companies_df.empty and cnpj in self.companies_df['cnpj'].values:
            logger.warning(f"Tentativa de adicionar empresa com CNPJ duplicado: {cnpj}")
            return None, "CNPJ já cadastrado."
        new_data = [nome, cnpj, "Ativo"]
        sheet_ops = SheetOperations(self.spreadsheet_id)
        company_id = sheet_ops.adc_dados_aba("empresas", new_data)
        if company_id:
            self.log_action("add_company", {"company_id": company_id, "nome": nome})
            load_companies_df.clear() # Clear cache after addition
            return company_id, "Empresa cadastrada com sucesso"
        logger.error(f"Falha ao adicionar empresa {nome} ({cnpj}).")
        return None, "Falha ao obter ID da empresa."

    def add_employee(self, nome, cargo, data_admissao, empresa_id):
        new_data = [nome, str(empresa_id), cargo, data_admissao.strftime("%d/%m/%Y"), "Ativo"]
        sheet_ops = SheetOperations(self.spreadsheet_id)
        employee_id = sheet_ops.adc_dados_aba("funcionarios", new_data)
        if employee_id:
            self.log_action("add_employee", {"employee_id": employee_id, "nome": nome})
            load_employees_df.clear() # Clear cache after addition
            return employee_id, "Funcionário adicionado com sucesso"
        logger.error(f"Falha ao adicionar funcionário {nome} para a empresa {empresa_id}.")
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
        sheet_ops = SheetOperations(self.spreadsheet_id)
        aso_id = sheet_ops.adc_dados_aba("asos", new_data)
        if aso_id:
            self.log_action("add_aso", {"aso_id": aso_id, "funcionario_id": aso_data.get('funcionario_id')})
            load_asos_df.clear() # Clear cache after addition
        else:
            logger.error(f"Falha ao adicionar ASO para o funcionário {aso_data.get('funcionario_id')}.")
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
        sheet_ops = SheetOperations(self.spreadsheet_id)
        training_id = sheet_ops.adc_dados_aba("treinamentos", new_data)
        if training_id:
            self.log_action("add_training", {"training_id": training_id, "norma": training_data.get('norma')})
            load_trainings_df.clear() # Clear cache after addition
        else:
            logger.error(f"Falha ao adicionar treinamento para o funcionário {training_data.get('funcionario_id')}.")
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
        sheet_ops = SheetOperations(self.spreadsheet_id)
        success = sheet_ops.update_row_by_id(sheet_name, item_id, {'status': status})
        if success:
            self.log_action("set_status", {"item_id": item_id, "sheet": sheet_name, "status": status})
            if sheet_name == "empresas":
                load_companies_df.clear()
            elif sheet_name == "funcionarios":
                load_employees_df.clear()
        else:
            logger.error(f"Falha ao definir status '{status}' para {item_id} na aba {sheet_name}.")
        return success

    def archive_company(self, company_id: str): 
        logger.info(f"Arquivando empresa com ID: {company_id}")
        return self._set_status("empresas", company_id, "Arquivado")

    def unarchive_company(self, company_id: str): 
        logger.info(f"Desarquivando empresa com ID: {company_id}")
        return self._set_status("empresas", company_id, "Ativo")

    def archive_employee(self, employee_id: str): 
        logger.info(f"Arquivando funcionário com ID: {employee_id}")
        return self._set_status("funcionarios", employee_id, "Arquivado")

    def unarchive_employee(self, employee_id: str): 
        logger.info(f"Desarquivando funcionário com ID: {employee_id}")
        return self._set_status("funcionarios", employee_id, "Ativo")

    def get_latest_aso_by_employee(self, employee_id):
        if self.aso_df.empty:
            logger.debug(f"aso_df está vazio para o funcionário {employee_id}. Retornando DataFrame vazio.")
            return pd.DataFrame()
        aso_docs = self.aso_df[self.aso_df['funcionario_id'] == str(employee_id)].copy()
        if aso_docs.empty:
            logger.debug(f"Nenhum ASO encontrado para o funcionário {employee_id}. Retornando DataFrame vazio.")
            return pd.DataFrame()
        if 'tipo_aso' not in aso_docs.columns: 
            logger.warning("Coluna 'tipo_aso' não encontrada em aso_docs. Adicionando como 'N/A'.")
            aso_docs['tipo_aso'] = 'N/A'
        aso_docs['tipo_aso'] = aso_docs['tipo_aso'].fillna('N/A').astype(str).str.strip()
        
        # Converter data_aso com tratamento de erro
        aso_docs['data_aso_dt'] = pd.to_datetime(aso_docs['data_aso'], format='%d/%m/%Y', errors='coerce')
        if aso_docs['data_aso_dt'].isnull().any():
            logger.warning(f"ASOs para o funcionário {employee_id} contêm datas inválidas na coluna 'data_aso'.")
        aso_docs.dropna(subset=['data_aso_dt'], inplace=True)
        
        if aso_docs.empty: return pd.DataFrame()
        latest_asos = aso_docs.sort_values('data_aso_dt', ascending=False).groupby('tipo_aso').head(1).copy()
        latest_asos['data_aso'] = latest_asos['data_aso_dt'].dt.date
        
        # Converter vencimento com tratamento de erro
        latest_asos['vencimento'] = pd.to_datetime(latest_asos['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        if latest_asos['vencimento'].isnull().any():
            logger.warning(f"ASOs para o funcionário {employee_id} contêm datas inválidas na coluna 'vencimento'.")

        logger.debug(f"ASOs mais recentes para o funcionário {employee_id} processados com sucesso.")
        return latest_asos.drop(columns=['data_aso_dt']).sort_values('data_aso', ascending=False)

    def get_all_trainings_by_employee(self, employee_id):
        if self.training_df.empty:
            logger.debug(f"training_df está vazio para o funcionário {employee_id}. Retornando DataFrame vazio.")
            return pd.DataFrame()
        training_docs = self.training_df[self.training_df['funcionario_id'] == str(employee_id)].copy()
        if training_docs.empty:
            logger.debug(f"Nenhum treinamento encontrado para o funcionário {employee_id}. Retornando DataFrame vazio.")
            return pd.DataFrame()
        
        for col in ['norma', 'modulo', 'tipo_treinamento']:
            if col not in training_docs.columns: 
                logger.warning(f"Coluna '{col}' não encontrada em training_docs. Adicionando como 'N/A'.")
                training_docs[col] = 'N/A'
            training_docs[col] = training_docs[col].fillna('N/A').astype(str).str.strip()
        
        # Converter data com tratamento de erro
        training_docs['data_dt'] = pd.to_datetime(training_docs['data'], format='%d/%m/%Y', errors='coerce')
        if training_docs['data_dt'].isnull().any():
            logger.warning(f"Treinamentos para o funcionário {employee_id} contêm datas inválidas na coluna 'data'.")
        training_docs.dropna(subset=['data_dt'], inplace=True)
        
        if training_docs.empty: return pd.DataFrame()
        latest_trainings = training_docs.sort_values('data_dt', ascending=False).groupby('norma').head(1).copy()
        latest_trainings['data'] = latest_trainings['data_dt'].dt.date
        
        # Converter vencimento com tratamento de erro
        latest_trainings['vencimento'] = pd.to_datetime(latest_trainings['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        if latest_trainings['vencimento'].isnull().any():
            logger.warning(f"Treinamentos para o funcionário {employee_id} contêm datas inválidas na coluna 'vencimento'.")

        logger.debug(f"Treinamentos mais recentes para o funcionário {employee_id} processados com sucesso.")
        return latest_trainings.drop(columns=['data_dt']).sort_values('data', ascending=False)

    def get_company_name(self, company_id):
        if self.companies_df.empty: 
            logger.debug(f"companies_df está vazio. Não foi possível obter o nome da empresa para ID {company_id}.")
            return f"ID {company_id}"
        company = self.companies_df[self.companies_df['id'] == str(company_id)]
        if not company.empty:
            return company.iloc[0]['nome']
        logger.debug(f"Empresa com ID {company_id} não encontrada em companies_df.")
        return f"ID {company_id}"

    def get_employee_name(self, employee_id):
        if self.employees_df.empty:
            logger.debug(f"employees_df está vazio. Não foi possível obter o nome do funcionário para ID {employee_id}.")
            return f"ID {employee_id}"
        employee = self.employees_df[self.employees_df['id'] == str(employee_id)]
        if not employee.empty:
            return employee.iloc[0]['nome']
        logger.debug(f"Funcionário com ID {employee_id} não encontrado em employees_df.")
        return f"ID {employee_id}"

    def get_employees_by_company(self, company_id: str, include_archived: bool = False):
        if self.employees_df.empty:
            logger.debug(f"employees_df está vazio. Retornando DataFrame vazio para a empresa {company_id}.")
            return pd.DataFrame()
        company_employees = self.employees_df[self.employees_df['empresa_id'] == str(company_id)]
        if include_archived or 'status' not in company_employees.columns:
            return company_employees
        return company_employees[company_employees['status'].str.lower() == 'ativo']

    def _padronizar_norma(self, norma):
        if not norma: 
            logger.debug("Norma vazia recebida para padronização. Retornando 'N/A'.")
            return "N/A"
        norma_upper = str(norma).strip().upper()
        if any(term in norma_upper for term in ["BRIGADA", "INCÊNDIO", "IT-17", "NR-23"]): return "BRIGADA DE INCÊNDIO"
        if "16710" in norma_upper or "RESGATE TÉCNICO" in norma_upper: return "NBR-16710 RESGATE TÉCNICO"
        if "PERMISSÃO" in norma_upper or re.search(r'\bPT\b', norma_upper): return "PERMISSÃO DE TRABALHO (PT)"
        match = re.search(r'NR\s?-?(\d+)', norma_upper)
        if match: return f"NR-{int(match.group(1)):02d}"
        logger.debug(f"Norma '{norma_upper}' não padronizada. Retornando original.")
        return norma_upper

    def calcular_vencimento_treinamento(self, data, norma, modulo=None, tipo_treinamento='formação'):
        if not isinstance(data, date): 
            logger.warning(f"Data inválida '{data}' recebida para calcular vencimento. Retornando None.")
            return None
        norma_padronizada = self._padronizar_norma(norma)
        anos_validade = None
        if norma_padronizada == "NR-20" and modulo:
            config = self.nr20_config.get(modulo.strip().title())
            if config: anos_validade = config.get('reciclagem_anos')
            logger.debug(f"NR-20: Norma '{norma_padronizada}', Módulo '{modulo}', Anos validade: {anos_validade}")
        else:
            config = self.nr_config.get(norma_padronizada)
            if config: anos_validade = config.get('reciclagem_anos')
            logger.debug(f"Outra NR: Norma '{norma_padronizada}', Anos validade: {anos_validade}")
        
        if anos_validade:
            vencimento = data + relativedelta(years=int(anos_validade))
            logger.info(f"Vencimento calculado para '{norma_padronizada}': {vencimento.strftime('%d/%m/%Y')}")
            return vencimento
        
        st.warning(f"Regras de vencimento não encontradas para '{norma_padronizada}'. O vencimento não foi calculado.")
        logger.warning(f"Regras de vencimento não encontradas para '{norma_padronizada}'. Retornando None.")
        return None

    def find_closest_function(self, cargo: str, score_cutoff: int = 80) -> str | None:
        if self.training_matrix_df.empty or 'funcao' not in self.training_matrix_df.columns: 
            logger.debug("Matriz de treinamentos vazia ou sem coluna 'funcao'. Não é possível encontrar função correspondente.")
            return None
        available_functions = self.training_matrix_df['funcao'].dropna().unique().tolist()
        if not available_functions: 
            logger.debug("Nenhuma função disponível na matriz de treinamentos.")
            return None
        best_match = process.extractOne(cargo, available_functions, score_cutoff=score_cutoff)
        if best_match:
            logger.debug(f"Função mais próxima para '{cargo}': {best_match[0]} (Score: {best_match[1]})")
            return best_match[0]
        logger.debug(f"Nenhuma função correspondente encontrada para '{cargo}' com score acima de {score_cutoff}.")
        return None

    def get_required_trainings_for_function(self, function_name: str) -> list:
        if self.training_matrix_df.empty or not function_name: 
            logger.debug(f"Matriz de treinamentos vazia ou função '{function_name}' inválida. Retornando lista vazia.")
            return []
        row = self.training_matrix_df[self.training_matrix_df['funcao'] == function_name]
        if row.empty: 
            logger.debug(f"Nenhuma linha encontrada na matriz de treinamentos para a função '{function_name}'.")
            return []
        trainings_str = row.iloc[0].get('treinamentos_obrigatorios', '')
        if trainings_str and isinstance(trainings_str, str):
            trainings = [training.strip() for training in trainings_str.split(',') if training.strip()]
            logger.debug(f"Treinamentos obrigatórios para '{function_name}': {trainings}")
            return trainings
        logger.debug(f"String de treinamentos obrigatórios vazia ou inválida para a função '{function_name}'.")
        return []
