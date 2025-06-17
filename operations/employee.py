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
    pass

@st.cache_resource
def get_sheet_operations():
    return SheetOperations()

@st.cache_data(ttl=30)
def load_sheet_data(sheet_name):
    sheet_ops = get_sheet_operations()
    return sheet_ops.carregar_dados_aba(sheet_name)

class EmployeeManager:
    def _parse_flexible_date(self, date_string: str) -> date | None:
        if not date_string or date_string.lower() == 'n/a':
            return None
        match = re.search(r'(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})|(\d{1,2} de \w+ de \d{4})|(\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2})', date_string, re.IGNORECASE)
        if not match:
            return None
        clean_date_string = match.group(0).replace('.', '/')
        formats = ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y', '%d de %B de %Y', '%Y-%m-%d']
        for fmt in formats:
            try:
                return datetime.strptime(clean_date_string, fmt).date()
            except ValueError:
                continue
        return None

    def __init__(self):
        self.sheet_ops = get_sheet_operations()
        if not self.initialize_sheets():
            st.error("Erro ao inicializar as abas da planilha.")
        self.load_data()
        self._pdf_analyzer = None
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
                if not data:
                    self.sheet_ops.criar_aba(sheet_name, columns)
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
            if 'tipo_aso' not in aso_docs.columns:
                aso_docs['tipo_aso'] = 'Não Identificado'
            aso_docs['tipo_aso'] = aso_docs['tipo_aso'].fillna('Não Identificado')
            
            aso_docs['data_aso_dt'] = pd.to_datetime(aso_docs['data_aso'], format='%d/%m/%Y', errors='coerce')
            aso_docs.dropna(subset=['data_aso_dt'], inplace=True)
            latest_asos = aso_docs.sort_values('data_aso_dt', ascending=False).groupby('tipo_aso').head(1)
            latest_asos['data_aso'] = pd.to_datetime(latest_asos['data_aso'], format='%d/%m/%Y', errors='coerce').dt.date
            latest_asos['vencimento'] = pd.to_datetime(latest_asos['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
            latest_asos = latest_asos.drop(columns=['data_aso_dt'])
            return latest_asos.sort_values('data_aso', ascending=False)
        return pd.DataFrame()

    def get_all_trainings_by_employee(self, employee_id):
        if self.training_df.empty: return pd.DataFrame()
        training_docs = self.training_df[self.training_df['funcionario_id'] == str(employee_id)].copy()
        if training_docs.empty: return pd.DataFrame()
        if 'modulo' not in training_docs.columns:
            training_docs['modulo'] = 'N/A'
        training_docs['modulo'] = training_docs['modulo'].fillna('N/A')
        
        if 'norma' not in training_docs.columns: return pd.DataFrame()
        training_docs['data_dt'] = pd.to_datetime(training_docs['data'], format='%d/%m/%Y', errors='coerce')
        training_docs.dropna(subset=['data_dt'], inplace=True)
        latest_trainings = training_docs.sort_values('data_dt', ascending=False).groupby(['norma', 'modulo']).head(1)
        latest_trainings['data'] = pd.to_datetime(latest_trainings['data'], format='%d/%m/%Y', errors='coerce').dt.date
        latest_trainings['vencimento'] = pd.to_datetime(latest_trainings['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        latest_trainings = latest_trainings.drop(columns=['data_dt'])
        return latest_trainings.sort_values('data', ascending=False)

    def analyze_training_pdf(self, pdf_file):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue()); temp_path = temp_file.name
            combined_question = """
            Por favor, analise o documento e responda as seguintes perguntas, uma por linha:
            1. Qual é a norma regulamentadora (NR) deste treinamento? (ex: NR-10)
            2. Qual é o módulo do treinamento? (ex: Básico, ou 'Não se aplica')
            3. Qual é a data de realização do treinamento? (ex: 25/05/2024)
            4. Este documento é um certificado de reciclagem? (Responda 'sim' ou 'não')
            5. Qual é a carga horária total do treinamento em horas? (Responda apenas o número)
            """
            answer, _ = self.pdf_analyzer.answer_question([temp_path], combined_question); os.unlink(temp_path)
            if not answer: return None
            lines = answer.strip().split('\n'); results = {}
            for line in lines:
                match = re.match(r'\s*\*?\s*(\d+)\s*\.?\s*(.*)', line)
                if match: key = int(match.group(1)); value = match.group(2).strip(); results[key] = value
            data = self._parse_flexible_date(results.get(3, '')); norma = self._padronizar_norma(results.get(1))
            if not data or not norma: st.warning("Não foi possível extrair a data ou a norma do PDF."); return None
            carga_horaria_str = results.get(5, '0'); match_carga = re.search(r'\d+', carga_horaria_str); carga_horaria = int(match_carga.group(0)) if match_carga else 0
            modulo = results.get(2, "").strip(); tipo_treinamento = 'reciclagem' if 'sim' in results.get(4, '').lower() else 'formação'
            if norma == "NR-20" and (not modulo or modulo.lower() == 'não se aplica'):
                st.info("Módulo da NR-20 não encontrado, tentando inferir pela carga horária...")
                for mod, config in self.nr20_config.items():
                    key_ch = 'inicial_horas' if tipo_treinamento == 'formação' else 'reciclagem_horas'
                    if carga_horaria == config.get(key_ch):
                        modulo = mod; st.success(f"Módulo inferido como '{mod}' com base na carga horária de {carga_horaria}h."); break
            return {'data': data, 'norma': norma, 'modulo': modulo, 'tipo_treinamento': tipo_treinamento, 'carga_horaria': carga_horaria}
        except Exception as e:
            st.error(f"Erro ao analisar o PDF de treinamento: {str(e)}"); return None

    def analyze_aso_pdf(self, pdf_file):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name
            
            st.info("Iniciando análise geral do ASO...")
            general_prompt = """
            Por favor, analise o documento e responda as seguintes perguntas, uma por linha:
            1. Qual a data de emissão do ASO? (ex: 25/05/2024)
            2. Qual a data de vencimento do ASO? (Se não houver, responda 'N/A')
            3. Quais são os riscos ocupacionais?
            4. Qual o cargo do funcionário?
            5. Qual o tipo de exame médico? (ex: Admissional, Periódico, Demissional)
            """
            answer, _ = self.pdf_analyzer.answer_question([temp_path], general_prompt)
            
            if not answer: 
                os.unlink(temp_path)
                return None
            
            lines = answer.strip().split('\n')
            results = {}
            for line in lines:
                match = re.match(r'\s*\*?\s*(\d+)\s*\.?\s*(.*)', line)
                if match:
                    key = int(match.group(1))
                    value = match.group(2).strip()
                    results[key] = value

            data_aso = self._parse_flexible_date(results.get(1, ''))
            
            if data_aso is None:
                st.warning("Análise geral não encontrou a data. Tentando análise focada...")
                focused_prompt = "Qual é a data de realização ou emissão do exame clínico neste ASO? Ignore qualquer outra data ou campo de assinatura. Responda APENAS a data no formato DD/MM/AAAA."
                
                focused_answer, _ = self.pdf_analyzer.answer_question([temp_path], focused_prompt)
                
                if focused_answer:
                    data_aso = self._parse_flexible_date(focused_answer)

            # Se ainda assim falhar, desiste
            if not data_aso:
                st.error("Não foi possível extrair a data de realização, mesmo com a análise focada.")
                os.unlink(temp_path)
                return None
            
            # Continua o processamento com os resultados da primeira análise (ou data corrigida)
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
            
            os.unlink(temp_path)
            return {
                'data_aso': data_aso, 'vencimento': vencimento, 
                'riscos': results.get(3, ""), 'cargo': results.get(4, ""),
                'tipo_aso': tipo_aso
            }
        except Exception as e:
            st.error(f"Erro ao analisar o PDF do ASO: {str(e)}")
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
            return None

    def add_company(self, nome, cnpj):
        from gdrive.config import EMPLOYEE_SHEET_NAME
        if not self.companies_df.empty and cnpj in self.companies_df['cnpj'].values: return None, "CNPJ já cadastrado"
        new_data = [nome, cnpj]
        try:
            company_id = self.sheet_ops.adc_dados_aba(EMPLOYEE_SHEET_NAME, new_data)
            if company_id: st.cache_data.clear(); self.load_data(); return company_id, "Empresa cadastrada com sucesso"
            return None, "Falha ao obter ID da empresa."
        except Exception as e: return None, f"Erro ao cadastrar empresa: {str(e)}"
    
    def add_employee(self, nome, cargo, data_admissao, empresa_id):
        from gdrive.config import EMPLOYEE_DATA_SHEET_NAME
        new_data = [nome, empresa_id, cargo, data_admissao.strftime("%d/%m/%Y")]
        try:
            employee_id = self.sheet_ops.adc_dados_aba(EMPLOYEE_DATA_SHEET_NAME, new_data)
            if employee_id: st.cache_data.clear(); self.load_data(); return employee_id, "Funcionário adicionado com sucesso"
            return None, "Erro ao adicionar funcionário na planilha"
        except Exception as e: return None, f"Erro ao adicionar funcionário: {str(e)}"

    def add_aso(self, id, data_aso, vencimento, arquivo_id, riscos, cargo, tipo_aso="Não identificado"):
        from gdrive.config import ASO_SHEET_NAME
        if not all([id, data_aso, arquivo_id, cargo]): st.error("Dados essenciais para o ASO (ID, Data, Arquivo, Cargo) estão faltando."); return None
        vencimento_str = vencimento.strftime("%d/%m/%Y") if vencimento else "N/A"
        new_data = [str(id), data_aso.strftime("%d/%m/%Y"), vencimento_str, str(arquivo_id), str(riscos), str(cargo), str(tipo_aso)]
        try:
            aso_id = self.sheet_ops.adc_dados_aba(ASO_SHEET_NAME, new_data)
            if aso_id: st.cache_data.clear(); self.load_data(); return aso_id
            return None
        except Exception as e: st.error(f"Erro ao adicionar ASO: {str(e)}"); return None

    def _padronizar_norma(self, norma):
        if not norma: return None
        norma = str(norma).strip().upper().replace("NR ", "NR-")
        parts = norma.split('-')
        if len(parts) == 2 and parts[0] == "NR" and parts[1].isdigit() and len(parts[1]) == 1: return f"NR-0{parts[1]}"
        return norma

    def add_training(self, id, data, vencimento, norma, modulo, status, anexo, tipo_treinamento, carga_horaria):
        from gdrive.config import TRAINING_SHEET_NAME
        if not all([data, norma, vencimento]): st.error("Dados essenciais (data, norma, vencimento) para o treinamento estão faltando."); return None
        new_data = [str(id), data.strftime("%d/%m/%Y"), vencimento.strftime("%d/%m/%Y"), self._padronizar_norma(norma), str(modulo), str(status), str(anexo), str(tipo_treinamento), str(carga_horaria)]
        try:
            training_id = self.sheet_ops.adc_dados_aba(TRAINING_SHEET_NAME, new_data)
            if training_id: st.cache_data.clear(); self.load_data(); return training_id
            return None
        except Exception as e: st.error(f"Erro ao adicionar treinamento: {str(e)}"); return None

    def get_company_name(self, company_id):
        if self.companies_df.empty: return None
        company = self.companies_df[self.companies_df['id'] == str(company_id)]
        return company.iloc[0]['nome'] if not company.empty else None
    
    def get_employee_name(self, employee_id):
        if self.employees_df.empty: return None
        employee = self.employees_df[self.employees_df['id'] == str(employee_id)]
        return employee.iloc[0]['nome'] if not employee.empty else None
    
    def get_employees_by_company(self, company_id):
        if self.employees_df.empty or 'empresa_id' not in self.employees_df.columns: return pd.DataFrame()
        return self.employees_df[self.employees_df['empresa_id'] == str(company_id)]
    
    def get_employee_docs(self, employee_id):
        latest_aso = self.get_latest_aso_by_employee(employee_id)
        latest_trainings = self.get_all_trainings_by_employee(employee_id)
        return latest_aso, latest_trainings

    def calcular_vencimento_treinamento(self, data, norma, modulo=None, tipo_treinamento='formação'):
        if not isinstance(data, date): return None
        norma_padronizada = self._padronizar_norma(norma)
        if not norma_padronizada: return None
        
        modulo_normalizado = modulo.strip().capitalize() if modulo else None
        
        config = None
        if norma_padronizada == "NR-20":
            if modulo_normalizado:
                for key, value in self.nr20_config.items():
                    if key.lower() == modulo_normalizado.lower():
                        config = value
                        break
        else:
            config = self.nr_config.get(norma_padronizada)
        
        if config:
            anos_validade = config.get('reciclagem_anos', 1)
            return data + timedelta(days=anos_validade * 365)
        
        return None

    def validar_treinamento(self, norma, modulo, tipo_treinamento, carga_horaria):
        return True, ""
