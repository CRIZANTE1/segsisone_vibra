import pandas as pd
from operations.sheet import SheetOperations
from gdrive.config import MATRIX_SPREADSHEET_ID
from fuzzywuzzy import process

class MatrixManager:
    def __init__(self):
        """
        Gerencia os dados da Planilha Matriz, que contém a lista de unidades (tenants)
        e a lista de usuários autorizados do sistema.
        """
        # Este gerenciador SEMPRE se conecta à planilha matriz.
        self.sheet_ops = SheetOperations(MATRIX_SPREADSHEET_ID)
        self.users_df = pd.DataFrame()
        self.units_df = pd.DataFrame()
        self.training_matrix_df = pd.DataFrame() # DataFrame para a matriz de treinamentos
        self._load_data()

    def _load_data(self):
        """
        Carrega os dados das abas 'usuarios', 'unidades' e 'matriz_treinamentos'
        da Planilha Matriz de forma robusta.
        """
        # Carrega dados dos usuários
        users_data = self.sheet_ops.carregar_dados_aba("usuarios")
        if users_data and len(users_data) > 1:
            self.users_df = pd.DataFrame(users_data[1:], columns=users_data[0])
        else:
            # Garante que sempre seja um DataFrame, mesmo que vazio
            self.users_df = pd.DataFrame(columns=['email', 'nome', 'role', 'unidade_associada'])

        # Carrega dados das unidades
        units_data = self.sheet_ops.carregar_dados_aba("unidades")
        if units_data and len(units_data) > 1:
            self.units_df = pd.DataFrame(units_data[1:], columns=units_data[0])
        else:
            # Garante que sempre seja um DataFrame, mesmo que vazio
            self.units_df = pd.DataFrame(columns=['nome_unidade', 'spreadsheet_id', 'folder_id'])
            
        # Carrega a matriz de treinamentos
        # Supondo que exista uma aba chamada 'matriz_treinamentos' com colunas como 'funcao' e 'treinamentos_obrigatorios'
        matrix_data = self.sheet_ops.carregar_dados_aba("matriz_treinamentos")
        if matrix_data and len(matrix_data) > 1:
            self.training_matrix_df = pd.DataFrame(matrix_data[1:], columns=matrix_data[0])
        else:
            self.training_matrix_df = pd.DataFrame(columns=['funcao', 'treinamentos_obrigatorios'])


    def get_user_info(self, email: str) -> dict | None:
        """Busca informações de um usuário pelo e-mail."""
        if self.users_df.empty: 
            return None
        # Garante a comparação sem distinção de maiúsculas/minúsculas
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

    def find_closest_function(self, cargo: str, score_cutoff: int = 80) -> str | None:
        """
        Encontra o nome da função mais próxima na matriz de treinamentos usando fuzzy matching.
        Retorna o nome exato da função da matriz se a similaridade for alta o suficiente.
        """
        if self.training_matrix_df.empty or 'funcao' not in self.training_matrix_df.columns:
            return None
        
        # Obtém uma lista de todas as funções únicas da matriz
        available_functions = self.training_matrix_df['funcao'].dropna().unique().tolist()
        if not available_functions:
            return None
            
        # Usa fuzzywuzzy para encontrar a correspondência mais próxima
        best_match = process.extractOne(cargo, available_functions, score_cutoff=score_cutoff)
        
        # Retorna o nome da função se uma boa correspondência for encontrada
        return best_match[0] if best_match else None

    def get_required_trainings_for_function(self, function_name: str) -> list:
        """
        Busca os treinamentos obrigatórios para uma função específica na matriz.
        Assume que os treinamentos estão em uma coluna 'treinamentos_obrigatorios',
        separados por vírgula.
        """
        if self.training_matrix_df.empty or not function_name:
            return []
            
        # Filtra o DataFrame para a função exata
        row = self.training_matrix_df[self.training_matrix_df['funcao'] == function_name]
        
        if row.empty:
            return []
            
        # Pega o valor da coluna de treinamentos
        trainings_str = row.iloc[0].get('treinamentos_obrigatorios', '')
        
        # Retorna uma lista limpa de treinamentos
        if trainings_str and isinstance(trainings_str, str):
            # Divide a string por vírgula e remove espaços em branco de cada item
            return [training.strip() for training in trainings_str.split(',') if training.strip()]
        
        return []
