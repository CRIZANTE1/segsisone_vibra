import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, date
from gdrive.gdrive_upload import GoogleDriveUploader
from AI.api_Operation import PDFQA
from operations.sheet import SheetOperations
import tempfile
import os
from gdrive.config import (
    ASO_SHEET_NAME,
    EMPLOYEE_SHEET_NAME,
    EMPLOYEE_DATA_SHEET_NAME,
    TRAINING_SHEET_NAME
)
import random

# Inicializa o uploader do Google Drive globalmente
gdrive_uploader = GoogleDriveUploader()

# Cache para carregar dados das planilhas
@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_sheet_data(sheet_name):
    sheet_ops = SheetOperations()
    return sheet_ops.carregar_dados_aba(sheet_name)

class EmployeeManager:
    def __init__(self):
        # Inicializa o gerenciador de planilhas e carrega os dados
        self.sheet_ops = SheetOperations()
        
        # Inicializa as abas se necessário
        if not self.initialize_sheets():
            st.error("Erro ao inicializar as abas da planilha. Algumas funcionalidades podem não funcionar corretamente.")
        
        # Carrega os dados
        self.load_data()
        
        # Inicializa o analisador de PDF apenas quando necessário
        self._pdf_analyzer = None
        
        # Configuração dos módulos da NR-20
        self.nr20_config = {
            'Básico': {
                'reciclagem_anos': 3,
                'reciclagem_horas': 4,
                'inicial_horas': 8
            },
            'Intermediário': {
                'reciclagem_anos': 2,
                'reciclagem_horas': 4,
                'inicial_horas': 16
            },
            'Avançado I': {
                'reciclagem_anos': 1,
                'reciclagem_horas': 4,
                'inicial_horas': 32
            },
            'Avançado II': {
                'reciclagem_anos': 1,
                'reciclagem_horas': 4,
                'inicial_horas': 40
            }
        }

        # Configuração das outras NRs
        self.nr_config = {
            'NR-35': {
                'inicial_horas': 8,
                'reciclagem_horas': 8,
                'reciclagem_anos': 2
            },
            'NR-10': {
                'inicial_horas': 40,
                'reciclagem_horas': 40,
                'reciclagem_anos': 2
            },
            'NR-18': {
                'inicial_horas': 8,
                'reciclagem_horas': 8,
                'reciclagem_anos': 1
            },
            'NR-12': {
                'inicial_horas': 8,
                'reciclagem_horas': 8,
                'reciclagem_anos': 2
            },
            'NR-34': {
                'inicial_horas': 8,
                'reciclagem_horas': 8,
                'reciclagem_anos': 1
            }
        }

    @property
    def pdf_analyzer(self):
        if self._pdf_analyzer is None:
            self._pdf_analyzer = PDFQA()
        return self._pdf_analyzer

    def load_data(self):
        # Carrega os dados das diferentes abas usando cache
        companies_data = load_sheet_data(EMPLOYEE_SHEET_NAME)
        employees_data = load_sheet_data(EMPLOYEE_DATA_SHEET_NAME)
        aso_data = load_sheet_data(ASO_SHEET_NAME)
        training_data = load_sheet_data(TRAINING_SHEET_NAME)
        
        # Define as colunas padrão para cada DataFrame
        company_columns = ['id', 'nome', 'cnpj']
        employee_columns = ['id', 'nome', 'empresa_id', 'cargo', 'data_admissao']
        aso_columns = ['id', 'funcionario_id', 'data_aso', 'vencimento', 'arquivo_id', 'riscos', 'cargo']
        training_columns = [
            'funcionario_id', 'data', 'vencimento', 'norma', 'modulo', 'status',
            'arquivo_id', 'tipo_treinamento', 'carga_horaria'
        ]
        
        # Converte os dados para DataFrames com as colunas corretas
        if companies_data and len(companies_data) > 0:
            self.companies_df = pd.DataFrame(companies_data[1:], columns=companies_data[0])
            # Garante que todas as colunas necessárias existam
            for col in company_columns:
                if col not in self.companies_df.columns:
                    self.companies_df[col] = ''
        else:
            self.companies_df = pd.DataFrame(columns=company_columns)
            
        if employees_data and len(employees_data) > 0:
            self.employees_df = pd.DataFrame(employees_data[1:], columns=employees_data[0])
            # Garante que todas as colunas necessárias existam
            for col in employee_columns:
                if col not in self.employees_df.columns:
                    self.employees_df[col] = ''
        else:
            self.employees_df = pd.DataFrame(columns=employee_columns)
            st.warning("Nenhum funcionário encontrado na planilha.")
            
        if aso_data and len(aso_data) > 0:
            self.aso_df = pd.DataFrame(aso_data[1:], columns=aso_data[0])
            # Garante que todas as colunas necessárias existam
            for col in aso_columns:
                if col not in self.aso_df.columns:
                    self.aso_df[col] = ''
        else:
            self.aso_df = pd.DataFrame(columns=aso_columns)
            
        if training_data and len(training_data) > 0:
            self.training_df = pd.DataFrame(training_data[1:], columns=training_data[0])
            # Garante que todas as colunas necessárias existam
            for col in training_columns:
                if col not in self.training_df.columns:
                    self.training_df[col] = ''
        else:
            self.training_df = pd.DataFrame(columns=training_columns)
            st.warning("Nenhum treinamento encontrado na planilha.")

    def initialize_sheets(self):
        """
        Inicializa as abas da planilha com as colunas corretas se elas não existirem.
        """
        try:
            # Define as colunas para cada aba
            sheets_structure = {
                EMPLOYEE_SHEET_NAME: ['id', 'nome', 'cnpj'],
                EMPLOYEE_DATA_SHEET_NAME: ['id', 'nome', 'empresa_id', 'cargo', 'data_admissao'],
                ASO_SHEET_NAME: ['id', 'funcionario_id', 'data_aso', 'vencimento', 'arquivo_id', 'riscos', 'cargo'],
                TRAINING_SHEET_NAME: [
                    'funcionario_id', 'data', 'vencimento', 'norma', 'modulo', 'status',
                    'arquivo_id', 'tipo_treinamento', 'carga_horaria'
                ]
            }
            
            # Inicializa cada aba
            for sheet_name, columns in sheets_structure.items():
                data = self.sheet_ops.carregar_dados_aba(sheet_name)
                if not data:
                    # Se a aba não existe, cria com as colunas corretas
                    self.sheet_ops.criar_aba(sheet_name, columns)
                    st.success(f"Aba {sheet_name} inicializada com sucesso!")
                else:
                    # Verifica se todas as colunas necessárias existem e se não há colunas extras
                    existing_columns = data[0] if data else []
                    missing_columns = [col for col in columns if col not in existing_columns]
                    extra_columns = [col for col in existing_columns if col and col not in columns]
                    
                    if missing_columns or extra_columns:
                        st.warning(f"Recriando a aba {sheet_name} para corrigir a estrutura...")
                        
                        # Backup dos dados existentes se houver
                        existing_data = []
                        if len(data) > 1:  # Se há dados além do cabeçalho
                            df = pd.DataFrame(data[1:], columns=existing_columns)
                            # Mantém apenas as colunas que existem na nova estrutura
                            common_columns = [col for col in columns if col in existing_columns]
                            if common_columns:
                                existing_data = df[common_columns].values.tolist()
                        
                        # Recria a aba com a estrutura correta
                        if self.sheet_ops.limpar_e_recriar_aba(sheet_name, columns):
                            # Restaura os dados se houver
                            if existing_data:
                                aba = self.sheet_ops.credentials.open_by_url(
                                    self.sheet_ops.my_archive_google_sheets
                                ).worksheet_by_title(sheet_name)
                                aba.append_table(existing_data)
                            st.success(f"Aba {sheet_name} recriada com sucesso!")
                        else:
                            st.error(f"Erro ao recriar a aba {sheet_name}")
            
            return True
        except Exception as e:
            st.error(f"Erro ao inicializar as abas: {str(e)}")
            return False

    def analyze_training_pdf(self, pdf_file):
        try:
            # Salvar o arquivo temporariamente
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name

            # Perguntas detalhadas para extrair informações do PDF
            questions = [
                "Qual é a norma regulamentadora (NR) deste treinamento? Procure por campos como 'NR', 'Norma Regulamentadora' ou similar. Responda apenas o número da NR.",
                "Qual é o tipo específico do treinamento? Procure por campos como 'Tipo', 'Modalidade' ou similar. Responda apenas o número da NR.",
                "Qual é o módulo do treinamento? Se for NR-20, especifique se é Básico, Intermediário, Avançado I ou Avançado II.",
                "Qual é a data de realização do treinamento? Procure por campos como 'Data do Curso', 'Data de Realização' ou similar. Responda apenas a data no formato DD/MM/AAAA.",
                "Este documento é um certificado de reciclagem? Procure por palavras como 'reciclagem', 'reciclagem' ou similar. Responda apenas 'sim' ou 'não'. Se for 'sim', é reciclagem. Se for 'não', é treinamento inicial.",
                "Qual é a carga horária total do treinamento em horas? Procure por campos como 'Carga Horária', 'Duração' ou similar. Responda apenas o número, sem texto adicional. Por exemplo, se for 8 horas, responda apenas '8'."
            ]

            results = {}
            for question in questions:
                answer, _ = self.pdf_analyzer.answer_question([temp_path], question)
                results[question] = answer.strip()

            # Limpar o arquivo temporário
            os.unlink(temp_path)

            # Processar as respostas
            try:
                data = datetime.strptime(results[questions[2]], "%d/%m/%Y").date()
            except:
                data = None

            norma = f"NR-{results[questions[0]]}" if results[questions[0]].isdigit() else results[questions[0]]
            modulo = results[questions[1]]
            
            # Processar o tipo de treinamento
            tipo_treinamento = results[questions[4]].lower()
            if 'sim' in tipo_treinamento:
                tipo_treinamento = 'reciclagem'
            else:
                tipo_treinamento = 'inicial'  # Assume inicial como padrão
            
            # Processar a carga horária
            try:
                # Remove qualquer texto não numérico e converte para inteiro
                carga_horaria_str = ''.join(filter(str.isdigit, results[questions[5]]))
                if carga_horaria_str:
                    carga_horaria = int(carga_horaria_str)
                else:
                    # Se não encontrou números, tenta extrair do texto
                    carga_horaria_text = results[questions[5]].lower()
                    if 'hora' in carga_horaria_text:
                        # Procura por números antes da palavra "hora"
                        import re
                        match = re.search(r'(\d+)\s*hora', carga_horaria_text)
                        if match:
                            carga_horaria = int(match.group(1))
                        else:
                            carga_horaria = None
                    else:
                        carga_horaria = None
            except:
                carga_horaria = None

            # Calcula o vencimento automaticamente
            vencimento = None
            if data:
                vencimento = self.calcular_vencimento_treinamento(data, norma, modulo, tipo_treinamento)

            return {
                'norma': norma,
                'modulo': modulo,
                'data': data,
                'vencimento': vencimento,
                'tipo_treinamento': tipo_treinamento,
                'carga_horaria': carga_horaria
            }
        except Exception as e:
            st.error(f"Erro ao analisar o PDF: {str(e)}")
            return None

    def add_company(self, nome, cnpj):
        # Verifica se o CNPJ já existe
        if not self.companies_df.empty and cnpj in self.companies_df['cnpj'].values:
            return None, "CNPJ já cadastrado"
        
        # Prepara os dados da nova empresa
        new_data = [nome, cnpj]
        
        try:
            # Adiciona a empresa na planilha
            self.sheet_ops.adc_dados_aba(EMPLOYEE_SHEET_NAME, new_data)
            # Recarrega os dados
            self.load_data()
            # Retorna o ID gerado
            return self.companies_df.iloc[-1]['id'], "Empresa cadastrada com sucesso"
        except Exception as e:
            return None, f"Erro ao cadastrar empresa: {str(e)}"
    
    def add_employee(self, nome, cargo, data_admissao, empresa_id):
        """
        Adiciona um novo funcionário.
        
        Args:
            nome: Nome do funcionário
            cargo: Cargo do funcionário
            data_admissao: Data de admissão (datetime.date)
            empresa_id: ID da empresa
            
        Returns:
            tuple: (employee_id, message) - ID do funcionário e mensagem de sucesso/erro
        """
        try:
            # Prepara os dados do novo funcionário na ordem correta da planilha
            new_data = [
                nome,  # nome
                empresa_id,  # empresa_id
                cargo,  # cargo
                data_admissao.strftime("%d/%m/%Y") if isinstance(data_admissao, (datetime, date)) else data_admissao  # data_admissao
            ]
            
            # Adiciona o funcionário na planilha usando a aba correta de funcionários
            employee_id = self.sheet_ops.adc_dados_aba(EMPLOYEE_DATA_SHEET_NAME, new_data)
            if employee_id:
                # Limpa o cache antes de recarregar os dados
                st.cache_data.clear()
                # Recarrega os dados após adicionar
                self.load_data()
                st.success(f"Funcionário adicionado com sucesso! ID: {employee_id}")
                return employee_id, "Funcionário adicionado com sucesso"
            else:
                st.error("Erro ao adicionar funcionário na planilha")
                return None, "Erro ao adicionar funcionário na planilha"
        except Exception as e:
            st.error(f"Erro ao adicionar funcionário: {str(e)}")
            return None, f"Erro ao adicionar funcionário: {str(e)}"
    
    def clear_fields(self):
        """
        Limpa os campos após adicionar um treinamento ou ASO.
        """
        if 'data_aso' in st.session_state:
            st.session_state.data_aso = None
        if 'vencimento_aso' in st.session_state:
            st.session_state.vencimento_aso = None
        if 'riscos' in st.session_state:
            st.session_state.riscos = ""
        if 'cargo_aso' in st.session_state:
            st.session_state.cargo_aso = ""
        if 'data_treinamento' in st.session_state:
            st.session_state.data_treinamento = None
        if 'vencimento_treinamento' in st.session_state:
            st.session_state.vencimento_treinamento = None
        if 'norma' in st.session_state:
            st.session_state.norma = ""
        if 'modulo' in st.session_state:
            st.session_state.modulo = ""
        if 'status' in st.session_state:
            st.session_state.status = ""
        if 'tipo_treinamento' in st.session_state:
            st.session_state.tipo_treinamento = ""
        if 'carga_horaria' in st.session_state:
            st.session_state.carga_horaria = None

    def add_aso(self, id, data_aso, vencimento, arquivo_id, riscos, cargo):
        """
        Adiciona um novo ASO para um funcionário.
        
        Args:
            id: ID do funcionário
            data_aso: Data do ASO
            vencimento: Data de vencimento
            arquivo_id: ID do arquivo no Google Drive
            riscos: Riscos ocupacionais
            cargo: Cargo conforme ASO
        """
        # Prepara os dados do novo ASO
        new_data = [
            id,
            data_aso.strftime("%d/%m/%Y"),
            vencimento.strftime("%d/%m/%Y"),
            arquivo_id,  # ID do arquivo no Google Drive
            riscos,
            cargo
        ]
        
        try:
            # Adiciona o ASO na planilha
            aso_id = self.sheet_ops.adc_dados_aba(ASO_SHEET_NAME, new_data)
            if aso_id:
                # Recarrega os dados após adicionar
                self.load_data()
                # Limpa os campos após adicionar com sucesso
                self.clear_fields()
                st.success(f"ASO adicionado com sucesso! ID: {aso_id}")
                return aso_id
            else:
                st.error("Erro ao adicionar ASO na planilha")
                return None
        except Exception as e:
            st.error(f"Erro ao adicionar ASO: {str(e)}")
            return None

    def add_training(self, employee_id, data, norma, modulo, tipo_treinamento, carga_horaria, arquivo_id=None):
        """
        Adiciona um treinamento para um funcionário.
        
        Args:
            employee_id: ID do funcionário
            data: Data do treinamento
            norma: Norma do treinamento
            modulo: Módulo do treinamento
            tipo_treinamento: Tipo do treinamento (inicial ou reciclagem)
            carga_horaria: Carga horária do treinamento
            arquivo_id: ID do arquivo no Google Drive (opcional)
            
        Returns:
            tuple: (id, message) - ID do treinamento e mensagem de sucesso/erro
        """
        try:
            # Validar o treinamento
            valido, mensagem = self.validar_treinamento(norma, modulo, tipo_treinamento, carga_horaria)
            if not valido:
                return None, mensagem

            # Calcular o vencimento
            vencimento = self.calcular_vencimento_treinamento(data, norma, modulo, tipo_treinamento)
            if not vencimento:
                return None, "Não foi possível calcular a data de vencimento do treinamento."

            # Preparar os dados
            training_data = [
                employee_id,
                data.strftime("%d/%m/%Y"),
                vencimento.strftime("%d/%m/%Y"),
                norma,
                modulo,
                "Válido" if vencimento > date.today() else "Vencido",
                arquivo_id if arquivo_id else "",
                tipo_treinamento,
                str(carga_horaria)
            ]

            # Adicionar à planilha
            if self.sheet_ops.adicionar_dados_aba(TRAINING_SHEET_NAME, training_data):
                # Atualizar o DataFrame local
                self.training_df = pd.concat([
                    self.training_df,
                    pd.DataFrame([training_data], columns=self.training_df.columns)
                ])
                return employee_id, "Treinamento adicionado com sucesso!"
            else:
                return None, "Erro ao adicionar treinamento na planilha."

        except Exception as e:
            st.error(f"Erro ao adicionar treinamento: {str(e)}")
            return None, f"Erro ao adicionar treinamento: {str(e)}"

    def get_company_name(self, company_id):
        company = self.companies_df[self.companies_df['id'] == company_id]
        if not company.empty:
            return company.iloc[0]['nome']
        return None
    
    def get_employee_name(self, employee_id):
        employee = self.employees_df[self.employees_df['id'] == employee_id]
        if not employee.empty:
            return employee.iloc[0]['nome']
        return None
    
    def get_employees_by_company(self, company_id):
        # Verifica se o DataFrame está vazio
        if self.employees_df.empty:
            return pd.DataFrame()
        
        # Verifica se a coluna existe
        if 'empresa_id' not in self.employees_df.columns:
            st.error("Erro: A coluna 'empresa_id' não foi encontrada nos dados dos funcionários.")
            return pd.DataFrame()
        
        return self.employees_df[self.employees_df['empresa_id'] == company_id]
    
    def get_employee_docs(self, employee_id):
        """
        Obtém os documentos (ASO e treinamentos) de um funcionário.
        
        Args:
            employee_id: ID do funcionário
            
        Returns:
            tuple: (aso_docs, training_docs) - DataFrames com os documentos
        """
        # Recarrega os dados antes de buscar os documentos
        self.load_data()
        
        # Filtra os documentos do funcionário
        aso_docs = self.aso_df[self.aso_df['funcionario_id'] == employee_id].copy()
        training_docs = self.training_df[self.training_df['funcionario_id'] == employee_id].copy()
        
        # Log para debug
        st.write(f"Treinamentos encontrados para o funcionário {employee_id}: {len(training_docs)} registros")
        
        return aso_docs, training_docs

    def calcular_vencimento_treinamento(self, data_realizacao, norma, modulo=None, tipo_treinamento='inicial'):
        """
        Calcula a data de vencimento do treinamento com base na norma.
        
        Args:
            data_realizacao (datetime.date): Data de realização do treinamento
            norma (str): Norma do treinamento (ex: NR-35, NR-10)
            modulo (str, optional): Módulo do treinamento (necessário para NR-20)
            tipo_treinamento (str): 'inicial' ou 'reciclagem'
            
        Returns:
            datetime.date: Data de vencimento do treinamento
        """
        if norma == "NR-20" and modulo in self.nr20_config:
            anos = self.nr20_config[modulo]['reciclagem_anos']
            return data_realizacao + timedelta(days=anos * 365)
        elif norma in self.nr_config:
            anos = self.nr_config[norma]['reciclagem_anos']
            return data_realizacao + timedelta(days=anos * 365)
            
        return None

    def verificar_carga_horaria(self, norma, modulo=None, tipo_treinamento='inicial'):
        """
        Verifica a carga horária mínima necessária para o treinamento.
        
        Args:
            norma (str): Norma do treinamento (ex: NR-35, NR-10)
            modulo (str, optional): Módulo do treinamento (necessário para NR-20)
            tipo_treinamento (str): 'inicial' ou 'reciclagem'
            
        Returns:
            int: Carga horária mínima em horas
        """
        if norma == "NR-20" and modulo in self.nr20_config:
            if tipo_treinamento == 'inicial':
                return self.nr20_config[modulo]['inicial_horas']
            else:  # reciclagem
                return self.nr20_config[modulo]['reciclagem_horas']
        elif norma in self.nr_config:
            if tipo_treinamento == 'inicial':
                return self.nr_config[norma]['inicial_horas']
            else:  # reciclagem
                return self.nr_config[norma]['reciclagem_horas']
            
        return None

    def validar_treinamento(self, norma, modulo, tipo_treinamento, carga_horaria):
        """
        Valida se a carga horária do treinamento está de acordo com os requisitos.
        
        Returns:
            tuple: (bool, str) - (válido, mensagem)
        """
        carga_minima = self.verificar_carga_horaria(norma, modulo, tipo_treinamento)
        if carga_minima and carga_horaria < carga_minima:
            return False, f"Carga horária insuficiente para {norma}. Mínimo necessário: {carga_minima} horas"
        return True, ""

    def analyze_aso_pdf(self, pdf_file):
        """
        Analisa um PDF de ASO para extrair informações relevantes.
        
        Args:
            pdf_file: Arquivo PDF do ASO
            
        Returns:
            dict: Dicionário com as informações extraídas do ASO
        """
        try:
            # Salvar o arquivo temporariamente
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name

            # Perguntas específicas para extrair informações do ASO
            questions = [
                "Qual é a data de realização do ASO? Responda apenas a data no formato DD/MM/AAAA.",
                "Qual é a data de vencimento do ASO? Responda apenas a data no formato DD/MM/AAAA.",
                "Quais são os riscos ocupacionais identificados? Liste apenas os riscos.",
                "Qual é o cargo do funcionário conforme consta no ASO? Responda apenas o cargo."
            ]

            results = {}
            for question in questions:
                answer, _ = self.pdf_analyzer.answer_question([temp_path], question)
                results[question] = answer.strip()

            # Limpar o arquivo temporário
            os.unlink(temp_path)

            # Processar as respostas
            try:
                data_aso = datetime.strptime(results[questions[0]], "%d/%m/%Y").date()
            except:
                data_aso = None

            try:
                vencimento = datetime.strptime(results[questions[1]], "%d/%m/%Y").date()
            except:
                vencimento = None

            # Se não encontrou a data de vencimento, calcula como 1 ano após a data do ASO
            if data_aso and not vencimento:
                vencimento = data_aso + timedelta(days=365)

            return {
                'data_aso': data_aso,
                'vencimento': vencimento,
                'riscos': results[questions[2]],
                'cargo': results[questions[3]]
            }

        except Exception as e:
            st.error(f"Erro ao analisar o PDF do ASO: {str(e)}")
            return None

    def get_document_by_id(self, aba_name, doc_id):
        """
        Recupera um documento (ASO ou treinamento) pelo ID.
        
        Args:
            aba_name: Nome da aba (LIFTING_SHEET_NAME ou CRANE_SHEET_NAME)
            doc_id: ID do documento
            
        Returns:
            dict: Dados do documento ou None se não encontrado
        """
        try:
            data = self.sheet_ops.carregar_dados_aba(aba_name)
            if not data:
                return None
                
            # Procura o documento pelo ID
            for row in data[1:]:  # Pula o cabeçalho
                if row[0] == str(doc_id):
                    if aba_name == ASO_SHEET_NAME:
                        return {
                            'id': row[0],
                            'funcionario_id': row[1],
                            'data_aso': row[2],
                            'vencimento': row[3],
                            'arquivo_id': row[4],
                            'riscos': row[5],
                            'cargo': row[6]
                        }
                    else:  # treinamentos
                        return {
                            'id': row[0],
                            'funcionario_id': row[1],
                            'data': row[2],
                            'vencimento': row[3],
                            'norma': row[4],
                            'modulo': row[5],
                            'status': row[6],
                            'arquivo_id': row[7],
                            'tipo_treinamento': row[8],
                            'carga_horaria': row[9]
                        }
            return None
        except Exception as e:
            st.error(f"Erro ao buscar documento: {str(e)}")
            return None





