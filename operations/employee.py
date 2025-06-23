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
import json  

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
            'NR-12': {'inicial_horas': 8, 'reciclagem_horas': 8, 'reciclagem_anos': 5},
            'NR-34': {'inicial_horas': 8, 'reciclagem_horas': 8, 'reciclagem_anos': 1},
            'NR-33': {'reciclagem_anos': 1},
            'BRIGADA DE INCÊNDIO': {'reciclagem_anos': 1}

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
        if self.aso_df.empty:
            return pd.DataFrame()
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
        if self.training_df.empty:
            return pd.DataFrame()
        training_docs = self.training_df[self.training_df['funcionario_id'] == str(employee_id)].copy()
        if training_docs.empty:
            return pd.DataFrame()
        if 'modulo' not in training_docs.columns:
            training_docs['modulo'] = 'N/A'
        training_docs['modulo'] = training_docs['modulo'].fillna('N/A')
        
        if 'norma' not in training_docs.columns:
            return pd.DataFrame()
        training_docs['data_dt'] = pd.to_datetime(training_docs['data'], format='%d/%m/%Y', errors='coerce')
        training_docs.dropna(subset=['data_dt'], inplace=True)
        latest_trainings = training_docs.sort_values('data_dt', ascending=False).groupby(['norma', 'modulo']).head(1)
        latest_trainings['data'] = pd.to_datetime(latest_trainings['data'], format='%d/%m/%Y', errors='coerce').dt.date
        latest_trainings['vencimento'] = pd.to_datetime(latest_trainings['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        latest_trainings = latest_trainings.drop(columns=['data_dt'])
        return latest_trainings.sort_values('data', ascending=False)

    def analyze_training_pdf(self, pdf_file):
        """
        Analisa um PDF de certificado de treinamento usando um prompt JSON estruturado para extrair informações.
        """
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
            "norma": "A norma regulamentadora do treinamento (ex: 'NR-20', 'Brigada de Incêndio', 'IT-17').",
            "modulo": "O módulo específico do treinamento (ex: 'Básico', 'Avançado', 'Supervisor'). Se não for aplicável, use 'N/A', Não considere 'Nivel' apenas o módulo ex se vier 'Intermediário Nível III' considere apenas 'Intermediário'.",
            "data_realizacao": "A data de conclusão ou emissão do certificado. Formato: DD/MM/AAAA.",
            "tipo_treinamento": "Identifique se é 'formação' (inicial) ou 'reciclagem' se não estiver descrito será 'formação'.",
            "carga_horaria": "A carga horária total do treinamento, apenas o número."
            }

            """
            answer, _ = self.pdf_analyzer.answer_question([temp_path], structured_prompt)

        except Exception as e:
            st.error(f"Erro ao processar o arquivo PDF de treinamento: {str(e)}")
            return None
        finally:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)

        if not answer:
            st.error("A IA não retornou nenhuma resposta para o certificado de treinamento.")
            return None

        try:
            cleaned_answer = answer.strip().replace("```json", "").replace("```", "")
            data = json.loads(cleaned_answer)

            data_realizacao = self._parse_flexible_date(data.get('data_realizacao'))
            norma_bruta = data.get('norma')
            
            if not data_realizacao or not norma_bruta:
                st.error("Não foi possível extrair a data de realização ou a norma do certificado a partir da resposta da IA.")
                st.code(f"Resposta recebida da IA:\n{answer}")
                return None
                
            norma_padronizada = self._padronizar_norma(norma_bruta)
            carga_horaria = int(data.get('carga_horaria', 0)) if data.get('carga_horaria') is not None else 0
            modulo = data.get('modulo', "N/A")
            tipo_treinamento = str(data.get('tipo_treinamento', 'formação')).lower()
            
            if norma_padronizada == "NR-20" and (not modulo or modulo.lower() == 'n/a'):
                st.info("Módulo da NR-20 não encontrado, tentando inferir pela carga horária...")
                key_ch = 'inicial_horas' if tipo_treinamento == 'formação' else 'reciclagem_horas'
                for mod, config in self.nr20_config.items():
                    if carga_horaria == config.get(key_ch):
                        modulo = mod
                        st.success(f"Módulo inferido como '{mod}' com base na carga horária de {carga_horaria}h.")
                        break
            
            return {
                'data': data_realizacao, 
                'norma': norma_padronizada, 
                'modulo': modulo, 
                'tipo_treinamento': tipo_treinamento, 
                'carga_horaria': carga_horaria
            }

        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as e:
            st.error(f"Erro ao processar a resposta da IA para o treinamento. A resposta pode não ser um JSON válido ou os dados estão incorretos: {e}")
            st.code(f"Resposta recebida da IA:\n{answer}")
            return None

    def analyze_aso_pdf(self, pdf_file):
        """
        Analisa um PDF de ASO usando um prompt JSON estruturado para extrair informações.
        """
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name
            
            st.info("Iniciando análise do ASO com prompt estruturado...")
            
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
        
        except Exception as e:
            st.error(f"Erro ao processar o arquivo PDF do ASO: {str(e)}")
            return None
        finally:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)

        if not answer:
            st.error("A IA não retornou nenhuma resposta para o ASO.")
            return None

        try:
            cleaned_answer = answer.strip().replace("```json", "").replace("```", "")
            data = json.loads(cleaned_answer)

            data_aso = self._parse_flexible_date(data.get('data_aso'))
            vencimento = self._parse_flexible_date(data.get('vencimento_aso'))
            
            if not data_aso:
                st.error("Não foi possível extrair a data de emissão do ASO a partir da resposta da IA.")
                st.code(f"Resposta recebida da IA:\n{answer}")
                return None
                
            tipo_aso = str(data.get('tipo_aso', 'Não identificado'))

            if not vencimento and tipo_aso != 'Demissional':
                st.info(f"Vencimento não encontrado explicitamente. Calculando com base no tipo '{tipo_aso}'...")
                if tipo_aso in ['Admissional', 'Periódico', 'Mudança de Risco', 'Retorno ao Trabalho']:
                    vencimento = data_aso + timedelta(days=365)
                elif tipo_aso == 'Monitoramento Pontual':
                    vencimento = data_aso + timedelta(days=180)
                else:
                    vencimento = data_aso + timedelta(days=365)
                    st.warning(f"Tipo de ASO '{tipo_aso}' não mapeado para cálculo de vencimento, assumindo validade de 1 ano.")
            
            return {
                'data_aso': data_aso, 
                'vencimento': vencimento, 
                'riscos': data.get('riscos', ""), 
                'cargo': data.get('cargo', ""),
                'tipo_aso': tipo_aso
            }

        except (json.JSONDecodeError, AttributeError) as e:
            st.error(f"Erro ao processar a resposta da IA para o ASO. A resposta não era um JSON válido: {e}")
            st.code(f"Resposta recebida da IA:\n{answer}")
            return None

    def add_company(self, nome, cnpj):
        from gdrive.config import EMPLOYEE_SHEET_NAME
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
        from gdrive.config import EMPLOYEE_DATA_SHEET_NAME
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

    def add_aso(self, id, data_aso, vencimento, arquivo_id, riscos, cargo, tipo_aso="Não identificado"):
        from gdrive.config import ASO_SHEET_NAME
        if not all([id, data_aso, arquivo_id, cargo]):
            st.error("Dados essenciais para o ASO (ID, Data, Arquivo, Cargo) estão faltando.")
            return None
        vencimento_str = vencimento.strftime("%d/%m/%Y") if vencimento else "N/A"
        new_data = [str(id), data_aso.strftime("%d/%m/%Y"), vencimento_str, str(arquivo_id), str(riscos), str(cargo), str(tipo_aso)]
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
        if not norma:
            return None
        
        norma_upper = str(norma).strip().upper()
    
        if "BRIGADA" in norma_upper or "INCÊNDIO" in norma_upper or "IT-17" in norma_upper or "IT 17" in norma_upper or "NR-23" in norma_upper or "NR 23" in norma_upper:
            return "BRIGADA DE INCÊNDIO"
            
        norma_padronizada = norma_upper.replace("NR ", "NR-")
        parts = norma_padronizada.split('-')
        if len(parts) == 2 and parts[0] == "NR" and parts[1].isdigit():
            num_str = parts[1]
            if len(num_str) == 1:
                return f"NR-0{num_str}"
            return norma_padronizada
            
        return norma_upper 

    def add_training(self, id, data, vencimento, norma, modulo, status, anexo, tipo_treinamento, carga_horaria):
        from gdrive.config import TRAINING_SHEET_NAME
        if not all([data, norma, vencimento]):
            st.error("Dados essenciais (data, norma, vencimento) para o treinamento estão faltando.")
            return None
        new_data = [str(id), data.strftime("%d/%m/%Y"), vencimento.strftime("%d/%m/%Y"), self._padronizar_norma(norma), str(modulo), str(status), str(anexo), str(tipo_treinamento), str(carga_horaria)]
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
        if self.companies_df.empty:
            return None
        company = self.companies_df[self.companies_df['id'] == str(company_id)]
        return company.iloc[0]['nome'] if not company.empty else None

    def get_employee_name(self, employee_id):
        if self.employees_df.empty:
            return None
        employee = self.employees_df[self.employees_df['id'] == str(employee_id)]
        return employee.iloc[0]['nome'] if not employee.empty else None

    def get_employees_by_company(self, company_id):
        if self.employees_df.empty or 'empresa_id' not in self.employees_df.columns:
            return pd.DataFrame()
        return self.employees_df[self.employees_df['empresa_id'] == str(company_id)]

    def get_employee_docs(self, employee_id):
        latest_aso = self.get_latest_aso_by_employee(employee_id)
        latest_trainings = self.get_all_trainings_by_employee(employee_id)
        return latest_aso, latest_trainings

    def calcular_vencimento_treinamento(self, data, norma, modulo=None, tipo_treinamento='formação'):
        if not isinstance(data, date):
            return None
        norma_padronizada = self._padronizar_norma(norma)
        if not norma_padronizada:
            return None
        
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
        norma_padronizada = self._padronizar_norma(norma)
        
        # Lógica para NR-33
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
                    
        elif norma_padronizada == "BRIGADA DE INCÊNDIO":
            # Considera qualquer menção a "avançado" no módulo
            is_avancado = "avançado" in str(modulo).lower()
            
            if is_avancado:
                if tipo_treinamento == 'formação' and carga_horaria < 24:
                    return False, f"Carga horária para formação de Brigada Avançada deve ser de 24h, mas foi de {carga_horaria}h."
                elif tipo_treinamento == 'reciclagem' and carga_horaria < 16:
                    return False, f"Carga horária para reciclagem de Brigada Avançada deve ser de 16h, mas foi de {carga_horaria}h."
            # Você pode adicionar lógica para outros níveis (básico, intermediário) aqui se precisar
            # else:
            #     # Lógica para Básico/Intermediário
            #     pass

        return True, "Carga horária conforme."
