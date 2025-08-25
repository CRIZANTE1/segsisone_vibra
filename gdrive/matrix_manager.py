import streamlit as st
import pandas as pd
import logging
from operations.sheet import SheetOperations
from gdrive.config import MATRIX_SPREADSHEET_ID

logger = logging.getLogger('segsisone_app.matrix_manager')

# --- FUNÇÃO DE CACHE GLOBAL PARA OS DADOS DA MATRIZ ---
@st.cache_data(ttl=300) # Cache de 5 minutos
def load_matrix_sheets_data():
    """
    Função em cache que se conecta à Planilha Matriz e carrega os dados brutos.
    Retorna os dados ou None em caso de falha.
    """
    logger.info("Tentando carregar dados da Planilha Matriz (pode usar cache)...")
    try:
        # A classe SheetOperations já lida com erros de conexão
        sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        
        # Verifica se a conexão foi bem-sucedida antes de prosseguir
        if not sheet_ops.spreadsheet:
            logger.error("Não foi possível abrir a Planilha Matriz. Verifique o ID e as permissões.")
            st.error("Erro Crítico: Não foi possível conectar à Planilha Matriz de controle.")
            return None, None

        users_data = sheet_ops.carregar_dados_aba("usuarios")
        units_data = sheet_ops.carregar_dados_aba("unidades")
        
        logger.info("Dados da Planilha Matriz carregados com sucesso.")
        return users_data, units_data
        
    except Exception as e:
        logger.critical(f"Falha crítica e inesperada ao carregar dados da Planilha Matriz: {e}", exc_info=True)
        st.error(f"Falha crítica ao carregar dados da Planilha Matriz: {e}")
        return None, None

class MatrixManager:
    def __init__(self):
        """
        Gerencia os dados da Planilha Matriz (usuários e unidades).
        """
        self.users_df = pd.DataFrame()
        self.units_df = pd.DataFrame()
        self.data_loaded_successfully = False
        self._load_data_from_cache()

    def _load_data_from_cache(self):
        """
        Carrega os dados da função em cache e os transforma em DataFrames robustos,
        garantindo que as colunas esperadas sempre existam.
        """
        users_data, units_data = load_matrix_sheets_data()

        # Define as colunas esperadas para garantir a integridade do DataFrame
        expected_user_cols = ['email', 'nome', 'role', 'unidade_associada']
        expected_unit_cols = ['nome_unidade', 'spreadsheet_id', 'folder_id']

        # Carrega dados dos usuários
        if users_data and len(users_data) > 1:
            self.users_df = pd.DataFrame(users_data[1:], columns=users_data[0])
            # Garante que todas as colunas esperadas existam, preenchendo com valores padrão se necessário
            for col in expected_user_cols:
                if col not in self.users_df.columns:
                    self.users_df[col] = None
            # Padroniza a coluna de e-mail para minúsculas para evitar erros de comparação
            self.users_df['email'] = self.users_df['email'].str.lower().str.strip()
        else:
            self.users_df = pd.DataFrame(columns=expected_user_cols)
            logger.warning("A aba 'usuarios' da Planilha Matriz está vazia ou contém apenas cabeçalho.")

        # Carrega dados das unidades
        if units_data and len(units_data) > 1:
            self.units_df = pd.DataFrame(units_data[1:], columns=units_data[0])
            for col in expected_unit_cols:
                if col not in self.units_df.columns:
                    self.units_df[col] = None
        else:
            self.units_df = pd.DataFrame(columns=expected_unit_cols)
            logger.warning("A aba 'unidades' da Planilha Matriz está vazia ou contém apenas cabeçalho.")
            
        # Se ambos os dataframes foram criados (mesmo que vazios), consideramos a carga bem-sucedida
        if isinstance(self.users_df, pd.DataFrame) and isinstance(self.units_df, pd.DataFrame):
            self.data_loaded_successfully = True

    def get_user_info(self, email: str) -> dict | None:
        """Busca informações de um usuário pelo e-mail (case-insensitive)."""
        if self.users_df.empty or not email:
            return None
        
        user_info = self.users_df[self.users_df['email'] == email.lower().strip()]
        
        return user_info.iloc[0].to_dict() if not user_info.empty else None

    def get_unit_info(self, unit_name: str) -> dict | None:
        """Busca informações de uma unidade pelo nome."""
        if self.units_df.empty or not unit_name:
            return None
            
        unit_info = self.units_df[self.units_df['nome_unidade'] == unit_name]
        
        return unit_info.iloc[0].to_dict() if not unit_info.empty else None
        
    def add_unit(self, unit_data: list) -> bool:
        """Adiciona uma nova unidade e limpa o cache."""
        try:
            sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
            result = sheet_ops.adc_dados_aba("unidades", unit_data)
            if result:
                load_matrix_sheets_data.clear() # Limpa o cache para forçar recarga
                logger.info(f"Nova unidade adicionada. Cache da Planilha Matriz invalidado.")
                return True
            return False
        except Exception as e:
            logger.error(f"Falha ao adicionar nova unidade: {e}")
            return False

    def get_all_units(self) -> list:
        """Retorna todas as unidades como uma lista de dicionários."""
        return self.units_df.to_dict(orient='records') if not self.units_df.empty else []

    def get_all_users(self) -> list:
        """Retorna todos os usuários como uma lista de dicionários."""
        return self.users_df.to_dict(orient='records') if not self.users_df.empty else []

    def add_user(self, user_data: list) -> bool:
        """Adiciona um novo usuário e limpa o cache."""
        try:
            sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
            result = sheet_ops.adc_dados_aba("usuarios", user_data)
            if result:
                load_matrix_sheets_data.clear() # Limpa o cache para forçar recarga
                logger.info(f"Novo usuário adicionado. Cache da Planilha Matriz invalidado.")
                return True
            return False
        except Exception as e:
            logger.error(f"Falha ao adicionar novo usuário: {e}")
            return False
