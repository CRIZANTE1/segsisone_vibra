import streamlit as st
import pandas as pd
from operations.sheet import SheetOperations
from gdrive.config import MATRIX_SPREADSHEET_ID

# --- FUNÇÃO DE CACHE GLOBAL PARA OS DADOS DA MATRIZ ---
@st.cache_data(ttl=600) # Cache de 10 minutos para dados da matriz
def load_matrix_sheets_data():
    """
    Função em cache que se conecta à Planilha Matriz e carrega os dados brutos
    de 'usuarios' e 'unidades', evitando chamadas repetidas à API.
    """
    try:
        sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        users_data = sheet_ops.carregar_dados_aba("usuarios")
        units_data = sheet_ops.carregar_dados_aba("unidades")
        return users_data, units_data
    except Exception as e:
        st.error(f"Falha crítica ao carregar dados da Planilha Matriz: {e}")
        return None, None

class MatrixManager:
    def __init__(self):
        """
        Gerencia os dados da Planilha Matriz. Agora usa uma função em cache
        para minimizar as chamadas à API do Google Sheets.
        """
        self.users_df = pd.DataFrame()
        self.units_df = pd.DataFrame()
        self._load_data_from_cache()

    def _load_data_from_cache(self):
        """
        Carrega os dados da função em cache e os transforma em DataFrames.
        """
        users_data, units_data = load_matrix_sheets_data()

        # Carrega dados dos usuários
        expected_user_cols = ['email', 'nome', 'role', 'unidade_associada']
        if users_data and len(users_data) > 1:
            self.users_df = pd.DataFrame(users_data[1:], columns=users_data[0])
        else:
            self.users_df = pd.DataFrame(columns=expected_user_cols)

        # Carrega dados das unidades
        expected_unit_cols = ['nome_unidade', 'spreadsheet_id', 'folder_id']
        if units_data and len(units_data) > 1:
            self.units_df = pd.DataFrame(units_data[1:], columns=units_data[0])
        else:
            self.units_df = pd.DataFrame(columns=expected_unit_cols)

    def get_user_info(self, email: str) -> dict | None:
        if self.users_df.empty: return None
        user_info = self.users_df[self.users_df['email'].str.lower() == email.lower()]
        return user_info.iloc[0].to_dict() if not user_info.empty else None

    def get_unit_info(self, unit_name: str) -> dict | None:
        if self.units_df.empty: return None
        unit_info = self.units_df[self.units_df['nome_unidade'] == unit_name]
        return unit_info.iloc[0].to_dict() if not unit_info.empty else None
        
    def add_unit(self, unit_data: list):
        sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        result = sheet_ops.adc_dados_aba("unidades", unit_data)
        if result: load_matrix_sheets_data.clear() # Limpa o cache após a escrita
        return result

    def get_all_units(self) -> list:
        return self.units_df.to_dict(orient='records') if not self.units_df.empty else []

    def get_all_users(self) -> list:
        return self.users_df.to_dict(orient='records') if not self.users_df.empty else []

    def add_user(self, user_data: list):
        sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        result = sheet_ops.adc_dados_aba("usuarios", user_data)
        if result: load_matrix_sheets_data.clear() # Limpa o cache após a escrita
        return result
