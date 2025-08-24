import streamlit as st
import pandas as pd
from operations.sheet import SheetOperations
from gdrive.config import MATRIX_SPREADSHEET_ID

# --- FUNÇÃO DE CACHE GLOBAL PARA OS DADOS DA MATRIZ ---
@st.cache_data(ttl=600) # Cache de 10 minutos para dados da matriz
def load_matrix_sheets_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Função em cache que se conecta à Planilha Matriz e carrega os dados brutos
    de 'usuarios' e 'unidades', evitando chamadas repetidas à API.
    """
    try:
        sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        users_df = sheet_ops.get_df_from_worksheet("usuarios")
        units_df = sheet_ops.get_df_from_worksheet("unidades")
        return users_df, units_df
    except Exception as e:
        st.error(f"Falha crítica ao carregar dados da Planilha Matriz: {e}")
        return pd.DataFrame(), pd.DataFrame()

class MatrixManager:
    def __init__(self):
        """
        Gerencia os dados da Planilha Matriz. Agora usa uma função em cache
        para minimizar as chamadas à API do Google Sheets.
        """
        self.users_df, self.units_df = load_matrix_sheets_data()

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
        new_unit_df = pd.DataFrame([unit_data], columns=self.units_df.columns)
        updated_units_df = pd.concat([self.units_df, new_unit_df], ignore_index=True)
        result = sheet_ops.update_worksheet_from_df("unidades", updated_units_df)
        if result: load_matrix_sheets_data.clear() # Limpa o cache após a escrita
        return result

    def get_all_units(self) -> list:
        return self.units_df.to_dict(orient='records') if not self.units_df.empty else []

    def get_all_users(self) -> list:
        return self.users_df.to_dict(orient='records') if not self.users_df.empty else []

    def add_user(self, user_data: list):
        sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        new_user_df = pd.DataFrame([user_data], columns=self.users_df.columns)
        updated_users_df = pd.concat([self.users_df, new_user_df], ignore_index=True)
        result = sheet_ops.update_worksheet_from_df("usuarios", updated_users_df)
        if result: load_matrix_sheets_data.clear() # Limpa o cache após a escrita
        return result