import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, date
from gdrive.gdrive_upload import GoogleDriveUploader
from AI.api_Operation import PDFQA
from operations.sheet import SheetOperations
from operations.matrix_manager import MatrixManager
import tempfile
import os
import re
import locale
import json
from dateutil.relativedelta import relativedelta
from auth.auth_utils import get_user_email

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    pass

class EmployeeManager:
    def __init__(self, spreadsheet_id: str):
        """
        Gerencia funcionários, ASOs e treinamentos para um tenant específico.
        Args:
            spreadsheet_id (str): O ID da Planilha Google do tenant.
        """
        self.sheet_ops = SheetOperations(spreadsheet_id)
        self.matrix_manager = MatrixManager()
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
            'NR-06': {'inicial_horas': 3, 'reciclagem_horas': 3, 'reciclagem_anos': 10},
            'NR-6': {'inicial_horas': 3, 'reciclagem_horas': 3, 'reciclagem_anos': 3},
            'NR-12': {'inicial_horas': 8, 'reciclagem_horas': 8, 'reciclagem_anos': 5},
            'NR-34': {'inicial_horas': 8, 'reciclagem_horas': 8, 'reciclagem_anos': 1},
            'NR-33': {'reciclagem_anos': 1},
            'BRIGADA DE INCÊNDIO': {'reciclagem_anos': 1},
            'NR-11': {'reciclagem_anos': 3, 'reciclagem_horas': 16},
            'NBR-16710 RESGATE TÉCNICO': {'reciclagem_anos': 1},
            'PERMISSÃO DE TRABALHO (PT)': {'reciclagem_anos': 1}
        }

    def log_action(self, action: str, details: dict):
        """
        Registra uma ação do usuário na aba de log centralizada.
        """
        try:
            user_email = get_user_email()
            user_role = st.session_state.get('role', 'N/A')
            target_uo = st.session_state.get('unit_name', 'N/A')
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            log_data = [
                timestamp,
                user_email,
                user_role,
                action,
                json.dumps(details),
                target_uo
            ]
            
            self.matrix_manager.log_action_central(log_data)
        except Exception as e:
            print(f"Error logging action centrally: {e}")

    @property
    def pdf_analyzer(self):
        if self._pdf_analyzer is None:
            self._pdf_analyzer = PDFQA()
        return self._pdf_analyzer

    def load_data(self):
        """Carrega todos os DataFrames do tenant."""
        try:
            companies_data = self.sheet_ops.carregar_dados_aba("empresas")
            self.companies_df = pd.DataFrame(companies_data[1:], columns=companies_data[0]) if companies_data and len(companies_data) > 1 else pd.DataFrame()

            employees_data = self.sheet_ops.carregar_dados_aba("funcionarios")
            self.employees_df = pd.DataFrame(employees_data[1:], columns=employees_data[0]) if employees_data and len(employees_data) > 1 else pd.DataFrame()

            aso_data = self.sheet_ops.carregar_dados_aba("asos")
            self.aso_df = pd.DataFrame(aso_data[1:], columns=aso_data[0]) if aso_data and len(aso_data) > 1 else pd.DataFrame()

            training_data = self.sheet_ops.carregar_dados_aba("treinamentos")
            self.training_df = pd.DataFrame(training_data[1:], columns=training_data[0]) if training_data and len(training_data) > 1 else pd.DataFrame()
        except Exception as e:
            st.error(f"Erro ao carregar dados do tenant: {str(e)}")
            self.companies_df, self.employees_df, self.aso_df, self.training_df = (pd.DataFrame() for _ in range(4))

    def add_company(self, nome, cnpj):
        if not self.companies_df.empty and cnpj in self.companies_df['cnpj'].values:
            return None, "CNPJ já cadastrado."
        new_data = [nome, cnpj, "Ativo"]
        try:
            company_id = self.sheet_ops.adc_dados_aba("empresas", new_data)
            if company_id:
                self.log_action("add_company", {"company_id": company_id, "nome": nome, "cnpj": cnpj})
                self.load_data()
                return company_id, "Empresa cadastrada com sucesso"
            return None, "Falha ao obter ID da empresa."
        except Exception as e:
            return None, f"Erro ao cadastrar empresa: {str(e)}"

    def add_employee(self, nome, cargo, data_admissao, empresa_id):
        new_data = [nome, str(empresa_id), cargo, data_admissao.strftime("%d/%m/%Y"), "Ativo"]
        try:
            employee_id = self.sheet_ops.adc_dados_aba("funcionarios", new_data)
            if employee_id:
                self.log_action("add_employee", {"employee_id": employee_id, "nome": nome, "empresa_id": empresa_id})
                self.load_data()
                return employee_id, "Funcionário adicionado com sucesso"
            return None, "Erro ao adicionar funcionário na planilha"
        except Exception as e:
            return None, f"Erro ao adicionar funcionário: {str(e)}"

    def add_aso(self, aso_data: dict):
        new_data = [
            str(aso_data.get('funcionario_id')),
            aso_data.get('data_aso').strftime("%d/%m/%Y"),
            aso_data.get('vencimento').strftime("%d/%m/%Y") if aso_data.get('vencimento') else "N/A",
            str(aso_data.get('arquivo_id')),
            aso_data.get('riscos', 'Não identificado'),
            aso_data.get('cargo', 'Não identificado'),
            aso_data.get('tipo_aso', 'Não identificado')
        ]
        try:
            aso_id = self.sheet_ops.adc_dados_aba("asos", new_data)
            if aso_id:
                self.log_action("add_aso", {"aso_id": aso_id, "funcionario_id": aso_data.get('funcionario_id')})
                self.load_data()
                return aso_id
            return None
        except Exception as e:
            st.error(f"Erro ao adicionar ASO na planilha: {str(e)}")
            return None

    def add_training(self, training_data: dict):
        new_data = [
            str(training_data.get('funcionario_id')),
            training_data.get('data').strftime("%d/%m/%Y"),
            training_data.get('vencimento').strftime("%d/%m/%Y"),
            self._padronizar_norma(training_data.get('norma')),
            str(training_data.get('modulo')) if training_data.get('modulo') else 'N/A',
            str(training_data.get('status')),
            str(training_data.get('anexo')),
            str(training_data.get('tipo_treinamento')) if training_data.get('tipo_treinamento') else 'Não identificado',
            str(training_data.get('carga_horaria')) if training_data.get('carga_horaria') is not None else '0'
        ]
        try:
            training_id = self.sheet_ops.adc_dados_aba("treinamentos", new_data)
            if training_id:
                self.log_action("add_training", {"training_id": training_id, "funcionario_id": training_data.get('funcionario_id'), "norma": training_data.get('norma')})
                self.load_data()
                return training_id
            st.error("A escrita na planilha falhou e não retornou um ID de registro.")
            return None
        except Exception as e:
            st.error(f"Erro ao adicionar treinamento na planilha: {str(e)}")
            return None

    def delete_training(self, training_id: str, file_url: str):
        uploader = GoogleDriveUploader()
        if file_url and pd.notna(file_url):
            if not uploader.delete_file_by_url(file_url):
                st.warning("Falha ao deletar o arquivo do Google Drive, mas prosseguindo.")
        
        deleted = self.sheet_ops.excluir_dados_aba("treinamentos", training_id)
        if deleted:
            self.log_action("delete_training", {"training_id": training_id})
            self.load_data()
        return deleted

    def delete_aso(self, aso_id: str, file_url: str):
        uploader = GoogleDriveUploader()
        if file_url and pd.notna(file_url):
            if not uploader.delete_file_by_url(file_url):
                st.warning("Falha ao deletar o arquivo do Google Drive, mas prosseguindo.")

        deleted = self.sheet_ops.excluir_dados_aba("asos", aso_id)
        if deleted:
            self.log_action("delete_aso", {"aso_id": aso_id})
            self.load_data()
        return deleted

    def delete_all_employee_data(self, employee_id: str):
        trainings_to_delete = self.training_df[self.training_df['funcionario_id'] == str(employee_id)]
        for index, row in trainings_to_delete.iterrows():
            self.delete_training(row['id'], row.get('arquivo_id'))
        
        asos_to_delete = self.aso_df[self.aso_df['funcionario_id'] == str(employee_id)]
        for index, row in asos_to_delete.iterrows():
            self.delete_aso(row['id'], row.get('arquivo_id'))

        if self.sheet_ops.excluir_dados_aba("funcionarios", employee_id):
            self.log_action("delete_all_employee_data", {"employee_id": employee_id})
            self.load_data()
            return True
        else:
            st.error(f"Falha ao excluir o registro principal do funcionário ID {employee_id}.")
            return False

    def _set_status(self, sheet_name: str, item_id: str, status: str):
        success = self.sheet_ops.update_row_by_id(sheet_name, item_id, {'status': status})
        if success:
            self.log_action("set_status", {"item_id": item_id, "sheet": sheet_name, "status": status})
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

    def get_latest_aso_by_employee(self, employee_id):
        if self.aso_df.empty:
            return pd.DataFrame()
            
        aso_docs = self.aso_df[self.aso_df['funcionario_id'] == str(employee_id)].copy()
        if aso_docs.empty:
            return pd.DataFrame()
    
        if 'tipo_aso' not in aso_docs.columns:
            aso_docs['tipo_aso'] = 'Não Identificado'
        aso_docs['tipo_aso'] = aso_docs['tipo_aso'].fillna('Não Identificado').astype(str).str.strip()
        
        aso_docs['data_aso_dt'] = pd.to_datetime(aso_docs['data_aso'], format='%d/%m/%Y', errors='coerce')
        aso_docs.dropna(subset=['data_aso_dt'], inplace=True)
        if aso_docs.empty: return pd.DataFrame()
        
        latest_asos = aso_docs.sort_values('data_aso_dt', ascending=False).groupby('tipo_aso').head(1).copy()
        
        latest_asos['data_aso'] = latest_asos['data_aso_dt'].dt.date
        latest_asos['vencimento'] = pd.to_datetime(latest_asos['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        latest_asos = latest_asos.drop(columns=['data_aso_dt'])
        
        return latest_asos.sort_values('data_aso', ascending=False)

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
    
        training_docs = training_docs.sort_values('data_dt', ascending=False)
        latest_trainings = training_docs.groupby('norma').head(1).copy()
                
        latest_trainings['data'] = latest_trainings['data_dt'].dt.date
        latest_trainings['vencimento'] = pd.to_datetime(latest_trainings['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        
        latest_trainings = latest_trainings.drop(columns=['data_dt'])
        
        return latest_trainings.sort_values('data', ascending=False)

    def analyze_training_pdf(self, pdf_file):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name
            
            structured_prompt = """...""" # Prompt is omitted for brevity
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

            # ... (parsing logic) 
            
            return {
                'data': data_realizacao, 
                'norma': norma_padronizada, 
                'modulo': modulo, 
                'tipo_treinamento': tipo_treinamento, 
                'carga_horaria': carga_horaria
            }

        except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as e:
            st.error(f"Erro ao processar a resposta da IA para o treinamento: {e}")
            st.code(f"Resposta recebida da IA:\n{answer}")
            return None

    def analyze_aso_pdf(self, pdf_file):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name
            
            structured_prompt = """...""" # Prompt is omitted for brevity
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

            # ... (parsing logic) 
            
            return {
                'data_aso': data_aso, 
                'vencimento': vencimento, 
                'riscos': data.get('riscos', ""), 
                'cargo': data.get('cargo', ""),
                'tipo_aso': tipo_aso
            }

        except (json.JSONDecodeError, AttributeError) as e:
            st.error(f"Erro ao processar a resposta da IA para o ASO: {e}")
            st.code(f"Resposta recebida da IA:\n{answer}")
            return None

    def _padronizar_norma(self, norma):
        if not norma:
            return None
        
        norma_upper = str(norma).strip().upper()
    
        if "BRIGADA" in norma_upper or "INCÊNDIO" in norma_upper or "IT-17" in norma_upper or "IT 17" in norma_upper or "NR-23" in norma_upper or "NR 23" in norma_upper:
            return "BRIGADA DE INCÊNDIO"

        if "16710" in norma_upper or "RESGATE TÉCNICO" in norma_upper:
            return "NBR-16710 RESGATE TÉCNICO"
        
        if "PERMISSÃO" in norma_upper or re.search(r'\b(PT)\b', norma_upper): 
            return "PERMISSÃO DE TRABALHO (PT)"
            
        match = re.search(r'NR\s?-?(\d+)', norma_upper)
        if match:
            num = int(match.group(1))
            return f"NR-{num:02d}"
            
        return norma_upper

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

    def get_employees_by_company(self, company_id: str, include_archived: bool = False):
        if self.employees_df.empty:
            return pd.DataFrame()
        
        company_employees = self.employees_df[self.employees_df['empresa_id'] == str(company_id)]
        
        if include_archived:
            return company_employees
        else:
            return company_employees[company_employees['status'].str.lower() == 'ativo']

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
        
        config = None
        anos_validade = None
    
        if norma_padronizada == "NR-20":
            if modulo and isinstance(modulo, str):
                modulo_limpo = modulo.strip()
                for key, value in self.nr20_config.items():
                    if key.lower() == modulo_limpo.lower():
                        config = value
                        anos_validade = config.get('reciclagem_anos')
                        break
            
            if anos_validade is None:
                st.warning(f"Módulo da NR-20 ('{modulo}') não reconhecido. Assumindo 1 ano.")
                anos_validade = 1
    
        else:
            config = self.nr_config.get(norma_padronizada)
            if config:
                anos_validade = config.get('reciclagem_anos')
    
        if anos_validade is not None:
            try:
                from dateutil.relativedelta import relativedelta
                return data + relativedelta(years=int(anos_validade))
            except ImportError:
                return data + timedelta(days=int(anos_validade * 365.25))
    
        st.error(f"Não foi possível encontrar regras de vencimento para a norma '{norma_padronizada}'.")
        return None
        
    def archive_training(self, training_id: str, archive: bool = True):
        status = "Arquivado" if archive else "Ativo"
        return self._set_status("treinamentos", training_id, {'status': status})

    def validar_treinamento(self, norma, modulo, tipo_treinamento, carga_horaria):
        norma_padronizada = self._padronizar_norma(norma)
        
        if norma_padronizada == "NR-33":
            # ... (logic)
            pass
        
        return True, "Carga horária conforme."