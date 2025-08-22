import pandas as pd
from operations.sheet import SheetOperations
from gdrive.config import MATRIX_SPREADSHEET_ID

class MatrixManager:
    def __init__(self):
        """
        Gerencia a Planilha Matriz, que atua como um roteador, contendo a lista
        de unidades (tenants) e a lista de usuários autorizados do sistema.
        """
        self.sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        self.users_df = pd.DataFrame()
        self.units_df = pd.DataFrame()
        self._load_data()

    def _load_data(self):
        """
        Carrega os dados das abas 'usuarios' e 'unidades' da Planilha Matriz.
        """
        # Carrega dados dos usuários
        users_data = self.sheet_ops.carregar_dados_aba("usuarios")
        if users_data and len(users_data) > 1:
            self.users_df = pd.DataFrame(users_data[1:], columns=users_data[0])
        else:
            self.users_df = pd.DataFrame(columns=['email', 'nome', 'role', 'unidade_associada'])

        # Carrega dados das unidades
        units_data = self.sheet_ops.carregar_dados_aba("unidades")
        if units_data and len(units_data) > 1:
            self.units_df = pd.DataFrame(units_data[1:], columns=units_data[0])
        else:
            self.units_df = pd.DataFrame(columns=['nome_unidade', 'spreadsheet_id', 'folder_id'])

    def get_user_info(self, email: str) -> dict | None:
        """Busca informações de um usuário pelo e-mail."""
        if self.users_df.empty: 
            return None
        user_info = self.users_df[self.users_df['email'].str.lower() == email.lower()]
        return user_info.iloc[0].to_dict() if not user_info.empty else None

    def get_unit_info(self, unit_name: str) -> dict | None:
        """Busca informações de uma unidade pelo nome."""
        if self.units_df.empty: 
            return None
        unit_info = self.units_df[self.units_df['nome_unidade'] == unit_name]
        return unit_info.iloc[0].to_dict() if not unit_info.empty else None
        
    def add_unit(self, unit_data: list) -> int | None:
        """Adiciona uma nova unidade à Planilha Matriz."""
        return self.sheet_ops.adc_dados_aba("unidades", unit_data)

    def get_all_units(self) -> list:
        """Retorna uma lista de dicionários de todas as unidades cadastradas."""
        return self.units_df.to_dict(orient='records') if not self.units_df.empty else []

    def get_all_users(self) -> list:
        """Retorna uma lista de dicionários de todos os usuários cadastrados."""
        return self.users_df.to_dict(orient='records') if not self.users_df.empty else []

    def add_user(self, user_data: list) -> int | None:
        """Adiciona um novo usuário à Planilha Matriz."""
        return self.sheet_ops.adc_dados_aba("usuarios", user_data)
