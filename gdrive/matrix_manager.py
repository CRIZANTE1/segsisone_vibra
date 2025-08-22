import pandas as pd
from operations.sheet import SheetOperations
from gdrive.config import MATRIX_SPREADSHEET_ID

class MatrixManager:
    def __init__(self):
        # Este gerenciador SEMPRE se conecta à planilha matriz.
        self.sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        self._load_data()

    def _load_data(self):
        users_data = self.sheet_ops.carregar_dados_aba("usuarios")
        self.users_df = pd.DataFrame(users_data[1:], columns=users_data[0]) if users_data and len(users_data) > 1 else pd.DataFrame()
        
        units_data = self.sheet_ops.carregar_dados_aba("unidades")
        self.units_df = pd.DataFrame(units_data[1:], columns=units_data[0]) if units_data and len(units_data) > 1 else pd.DataFrame()

    def get_user_info(self, email: str):
        if self.users_df.empty: return None
        user_info = self.users_df[self.users_df['email'].str.lower() == email.lower()]
        return user_info.iloc[0].to_dict() if not user_info.empty else None

    def get_unit_info(self, unit_name: str):
        if self.units_df.empty: return None
        unit_info = self.units_df[self.units_df['nome_unidade'] == unit_name]
        return unit_info.iloc[0].to_dict() if not unit_info.empty else None
        
    def add_unit(self, unit_data: list):
        return self.sheet_ops.adc_dados_aba("unidades", unit_data)

    def get_all_units(self):
        return self.units_df.to_dict(orient='records') if not self.units_df.empty else []

    def add_user(self, user_data: list):
        return self.sheet_ops.adc_dados_aba("usuarios", user_data)
