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

# Inicializa o uploader do Google Drive globalmente
gdrive_uploader = GoogleDriveUploader()

# Cache para carregar dados das planilhas
@st.cache_data(ttl=30) 
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
            'NR-6': {
                'inicial_horas': 3,
                'reciclagem_horas': 3,
                'reciclagem_anos': 3
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
            'id', 'funcionario_id', 'data', 'vencimento', 'norma', 'modulo', 'status',
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
                    'id', 'funcionario_id', 'data', 'vencimento', 'norma', 'modulo', 'status',
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

            # Todas as perguntas em uma única string
            combined_question = """
            Por favor, analise o documento e responda as seguintes perguntas:
            1. Qual é a norma regulamentadora (NR) deste treinamento? Responda apenas o número da NR.
            2. Qual é o tipo específico do treinamento? apenas o número da NR.
            3. Qual é o módulo do treinamento? Se for NR-20, especifique se é Básico, Intermediário, Avançado I ou Avançado II.
            4. Qual é a data de realização do treinamento? Responda no formato DD/MM/AAAA.
            5. Este documento é um certificado de reciclagem? Responda apenas 'sim' ou 'não'. Se for 'sim', é reciclagem. Se for 'não', é treinamento inicial.
            6. Qual é a carga horária total do treinamento em horas? Responda apenas o número.
            
            Responda cada pergunta em uma nova linha, numerada de 1 a 6.
            """

            # Fazer uma única requisição com todas as perguntas
            answer, _ = self.pdf_analyzer.answer_question([temp_path], combined_question)
            
            # Limpar o arquivo temporário
            try:
                os.unlink(temp_path)
            except Exception as e:
                st.warning(f"Erro ao remover arquivo temporário: {str(e)}")

            # Processar as respostas
            if answer:
                # Dividir as respostas em linhas e extrair as informações
                lines = answer.strip().split('\n')
                results = {}
                for line in lines:
                    if line.strip():
                        try:
                            num, value = line.split('.', 1)
                            results[int(num)] = value.strip()
                        except:
                            continue

                try:
                    data = datetime.strptime(results[4], "%d/%m/%Y").date()
                except:
                    data = None

                norma = f"NR-{results[1]}" if results[1].isdigit() else results[1]
                modulo = results[3]
                
                # Processar o tipo de treinamento
                tipo_treinamento = results[5].lower()
                if 'sim' in tipo_treinamento:
                    tipo_treinamento = 'reciclagem'
                else:
                    tipo_treinamento = 'inicial'  # Assume inicial como padrão
                
                try:
                    carga_horaria = int(''.join(filter(str.isdigit, results[6])))
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
            return None

        except Exception as e:
            st.error(f"Erro ao analisar o PDF: {str(e)}")
            # Garantir que o arquivo temporário seja removido mesmo em caso de erro
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except:
                pass
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
                st.success(f"ASO adicionado com sucesso! ID: {aso_id}")
                return aso_id
            else:
                st.error("Erro ao adicionar ASO na planilha")
                return None
        except Exception as e:
            st.error(f"Erro ao adicionar ASO: {str(e)}")
            return None

    def _padronizar_norma(self, norma):
        """
        Padroniza o formato da norma (ex: NR-6 -> NR-06)
        """
        if norma is None:
            return None
            
        # Converte para string se não for
        norma = str(norma)
        
        # Remove espaços extras e converte para maiúsculas
        norma = ' '.join(norma.split()).upper()
        
        # Remove espaços antes e depois
        norma = norma.strip()
        
        # Adiciona zero se necessário (NR-6 -> NR-06)
        if norma.startswith("NR-") and len(norma) == 4:
            norma = norma.replace("NR-", "NR-0")
        # Se tiver espaço entre NR e o número (ex: "NR 6")
        elif norma.startswith("NR ") and len(norma) == 4:
            norma = norma.replace("NR ", "NR-0")
        # Se tiver espaço entre NR e o número (ex: "NR 06")
        elif norma.startswith("NR ") and len(norma) == 5:
            norma = norma.replace("NR ", "NR-")
            
        return norma

    def add_training(self, id, data, vencimento, norma, modulo, status, anexo,
                    tipo_treinamento, carga_horaria):
        """
        Adiciona um novo treinamento para um funcionário.
        """
        try:
            # Verifica se a norma foi fornecida
            if norma is None:
                st.error("A norma do treinamento é obrigatória")
                return None
                
            # Padroniza o formato da norma
            norma = self._padronizar_norma(norma)
            
            # Prepara os dados do novo treinamento
            new_data = [
                id,                    # funcionario_id
                data.strftime("%d/%m/%Y") if data else None,
                vencimento.strftime("%d/%m/%Y") if vencimento else None,
                norma,
                modulo,
                status,
                anexo,               # arquivo_id
                tipo_treinamento,
                carga_horaria
            ]
            
            # Adiciona o treinamento na planilha
            training_id = self.sheet_ops.adc_dados_aba(TRAINING_SHEET_NAME, new_data)
            if training_id:
                # Recarrega os dados após adicionar
                self.load_data()
                st.success(f"Treinamento adicionado com sucesso! ID: {training_id}")
                return training_id
            else:
                st.error("Erro ao adicionar treinamento na planilha")
                return None
        except Exception as e:
            st.error(f"Erro ao adicionar treinamento: {str(e)}")
            return None

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
        aso_docs = self.aso_df[self.aso_df['funcionario_id'] == employee_id]
        training_docs = self.training_df[self.training_df['funcionario_id'] == employee_id]
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
        try:
            # Salvar o arquivo temporariamente
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name

            # Todas as perguntas em uma única string
            combined_question = """
            Por favor, analise o documento e responda as seguintes perguntas:
            1. Qual é a data de realização do ASO? Responda apenas a data no formato DD/MM/AAAA.
            2. Qual é a data de vencimento do ASO? Responda apenas a data no formato DD/MM/AAAA.
            3. Quais são os riscos ocupacionais identificados? Liste apenas os riscos.
            4. Qual é o cargo do funcionário conforme consta no ASO? Responda apenas o cargo.
            
            Responda cada pergunta em uma nova linha, numerada de 1 a 4.
            """

            # Fazer uma única requisição com todas as perguntas
            answer, _ = self.pdf_analyzer.answer_question([temp_path], combined_question)
            
            # Limpar o arquivo temporário
            try:
                os.unlink(temp_path)
            except Exception as e:
                st.warning(f"Erro ao remover arquivo temporário: {str(e)}")

            # Processar as respostas
            if answer:
                # Dividir as respostas em linhas e extrair as informações
                lines = answer.strip().split('\n')
                results = {}
                for line in lines:
                    if line.strip():
                        try:
                            num, value = line.split('.', 1)
                            results[int(num)] = value.strip()
                        except:
                            continue

                try:
                    data_aso = datetime.strptime(results[1], "%d/%m/%Y").date()
                except:
                    data_aso = None

                try:
                    vencimento = datetime.strptime(results[2], "%d/%m/%Y").date()
                except:
                    vencimento = None

                # Se não encontrou a data de vencimento, calcula como 1 ano após a data do ASO
                if data_aso and not vencimento:
                    vencimento = data_aso + timedelta(days=365)

                return {
                    'data_aso': data_aso,
                    'vencimento': vencimento,
                    'riscos': results[3],
                    'cargo': results[4]
                }
            return None

        except Exception as e:
            st.error(f"Erro ao analisar o PDF do ASO: {str(e)}")
            # Garantir que o arquivo temporário seja removido mesmo em caso de erro
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except:
                pass
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













