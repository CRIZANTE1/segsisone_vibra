import pandas as pd
import streamlit as st
from datetime import datetime, date, timedelta
from gdrive.google_api_manager import GoogleApiManager
from AI.api_Operation import PDFQA
from operations.sheet import SheetOperations
import tempfile
import os
import re
import locale
import json
from dateutil.relativedelta import relativedelta
from operations.audit_logger import log_action
from auth.auth_utils import get_user_email
from fuzzywuzzy import process
import logging

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    pass

logger = logging.getLogger('segsisone_app.employee_manager')

class EmployeeManager:
    def __init__(self, spreadsheet_id: str, folder_id: str):
        logger.info(f"Inicializando EmployeeManager para spreadsheet_id: ...{spreadsheet_id[-6:]}")
        self.sheet_ops = SheetOperations(spreadsheet_id)
        self.folder_id = folder_id
        self.api_manager = GoogleApiManager()
        self._pdf_analyzer = None
        self.data_loaded_successfully = False
        
        self.nr20_config = {
            'Básico': {'reciclagem_anos': 3, 'reciclagem_horas': 4, 'inicial_horas': 8},
            'Intermediário': {'reciclagem_anos': 2, 'reciclagem_horas': 4, 'inicial_horas': 16},
            'Avançado I': {'reciclagem_anos': 2, 'reciclagem_horas': 4, 'inicial_horas': 20},
            'Avançado II': {'reciclagem_anos': 1, 'reciclagem_horas': 4, 'inicial_horas': 32}
        }
        self.nr_config = {
            'NR-35': {'inicial_horas': 8, 'reciclagem_horas': 8, 'reciclagem_anos': 2},
            'NR-10': {'inicial_horas': 40, 'reciclagem_horas': 40, 'reciclagem_anos': 2},
            'NR-18': {'inicial_horas': 8, 'reciclagem_horas': 8, 'reciclagem_anos': 1},
            'NR-06': {'inicial_horas': 3, 'reciclagem_horas': 3, 'reciclagem_anos': 10},
            'NR-12': {'inicial_horas': 8, 'reciclagem_horas': 8, 'reciclagem_anos': 5},
            'NR-34': {'inicial_horas': 8, 'reciclagem_horas': 8, 'reciclagem_anos': 1},
            'NR-33': {'reciclagem_anos': 1},
            'BRIGADA DE INCÊNDIO': {'reciclagem_anos': 1},
            'NR-11': {'reciclagem_anos': 3, 'reciclagem_horas': 16},
            'NBR-16710 RESGATE TÉCNICO': {'reciclagem_anos': 1},
            'PERMISSÃO DE TRABALHO (PT)': {'reciclagem_anos': 1}
        }
        
        self.load_data()

    @property
    def pdf_analyzer(self):
        if self._pdf_analyzer is None: self._pdf_analyzer = PDFQA()
        return self._pdf_analyzer

    def upload_documento_e_obter_link(self, arquivo, novo_nome: str):
        """
        Faz o upload de um arquivo para a pasta da unidade e retorna o link.
        Esta função atua como um wrapper para o GoogleApiManager.
        """
        if not self.folder_id:
            st.error("O ID da pasta desta unidade não está definido. Não é possível fazer o upload.")
            logger.error(f"Tentativa de upload para a unidade, mas o folder_id não foi fornecido no construtor do EmployeeManager.")
            return None
        
        # A instância self.api_manager já foi criada no __init__
        logger.info(f"Iniciando upload do documento '{novo_nome}' para a pasta ID: ...{self.folder_id[-6:]}")
        return self.api_manager.upload_file(self.folder_id, arquivo, novo_nome)


    def load_data(self):
        """
        Carrega todos os DataFrames da planilha da unidade e centraliza o tratamento
        de tipos de dados, especialmente as colunas de data.
        """
        logger.info(f"Carregando dados para spreadsheet_id: ...{self.sheet_ops.spreadsheet.id[-6:] if self.sheet_ops.spreadsheet else 'N/A'}")
        
        try:
            # Define as colunas esperadas para cada aba, garantindo a criação de DFs vazios corretos
            company_cols = ['id', 'nome', 'cnpj', 'status']
            employee_cols = ['id', 'nome', 'empresa_id', 'cargo', 'data_admissao', 'status']
            aso_cols = ['id', 'funcionario_id', 'data_aso', 'vencimento', 'arquivo_id', 'riscos', 'cargo', 'tipo_aso']
            training_cols = ['id', 'funcionario_id', 'data', 'vencimento', 'norma', 'modulo', 'status', 'anexo', 'tipo_treinamento', 'carga_horaria']

            # Carrega os dados brutos de cada aba
            companies_data = self.sheet_ops.carregar_dados_aba("empresas")
            self.companies_df = pd.DataFrame(companies_data[1:], columns=companies_data[0]) if companies_data and len(companies_data) > 1 else pd.DataFrame(columns=company_cols)

            employees_data = self.sheet_ops.carregar_dados_aba("funcionarios")
            self.employees_df = pd.DataFrame(employees_data[1:], columns=employees_data[0]) if employees_data and len(employees_data) > 1 else pd.DataFrame(columns=employee_cols)

            aso_data = self.sheet_ops.carregar_dados_aba("asos")
            self.aso_df = pd.DataFrame(aso_data[1:], columns=aso_data[0]) if aso_data and len(aso_data) > 1 else pd.DataFrame(columns=aso_cols)

            training_data = self.sheet_ops.carregar_dados_aba("treinamentos")
            self.training_df = pd.DataFrame(training_data[1:], columns=training_data[0]) if training_data and len(training_data) > 1 else pd.DataFrame(columns=training_cols)
            
            # --- TRATAMENTO CENTRALIZADO DE DATAS ---
            # Converte as colunas de data para o tipo datetime do Pandas.
            # 'errors=coerce' transforma qualquer valor que não possa ser convertido em NaT (Not a Time).
            
            if not self.aso_df.empty:
                self.aso_df['data_aso'] = pd.to_datetime(self.aso_df['data_aso'], format='%d/%m/%Y', errors='coerce')
                self.aso_df['vencimento'] = pd.to_datetime(self.aso_df['vencimento'], format='%d/%m/%Y', errors='coerce')

            if not self.training_df.empty:
                self.training_df['data'] = pd.to_datetime(self.training_df['data'], format='%d/%m/%Y', errors='coerce')
                self.training_df['vencimento'] = pd.to_datetime(self.training_df['vencimento'], format='%d/%m/%Y', errors='coerce')
            
            if not self.employees_df.empty:
                self.employees_df['data_admissao'] = pd.to_datetime(self.employees_df['data_admissao'], format='%d/%m/%Y', errors='coerce')

            self.data_loaded_successfully = True
            logger.info("DataFrames da unidade carregados e datas tratadas com sucesso.")
            
        except Exception as e:
            logger.error(f"FALHA CRÍTICA ao carregar e tratar dados da unidade: {e}", exc_info=True)
            st.error(f"Erro crítico ao carregar dados da unidade: {e}")
            # Garante que os DFs sejam zerados em caso de erro
            self.companies_df = pd.DataFrame(columns=company_cols)
            self.employees_df = pd.DataFrame(columns=employee_cols)
            self.aso_df = pd.DataFrame(columns=aso_cols)
            self.training_df = pd.DataFrame(columns=training_cols)
            self.data_loaded_successfully = False

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

    def analyze_aso_pdf(self, pdf_file):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name
            
            structured_prompt = """        
            Você é um assistente de extração de dados para documentos de Saúde e Segurança do Trabalho. Sua tarefa é analisar o ASO em PDF e extrair as informações abaixo.
            REGRAS OBRIGATÓRIAS:
            1.Responda APENAS com um bloco de código JSON válido. Não inclua a palavra "json" ou qualquer outro texto antes ou depois do bloco JSON.
            2.Para todas as chaves de data, use ESTRITAMENTE o formato DD/MM/AAAA.
            3.Se uma informação não for encontrada de forma clara e inequívoca, o valor da chave correspondente no JSON deve ser null (sem aspas).
            4.IMPORTANTE: Os valores das chaves no JSON NÃO DEVEM conter o nome da chave.
            ERRADO: "cargo": "Cargo: Operador"
            CORRETO: "cargo": "Operador"
            JSON a ser preenchido:

            {
            "data_aso": "A data de emissão ou realização do exame clínico. Formato: DD/MM/AAAA.",
            "vencimento_aso": "A data de vencimento explícita no ASO, se houver. Formato: DD/MM/AAAA.",
            "riscos": "Uma string contendo os riscos ocupacionais listados, separados por vírgula.",
            "cargo": "O cargo ou função do trabalhador.",
            "tipo_aso": "O tipo de exame. Identifique como um dos seguintes: 'Admissional', 'Periódico', 'Demissional', 'Mudança de Risco', 'Retorno ao Trabalho', 'Monitoramento Pontual'."
            }

            """
            answer, _ = self.pdf_analyzer.answer_question([temp_path], structured_prompt)
            os.unlink(temp_path)
            if not answer: return None

            cleaned_answer = answer.strip().replace("```json", "").replace("```", "")
            data = json.loads(cleaned_answer)
            data_aso = self._parse_flexible_date(data.get('data_aso'))
            vencimento = self._parse_flexible_date(data.get('vencimento_aso'))
            if not data_aso: return None
                
            tipo_aso = str(data.get('tipo_aso', 'Não identificado'))
            if not vencimento and tipo_aso != 'Demissional':
                if tipo_aso in ['Admissional', 'Periódico', 'Mudança de Risco', 'Retorno ao Trabalho']:
                    vencimento = data_aso + relativedelta(years=1)
                elif tipo_aso == 'Monitoramento Pontual':
                    vencimento = data_aso + relativedelta(months=6)
            
            return {'data_aso': data_aso, 'vencimento': vencimento, 'riscos': data.get('riscos', ""), 'cargo': data.get('cargo', ""), 'tipo_aso': tipo_aso}
        except Exception as e:
            st.error(f"Erro ao analisar PDF do ASO: {e}")
            return None

    def analyze_training_pdf(self, pdf_file):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name
            
            structured_prompt = """
            Você é um especialista em análise de documentos de Saúde e Segurança do Trabalho. Sua tarefa é analisar o certificado de treinamento em PDF e extrair as informações abaixo.

            **REGRAS OBRIGATÓRIAS:**
            1.  Responda **APENAS com um bloco de código JSON válido**. Não inclua a palavra "json" ou qualquer outro texto antes ou depois do bloco JSON.
            2.  Para a chave de data, use ESTRITAMENTE o formato **DD/MM/AAAA**.
            3.  Se uma informação não for encontrada de forma clara, o valor da chave correspondente no JSON deve ser **null** (sem aspas).
            4.  Para a chave "norma", retorne o nome padronizado (ex: 'NR-10', 'NR-35').
            5.  Para a chave "carga_horaria", retorne apenas o número inteiro de horas.
            6.  **IMPORTANTE:** Os valores das chaves no JSON **NÃO DEVEM** conter o nome da chave.
                -   **ERRADO:** `"norma": "Norma: NR-35"`
                -   **CORRETO:** `"norma": "NR-35"`

            **JSON a ser preenchido:**
            ```json
            {
            "norma": "A norma regulamentadora do treinamento (ex: 'NR-20', 'NBR 16710' 'Brigada de Incêndio', 'IT-17','NR-11', 'NR-35', Permissão de Trabalho).",
            "modulo": "O módulo específico do treinamento (ex: 'Emitente', 'Requisitante', 'Resgate Técnico Industrial', 'Operador de Empilhadeira', 'Munck', 'Guindauto','Básico', 'Avançado', 'Supervisor'). Se não for aplicável, use 'N/A', Não considere 'Nivel' apenas o módulo ex se vier 'Intermediário Nível III' considere apenas 'Intermediário'.",
            "data_realizacao": "A data de conclusão ou emissão do certificado. Formato: DD/MM/AAAA.",
            "tipo_treinamento": "Identifique se é 'formação' (inicial) ou 'reciclagem' se não estiver descrito será 'formação'.",
            "carga_horaria": "A carga horária total do treinamento, apenas o número."
            }

            """
            answer, _ = self.pdf_analyzer.answer_question([temp_path], structured_prompt)
            os.unlink(temp_path)
            if not answer: return None

            cleaned_answer = answer.strip().replace("```json", "").replace("```", "")
            data = json.loads(cleaned_answer)
            data_realizacao = self._parse_flexible_date(data.get('data_realizacao'))
            if not data_realizacao: return None
                
            norma_padronizada = self._padronizar_norma(data.get('norma'))
            carga_horaria = int(data.get('carga_horaria', 0)) if data.get('carga_horaria') is not None else 0
            modulo = data.get('modulo', "N/A")
            tipo_treinamento = str(data.get('tipo_treinamento', 'formação')).lower()
            
            if norma_padronizada == "NR-20" and (not modulo or modulo.lower() == 'n/a'):
                key_ch = 'inicial_horas' if tipo_treinamento == 'formação' else 'reciclagem_horas'
                for mod, config in self.nr20_config.items():
                    if carga_horaria == config.get(key_ch):
                        modulo = mod
                        break
            
            return {'data': data_realizacao, 'norma': norma_padronizada, 'modulo': modulo, 'tipo_treinamento': tipo_treinamento, 'carga_horaria': carga_horaria}
        except Exception as e:
            st.error(f"Erro ao analisar PDF do Treinamento: {e}")
            return None

    def add_company(self, nome, cnpj):
        if not self.companies_df.empty and cnpj in self.companies_df['cnpj'].values:
            return None, "CNPJ já cadastrado."
        new_data = [nome, cnpj, "Ativo"]
        company_id = self.sheet_ops.adc_dados_aba("empresas", new_data)
        if company_id:
            self.load_data()
            return company_id, "Empresa cadastrada com sucesso"
        return None, "Falha ao obter ID da empresa."

    def add_employee(self, nome, cargo, data_admissao, empresa_id):
        new_data = [nome, str(empresa_id), cargo, data_admissao.strftime("%d/%m/%Y"), "Ativo"]
        employee_id = self.sheet_ops.adc_dados_aba("funcionarios", new_data)
        if employee_id:
            self.load_data()
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
        if aso_id: self.load_data()
        return aso_id

    def add_training(self, training_data: dict):
        new_data = [
            str(training_data.get('funcionario_id')),
            training_data.get('data').strftime("%d/%m/%Y"),
            training_data.get('vencimento').strftime("%d/%m/%Y"),
            self._padronizar_norma(training_data.get('norma')),
            str(training_data.get('modulo', 'N/A')),
            "Válido",
            str(training_data.get('anexo')),
            str(training_data.get('tipo_treinamento', 'N/A')),
            str(training_data.get('carga_horaria', '0'))
        ]
        training_id = self.sheet_ops.adc_dados_aba("treinamentos", new_data)
        if training_id: self.load_data()
        return training_id

    def _set_status(self, sheet_name: str, item_id: str, status: str):
        if self.sheet_ops.update_row_by_id(sheet_name, item_id, {'status': status}):
            self.load_data()
            return True
        return False

    def archive_company(self, company_id: str): return self._set_status("empresas", company_id, "Arquivado")
    def unarchive_company(self, company_id: str): return self._set_status("empresas", company_id, "Ativo")
    def archive_employee(self, employee_id: str): return self._set_status("funcionarios", employee_id, "Arquivado")
    def unarchive_employee(self, employee_id: str): return self._set_status("funcionarios", employee_id, "Ativo")

    def get_latest_aso_by_employee(self, employee_id):
        if self.aso_df.empty or 'funcionario_id' not in self.aso_df.columns: return pd.DataFrame()
        aso_docs = self.aso_df[self.aso_df['funcionario_id'] == str(employee_id)].copy()
        if aso_docs.empty: return pd.DataFrame()
        
        aso_docs['data_aso'] = pd.to_datetime(aso_docs['data_aso'], format='%d/%m/%Y', errors='coerce')
        aso_docs['vencimento'] = pd.to_datetime(aso_docs['vencimento'], format='%d/%m/%Y', errors='coerce')
        aso_docs.dropna(subset=['data_aso'], inplace=True)
        if aso_docs.empty: return pd.DataFrame()

        aso_docs['tipo_aso'] = aso_docs['tipo_aso'].fillna('N/A')
        return aso_docs.sort_values('data_aso', ascending=False).groupby('tipo_aso').head(1)

    def get_all_trainings_by_employee(self, employee_id):
        if self.training_df.empty or 'funcionario_id' not in self.training_df.columns: return pd.DataFrame()
        training_docs = self.training_df[self.training_df['funcionario_id'] == str(employee_id)].copy()
        if training_docs.empty: return pd.DataFrame()
        
        training_docs.dropna(subset=['data'], inplace=True)
        if training_docs.empty: return pd.DataFrame()

        for col in ['norma', 'modulo', 'tipo_treinamento']:
            if col not in training_docs.columns: training_docs[col] = 'N/A'
            training_docs[col] = training_docs[col].fillna('N/A')
        
        return training_docs.sort_values('data', ascending=False).groupby('norma').head(1)
        
        return latest_trainings

    def get_company_name(self, company_id):
        if self.companies_df.empty: return f"ID {company_id}"
        company = self.companies_df[self.companies_df['id'] == str(company_id)]
        return company.iloc[0]['nome'] if not company.empty else f"ID {company_id}"

    def get_employee_name(self, employee_id):
        if self.employees_df.empty: return f"ID {employee_id}"
        employee = self.employees_df[self.employees_df['id'] == str(employee_id)]
        return employee.iloc[0]['nome'] if not employee.empty else f"ID {employee_id}"

    def get_employees_by_company(self, company_id: str, include_archived: bool = False):
        if self.employees_df.empty or 'empresa_id' not in self.employees_df.columns: return pd.DataFrame()
        company_employees = self.employees_df[self.employees_df['empresa_id'] == str(company_id)]
        if include_archived or 'status' not in company_employees.columns: return company_employees
        return company_employees[company_employees['status'].str.lower() == 'ativo']

    def _padronizar_norma(self, norma):
        if not norma: return "N/A"
        norma_upper = str(norma).strip().upper()
        if any(term in norma_upper for term in ["BRIGADA", "INCÊNDIO", "IT-17", "NR-23"]): return "BRIGADA DE INCÊNDIO"
        if "16710" in norma_upper or "RESGATE TÉCNICO" in norma_upper: return "NBR-16710 RESGATE TÉCNICO"
        if "PERMISSÃO" in norma_upper or re.search(r'\bPT\b', norma_upper): return "PERMISSÃO DE TRABALHO (PT)"
        match = re.search(r'NR\s?-?(\d+)', norma_upper)
        if match: return f"NR-{int(match.group(1)):02d}"
        return norma_upper

    def calcular_vencimento_treinamento(self, data, norma, modulo=None, tipo_treinamento='formação'):
        if not isinstance(data, (date, datetime)): return None
        norma_padronizada = self._padronizar_norma(norma)
        anos_validade = None
        if norma_padronizada == "NR-20" and modulo:
            config = self.nr20_config.get(modulo.strip().title())
            if config: anos_validade = config.get('reciclagem_anos')
        else:
            config = self.nr_config.get(norma_padronizada)
            if config: anos_validade = config.get('reciclagem_anos')
        
        if anos_validade is not None:
            return data + relativedelta(years=int(anos_validade))
        st.warning(f"Regras de vencimento não encontradas para '{norma_padronizada}'.")
        return None

    def delete_aso(self, aso_id: str, file_url: str):
        """
        Deleta permanentemente um registro de ASO e seu arquivo, e registra a ação.
        """
        # Coleta informações para o log ANTES de deletar
        aso_info = self.aso_df[self.aso_df['id'] == aso_id]
        if not aso_info.empty:
            details = {
                "deleted_item_id": aso_id,
                "item_type": "ASO",
                "employee_id": aso_info.iloc[0].get('funcionario_id'),
                "aso_type": aso_info.iloc[0].get('tipo_aso'),
                "aso_date": str(aso_info.iloc[0].get('data_aso')),
                "file_url": file_url
            }
            log_action("DELETE_ASO", details)

        # Continua com a lógica de exclusão
        if file_url and pd.notna(file_url):
            self.api_manager.delete_file_by_url(file_url)
        
        if self.sheet_ops.excluir_dados_aba("asos", aso_id):
            self.load_data()
            return True
        return False

    def delete_training(self, training_id: str, file_url: str):
        """
        Deleta permanentemente um registro de treinamento e seu arquivo, e registra a ação.
        """
        # Coleta informações para o log ANTES de deletar
        training_info = self.training_df[self.training_df['id'] == training_id]
        if not training_info.empty:
            details = {
                "deleted_item_id": training_id,
                "item_type": "Treinamento",
                "employee_id": training_info.iloc[0].get('funcionario_id'),
                "norma": training_info.iloc[0].get('norma'),
                "training_date": str(training_info.iloc[0].get('data')),
                "file_url": file_url
            }
            log_action("DELETE_TRAINING", details)

        # Continua com a lógica de exclusão
        if file_url and pd.notna(file_url):
            self.api_manager.delete_file_by_url(file_url)

        if self.sheet_ops.excluir_dados_aba("treinamentos", training_id):
            self.load_data()
            return True
        return False

    def validar_treinamento(self, norma, modulo, tipo_treinamento, carga_horaria):
        """
        Valida a carga horária de um treinamento com base na norma, módulo e tipo.
        Retorna (True, "Mensagem de sucesso") ou (False, "Mensagem de erro").
        """
        norma_padronizada = self._padronizar_norma(norma)
        tipo_treinamento = str(tipo_treinamento).lower() # Garante que seja minúsculo

        # --- Lógica para NRs com regras simples (do dicionário nr_config) ---
        if norma_padronizada in self.nr_config:
            config = self.nr_config[norma_padronizada]
            
            # Verifica a carga horária de formação (inicial)
            if tipo_treinamento == 'formação' and 'inicial_horas' in config:
                if carga_horaria < config['inicial_horas']:
                    return False, f"Carga horária para formação ({norma_padronizada}) deve ser de {config['inicial_horas']}h, mas foi de {carga_horaria}h."
            
            # Verifica a carga horária de reciclagem
            elif tipo_treinamento == 'reciclagem' and 'reciclagem_horas' in config:
                if carga_horaria < config['reciclagem_horas']:
                    return False, f"Carga horária para reciclagem ({norma_padronizada}) deve ser de {config['reciclagem_horas']}h, mas foi de {carga_horaria}h."

        # --- Lógicas Específicas e Complexas ---

        # Lógica para NR-33 (Espaços Confinados)
        if norma_padronizada == "NR-33":
            modulo_normalizado = ""
            if modulo:
                if "supervisor" in modulo.lower():
                    modulo_normalizado = "supervisor"
                elif "trabalhador" in modulo.lower() or "autorizado" in modulo.lower():
                    modulo_normalizado = "trabalhador"
            
            if tipo_treinamento == 'formação':
                if modulo_normalizado == "supervisor" and carga_horaria < 40:
                    return False, f"Carga horária para formação de Supervisor (NR-33) deve ser de 40h, mas foi de {carga_horaria}h."
                if modulo_normalizado == "trabalhador" and carga_horaria < 16:
                    return False, f"Carga horária para formação de Trabalhador Autorizado (NR-33) deve ser de 16h, mas foi de {carga_horaria}h."
            
            elif tipo_treinamento == 'reciclagem':
                if carga_horaria < 8:
                    return False, f"Carga horária para reciclagem (NR-33) deve ser de 8h, mas foi de {carga_horaria}h."
        
        # Lógica para Permissão de Trabalho (PT)
        elif norma_padronizada == "PERMISSÃO DE TRABALHO (PT)":
            modulo_lower = str(modulo).lower()
            if "emitente" in modulo_lower:
                if tipo_treinamento == 'formação' and carga_horaria < 16:
                    return False, f"Carga horária para formação de Emitente de PT deve ser de 16h, mas foi de {carga_horaria}h."
                elif tipo_treinamento == 'reciclagem' and carga_horaria < 4:
                    return False, f"Carga horária para reciclagem de Emitente de PT deve ser de 4h, mas foi de {carga_horaria}h."
            elif "requisitante" in modulo_lower:
                if tipo_treinamento == 'formação' and carga_horaria < 8:
                    return False, f"Carga horária para formação de Requisitante de PT deve ser de 8h, mas foi de {carga_horaria}h."
                elif tipo_treinamento == 'reciclagem' and carga_horaria < 4:
                    return False, f"Carga horária para reciclagem de Requisitante de PT deve ser de 4h, mas foi de {carga_horaria}h."
          
        # Lógica para Brigada de Incêndio
        elif norma_padronizada == "BRIGADA DE INCÊNDIO":
            is_avancado = "avançado" in str(modulo).lower()
            if is_avancado:
                if tipo_treinamento == 'formação' and carga_horaria < 24:
                    return False, f"Carga horária para formação de Brigada Avançada deve ser de 24h, mas foi de {carga_horaria}h."
                elif tipo_treinamento == 'reciclagem' and carga_horaria < 16:
                    return False, f"Carga horária para reciclagem de Brigada Avançada deve ser de 16h, mas foi de {carga_horaria}h."

        # Lógica para NR-11 (Movimentação de Cargas)
        elif norma_padronizada == "NR-11":
            if tipo_treinamento == 'formação' and carga_horaria < 16:
                return False, f"Carga horária para formação (NR-11) parece baixa ({carga_horaria}h). O mínimo comum é 16h."
            elif tipo_treinamento == 'reciclagem' and carga_horaria < 16:
                 return False, f"Carga horária para reciclagem (NR-11) deve ser de 16h, mas foi de {carga_horaria}h."
        
        # Lógica para NBR 16710 (Resgate Técnico)
        elif norma_padronizada == "NBR-16710 RESGATE TÉCNICO":
            is_industrial_rescue = "industrial" in str(modulo).lower()
            if is_industrial_rescue:
                if tipo_treinamento == 'formação' and carga_horaria < 24:
                    return False, f"Carga horária para formação de Resgate Técnico Industrial (NBR 16710) deve ser de no mínimo 24h, mas foi de {carga_horaria}h."
                elif tipo_treinamento == 'reciclagem' and carga_horaria < 24:
                    return False, f"Carga horária para reciclagem de Resgate Técnico Industrial (NBR 16710) deve ser de no mínimo 24h, mas foi de {carga_horaria}h."
        
        # Se nenhuma das condições de falha for atendida, o treinamento é considerado conforme.
        return True, "Carga horária conforme."
