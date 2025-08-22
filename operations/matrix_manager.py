import pandas as pd
from operations.sheet import SheetOperations
from gdrive.config import MATRIX_SPREADSHEET_ID

class MatrixManager:
    def __init__(self):
        """
        Gerencia a Planilha Matriz que contém os dados de usuários e unidades.
        """
        self.sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        self.users_df = self._load_users()
        self.units_df = self._load_units()

    def _load_users(self):
        """Carrega os usuários da aba 'usuarios'."""
        users_data = self.sheet_ops.carregar_dados_aba("usuarios")
        if users_data and len(users_data) > 1:
            return pd.DataFrame(users_data[1:], columns=users_data[0])
        return pd.DataFrame(columns=['email', 'nome', 'role', 'unidade_associada'])

    def _load_units(self):
        """Carrega as unidades da aba 'unidades'."""
        units_data = self.sheet_ops.carregar_dados_aba("unidades")
        if units_data and len(units_data) > 1:
            return pd.DataFrame(units_data[1:], columns=units_data[0])
        return pd.DataFrame(columns=['id', 'nome_unidade', 'spreadsheet_id', 'folder_id'])

    def get_user_info(self, email: str) -> dict | None:
        """
        Busca informações de um usuário pelo email.
        """
        user_info = self.users_df[self.users_df['email'] == email]
        if not user_info.empty:
            return user_info.iloc[0].to_dict()
        return None

    def get_unit_info(self, unit_name: str) -> dict | None:
        """
        Busca informações de uma unidade pelo nome.
        """
        unit_info = self.units_df[self.units_df['nome_unidade'] == unit_name]
        if not unit_info.empty:
            return unit_info.iloc[0].to_dict()
        return None
        
    def add_unit(self, unit_data: list):
        """
        Adiciona uma nova unidade na aba 'unidades'.
        """
        return self.sheet_ops.adc_dados_aba("unidades", unit_data)

    def get_all_units(self) -> list[dict]:
        """
        Retorna uma lista de todos os tenants (unidades) cadastrados.
        """
        if not self.units_df.empty:
            return self.units_df.to_dict(orient='records')
        return []

    def log_action_central(self, log_data: list):
        """
        Registra uma ação na aba de log centralizada.
        """
        try:
            worksheet = self.sheet_ops._get_worksheet(CENTRAL_LOG_SHEET_NAME)
            if worksheet:
                worksheet.append_row(log_data, value_input_option='USER_ENTERED')
        except Exception as e:
            print(f"Error logging action centrally: {e}")