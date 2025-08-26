import streamlit as st
import pandas as pd
import logging
from operations.sheet import SheetOperations
from gdrive.config import MATRIX_SPREADSHEET_ID, CENTRAL_LOG_SHEET_NAME 
from fuzzywuzzy import process
from operations.audit_logger import log_action


logger = logging.getLogger('segsisone_app.matrix_manager')

# --- FUNÇÃO DE CACHE GLOBAL PARA OS DADOS DA MATRIZ ---
@st.cache_data(ttl=300)
def load_matrix_sheets_data():
    """
    Carrega TODAS as abas de dados da Planilha Matriz global.
    """
    logger.info("Carregando dados da Planilha Matriz (pode usar cache)...")
    try:
        sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        if not sheet_ops.spreadsheet:
            st.error("Erro Crítico: Não foi possível conectar à Planilha Matriz de controle.")
            return None, None, None, None, None

        users_data = sheet_ops.carregar_dados_aba("usuarios")
        units_data = sheet_ops.carregar_dados_aba("unidades")
        functions_data = sheet_ops.carregar_dados_aba("funcoes")
        matrix_data = sheet_ops.carregar_dados_aba("matriz_treinamentos")
        log_data = sheet_ops.carregar_dados_aba(CENTRAL_LOG_SHEET_NAME)
        
        logger.info("Dados da Planilha Matriz carregados com sucesso.")
        return users_data, units_data, functions_data, matrix_data, log_data
        
    except Exception as e:
        logger.critical(f"Falha crítica ao carregar dados da Planilha Matriz: {e}", exc_info=True)
        return None, None, None, None

