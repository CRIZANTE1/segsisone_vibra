import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from gdrive.gdrive_upload import GoogleDriveUploader
from AI.api_Operation import PDFQA
from operations.sheet import SheetOperations
import tempfile
import os
from gdrive.config import LIFTING_SHEET_NAME, CRANE_SHEET_NAME, EMPLOYEE_SHEET_NAME

# Inicializa o uploader do Google Drive globalmente
gdrive_uploader = GoogleDriveUploader()

class EmployeeManager:
    def __init__(self):
        # Inicializa o gerenciador de planilhas e carrega os dados
        self.sheet_ops = SheetOperations()
        self.load_data()
        self.pdf_analyzer = PDFQA()
        
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
            'NR-34': {
                'inicial_horas': 8,
                'reciclagem_horas': 8,
                'reciclagem_anos': 1
            }
        }

    def load_data(self):
        # Carrega os dados das diferentes abas
        companies_data = self.sheet_ops.carregar_dados_aba(EMPLOYEE_SHEET_NAME)
        employees_data = self.sheet_ops.carregar_dados_aba('funcionarios')
        aso_data = self.sheet_ops.carregar_dados_aba(LIFTING_SHEET_NAME)
        training_data = self.sheet_ops.carregar_dados_aba(CRANE_SHEET_NAME)
        
        # Converte os dados para DataFrames
        if companies_data:
            self.companies_df = pd.DataFrame(companies_data[1:], columns=companies_data[0])
        else:
            self.companies_df = pd.DataFrame(columns=['id', 'nome', 'cnpj'])
            
        if employees_data:
            self.employees_df = pd.DataFrame(employees_data[1:], columns=employees_data[0])
        else:
            self.employees_df = pd.DataFrame(columns=['id', 'nome', 'empresa_id', 'cargo', 'data_admissao'])
            
        if aso_data:
            self.aso_df = pd.DataFrame(aso_data[1:], columns=aso_data[0])
        else:
            self.aso_df = pd.DataFrame(columns=['id', 'data_aso', 'vencimento', 'aso', 'riscos', 'cargo', 'autorizacoes'])
            
        if training_data:
            self.training_df = pd.DataFrame(training_data[1:], columns=training_data[0])
        else:
            self.training_df = pd.DataFrame(columns=['id', 'contratado', 'data', 'vencimento', 'norma', 'modulo', 'status', 'anexo', 'tipo_treinamento', 'carga_horaria'])

    def analyze_training_pdf(self, pdf_file):
        try:
            # Salvar o arquivo temporariamente
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name

            # Perguntas detalhadas para extrair informações do PDF
            questions = [
                "Qual é a norma regulamentadora (NR) deste treinamento? Responda apenas o número da NR.",
                "Qual é o módulo ou tipo específico do treinamento? Se for NR-20, especifique se é Básico, Intermediário, Avançado I ou Avançado II.",
                "Qual é a data de realização do treinamento? Responda no formato DD/MM/AAAA.",
                "Este é um treinamento inicial ou uma reciclagem? Responda apenas 'inicial' ou 'reciclagem'.",
                "Qual é a carga horária total do treinamento em horas? Responda apenas o número.",
                "Qual é o nome do instrutor?",
                "Qual é o registro do instrutor?",
                "Qual é o CNPJ da empresa que ministrou o treinamento?",
                "Quais foram os tópicos abordados no treinamento?",
                "Há alguma observação importante no certificado?"
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
            tipo_treinamento = results[questions[3].lower()]
            try:
                carga_horaria = int(''.join(filter(str.isdigit, results[questions[4]])))
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
                'carga_horaria': carga_horaria,
                'instrutor': results[questions[5]],
                'registro_instrutor': results[questions[6]],
                'cnpj_empresa': results[questions[7]],
                'topicos': results[questions[8]],
                'observacoes': results[questions[9]]
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
    
    def add_employee(self, nome, empresa_id, cargo, data_admissao):
        # Verifica se a empresa existe
        if empresa_id not in self.companies_df['id'].values:
            return None, "Empresa não encontrada"
        
        # Prepara os dados do novo funcionário
        new_data = [nome, empresa_id, cargo, data_admissao.strftime("%d/%m/%Y")]
        
        try:
            # Adiciona o funcionário na planilha
            self.sheet_ops.adc_dados_aba('funcionarios', new_data)
            # Recarrega os dados
            self.load_data()
            # Retorna o ID gerado
            return self.employees_df.iloc[-1]['id'], "Funcionário cadastrado com sucesso"
        except Exception as e:
            return None, f"Erro ao cadastrar funcionário: {str(e)}"
    
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
            aso_id = self.sheet_ops.adc_dados_aba(LIFTING_SHEET_NAME, new_data)
            if aso_id:
                st.success(f"ASO adicionado com sucesso! ID: {aso_id}")
                return aso_id
            else:
                st.error("Erro ao adicionar ASO na planilha")
                return None
        except Exception as e:
            st.error(f"Erro ao adicionar ASO: {str(e)}")
            return None

    def add_training(self, id, contratado, data, vencimento, norma, modulo, status, anexo,
                    tipo_treinamento, carga_horaria, instrutor, registro_instrutor,
                    cnpj_empresa, topicos, observacoes):
        """
        Adiciona um novo treinamento para um funcionário.
        """
        # Prepara os dados do novo treinamento
        new_data = [
            id,
            contratado,
            data.strftime("%d/%m/%Y") if isinstance(data, datetime) else data,
            vencimento.strftime("%d/%m/%Y") if isinstance(vencimento, datetime) else vencimento,
            norma,
            modulo,
            status,
            anexo,  # ID do arquivo no Google Drive
            tipo_treinamento,
            carga_horaria,
            instrutor,
            registro_instrutor,
            cnpj_empresa,
            topicos,
            observacoes
        ]
        
        try:
            # Adiciona o treinamento na planilha
            training_id = self.sheet_ops.adc_dados_aba(CRANE_SHEET_NAME, new_data)
            if training_id:
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
        return self.employees_df[self.employees_df['empresa_id'] == company_id]
    
    def get_employee_docs(self, employee_id):
        aso_docs = self.aso_df[self.aso_df['id'] == employee_id]
        training_docs = self.training_df[self.training_df['id'] == employee_id]
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
                    if aba_name == LIFTING_SHEET_NAME:
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
                            'carga_horaria': row[9],
                            'instrutor': row[10],
                            'registro_instrutor': row[11],
                            'cnpj_empresa': row[12],
                            'topicos': row[13],
                            'observacoes': row[14]
                        }
            return None
        except Exception as e:
            st.error(f"Erro ao buscar documento: {str(e)}")
            return None 