class MatrixManager:
    def __init__(self):
        """
        Gerencia TODOS os dados da Planilha Matriz global:
        - Usuários e Unidades (para controle de acesso)
        - Funções e Matriz de Treinamentos (para lógica de negócio)
        """
        self.users_df = pd.DataFrame()
        self.units_df = pd.DataFrame()
        self.functions_df = pd.DataFrame()
        self.training_matrix_df = pd.DataFrame()
        self.log_df = pd.DataFrame()
        self.data_loaded_successfully = False
        self._load_data_from_cache()

    def _load_data_from_cache(self):
        """
        Carrega os dados da função em cache e os transforma em DataFrames robustos,
        garantindo que as colunas esperadas sempre existam.
        """
        users_data, units_data, functions_data, matrix_data, log_data = load_matrix_sheets_data()

        # Define as colunas esperadas para cada aba
        user_cols = ['email', 'nome', 'role', 'unidade_associada']
        unit_cols = ['nome_unidade', 'spreadsheet_id', 'folder_id']
        func_cols = ['id', 'nome_funcao', 'descricao']
        matrix_cols = ['id', 'id_funcao', 'norma_obrigatoria']
        log_cols = ['timestamp', 'user_email', 'user_role', 'action', 'details', 'target_uo']

        # --- Carrega Usuários ---
        if users_data and len(users_data) > 1:
            self.users_df = pd.DataFrame(users_data[1:], columns=users_data[0])
            # Garante que todas as colunas esperadas existam
            for col in user_cols:
                if col not in self.users_df.columns:
                    self.users_df[col] = None
            # Padroniza a coluna de e-mail
            if 'email' in self.users_df.columns:
                self.users_df['email'] = self.users_df['email'].str.lower().str.strip()
        else:
            self.users_df = pd.DataFrame(columns=user_cols)
            logger.warning("A aba 'usuarios' da Planilha Matriz está vazia ou contém apenas cabeçalho.")

        # --- Carrega Unidades ---
        if units_data and len(units_data) > 1:
            self.units_df = pd.DataFrame(units_data[1:], columns=units_data[0])
            for col in unit_cols:
                if col not in self.units_df.columns:
                    self.units_df[col] = None
        else:
            self.units_df = pd.DataFrame(columns=unit_cols)
            logger.warning("A aba 'unidades' da Planilha Matriz está vazia ou contém apenas cabeçalho.")

        # --- Carrega Funções ---
        if functions_data and len(functions_data) > 1:
            self.functions_df = pd.DataFrame(functions_data[1:], columns=functions_data[0])
            for col in func_cols:
                if col not in self.functions_df.columns:
                    self.functions_df[col] = None
        else:
            self.functions_df = pd.DataFrame(columns=func_cols)
            logger.warning("A aba 'funcoes' da Planilha Matriz está vazia ou contém apenas cabeçalho.")

        # --- Carrega Matriz de Treinamentos ---
        if matrix_data and len(matrix_data) > 1:
            self.training_matrix_df = pd.DataFrame(matrix_data[1:], columns=matrix_data[0])
            for col in matrix_cols:
                if col not in self.training_matrix_df.columns:
                    self.training_matrix_df[col] = None
        else:
            self.training_matrix_df = pd.DataFrame(columns=matrix_cols)
            logger.warning("A aba 'matriz_treinamentos' da Planilha Matriz está vazia ou contém apenas cabeçalho.")

        # --- Carrega Logs de Auditoria ---
        if log_data and len(log_data) > 1:
            self.log_df = pd.DataFrame(log_data[1:], columns=log_data[0])
            for col in log_cols:
                if col not in self.log_df.columns:
                    self.log_df[col] = None
        else:
            self.log_df = pd.DataFrame(columns=log_cols)
            logger.info("A aba 'log_auditoria' da Planilha Matriz está vazia ou contém apenas cabeçalho.")
        
        self.data_loaded_successfully = True
        
    # --- Métodos para Usuários e Unidades ---
    def get_user_info(self, email: str) -> dict | None:
        if self.users_df.empty: return None
        user_info = self.users_df[self.users_df['email'] == email.lower().strip()]
        return user_info.iloc[0].to_dict() if not user_info.empty else None

    def get_unit_info(self, unit_name: str) -> dict | None:
        if self.units_df.empty: return None
        unit_info = self.units_df[self.units_df['nome_unidade'] == unit_name]
        return unit_info.iloc[0].to_dict() if not unit_info.empty else None

    def get_all_units(self) -> list:
        return self.units_df.to_dict(orient='records') if not self.units_df.empty else []

    def get_audit_logs(self) -> pd.DataFrame:
        """Retorna o DataFrame de logs de auditoria."""
        return self.log_df

    def get_all_users(self) -> list:
        return self.users_df.to_dict(orient='records') if not self.users_df.empty else []

    def add_unit(self, unit_data: list) -> bool:
        """
        Adiciona uma nova unidade à Planilha Matriz e registra a ação no log.
        unit_data deve ser uma lista na ordem: [nome_unidade, spreadsheet_id, folder_id]
        """
        try:
            sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
            success = sheet_ops.adc_linha_simples("unidades", unit_data)
            
            if success:
                # --- LOG ADICIONADO AQUI ---
                log_action(
                    action="ADD_UNIT",
                    details={
                        "message": f"Nova unidade '{unit_data[0]}' adicionada ao sistema.",
                        "unit_name": unit_data[0],
                        "spreadsheet_id": unit_data[1],
                        "folder_id": unit_data[2]
                    }
                )
                
                load_matrix_sheets_data.clear()
                logger.info(f"Nova unidade '{unit_data[0]}' adicionada. Cache invalidado.")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Falha ao adicionar nova unidade: {e}")
            return False

    def add_user(self, user_data: list) -> bool:
        """
        Adiciona um novo usuário à Planilha Matriz e registra a ação no log.
        user_data deve ser uma lista na ordem: [email, nome, role, unidade_associada]
        """
        try:
            sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
            success = sheet_ops.adc_linha_simples("usuarios", user_data)
            
            if success:
                # --- LOG ADICIONADO AQUI ---
                log_action(
                    action="ADD_USER",
                    details={
                        "message": f"Novo usuário '{user_data[1]}' ({user_data[0]}) adicionado.",
                        "email": user_data[0],
                        "name": user_data[1],
                        "role": user_data[2],
                        "assigned_unit": user_data[3]
                    }
                )
                
                load_matrix_sheets_data.clear()
                logger.info(f"Novo usuário '{user_data[0]}' adicionado. Cache invalidado.")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Falha ao adicionar novo usuário: {e}")
            return False

    def remove_user(self, user_email: str) -> bool:
        """
        Remove um usuário da Planilha Matriz pelo e-mail e registra a ação no log.
        """
        if self.users_df.empty or not user_email:
            return False
        
        user_email_clean = user_email.lower().strip()
        user_row = self.users_df[self.users_df['email'] == user_email_clean]
        
        if user_row.empty:
            # Adiciona um log de aviso para facilitar a depuração
            logger.warning(f"Tentativa de remover usuário inexistente: {user_email_clean}")
            return False
        
        # O gspread precisa do índice da linha (começando em 1) + 1 (cabeçalho)
        row_to_delete_in_sheet = user_row.index[0] + 2
        
        try:
            sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
            success = sheet_ops.excluir_linha_por_indice("usuarios", row_to_delete_in_sheet)
            
            if success:
                # A sua chamada de log, que está correta
                log_action(
                    action="REMOVE_USER",
                    details={
                        "message": f"Usuário '{user_email_clean}' foi removido do sistema.",
                        "removed_user_email": user_email_clean
                    }
                )
                
                load_matrix_sheets_data.clear()
                logger.info(f"Usuário '{user_email_clean}' removido. Cache invalidado.")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Falha ao remover usuário '{user_email_clean}': {e}")
            return False

    # --- Métodos para Matriz de Treinamentos ---
    def find_closest_function(self, employee_cargo: str, score_cutoff: int = 80) -> str | None:
        if self.functions_df.empty or not employee_cargo: return None
        function_names = self.functions_df['nome_funcao'].tolist()
        best_match = process.extractOne(employee_cargo, function_names)
        if best_match and best_match[1] >= score_cutoff:
            return best_match[0]
        return None

    def get_required_trainings_for_function(self, function_name: str) -> list:
        if self.functions_df.empty or self.training_matrix_df.empty:
            return []
        
        function = self.functions_df[self.functions_df['nome_funcao'].str.lower() == function_name.lower()]
        if function.empty:
            return []
            
        function_id = function.iloc[0]['id']
        required_df = self.training_matrix_df[self.training_matrix_df['id_funcao'] == function_id]
        
        return required_df['norma_obrigatoria'].dropna().tolist()

    def add_function(self, name, description):
        if not self.functions_df.empty and name.lower() in self.functions_df['nome_funcao'].str.lower().values:
            return None, f"A função '{name}' já existe."
        sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        new_id = sheet_ops.adc_dados_aba("funcoes", [name, description])
        if new_id:
            load_matrix_sheets_data.clear()
            return new_id, "Função adicionada com sucesso."
        return None, "Falha ao adicionar função."

    def add_training_to_function(self, function_id, required_norm):
        if not self.training_matrix_df.empty and not self.training_matrix_df[(self.training_matrix_df['id_funcao'] == str(function_id)) & (self.training_matrix_df['norma_obrigatoria'] == required_norm)].empty:
            return None, "Este treinamento já está mapeado para esta função."
        sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        new_id = sheet_ops.adc_dados_aba("matriz_treinamentos", [str(function_id), required_norm])
        if new_id:
            load_matrix_sheets_data.clear()
            return new_id, "Treinamento mapeado com sucesso."
        return None, "Falha ao mapear treinamento."
