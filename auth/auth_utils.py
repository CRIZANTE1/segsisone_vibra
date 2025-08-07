import streamlit as st
import pandas as pd
from operations.sheet import SheetOperations
from gdrive.config import ADM_SHEET_NAME

def is_oidc_available():
    """Verifica se o login OIDC está configurado e disponível."""
    return hasattr(st, 'user') and hasattr(st.user, 'is_logged_in')

def is_user_logged_in():
    """Verifica se o usuário está logado."""
    return is_oidc_available() and st.user.is_logged_in

def get_user_email() -> str | None:
    """
    Retorna o e-mail do usuário logado, sempre em minúsculas.
    Este é o identificador único e primário do usuário.
    """
    if is_user_logged_in() and hasattr(st.user, 'email'):
        return st.user.email.lower().strip()
    return None

def get_user_display_name() -> str:
    """Retorna o nome de exibição do usuário para fins cosméticos."""
    if is_user_logged_in() and hasattr(st.user, 'name'):
        return st.user.name
    # Fallback para o e-mail se o nome não estiver disponível
    return get_user_email() or "Usuário Desconhecido"

# --- NOVA LÓGICA DE PERMISSÕES BASEADA EM PAPÉIS (ROLES) ---

@st.cache_data(ttl=300) # Cache da lista de permissões por 5 minutos
def get_user_permissions() -> pd.DataFrame:
    """
    Carrega a lista de usuários e suas permissões da planilha ADM.
    Retorna um DataFrame com as colunas 'email' e 'role'.
    """
    try:
        sheet_ops = SheetOperations()
        admins_data = sheet_ops.carregar_dados_aba(ADM_SHEET_NAME)
        
        # Retorna um DataFrame vazio se não houver dados ou apenas o cabeçalho
        if not admins_data or len(admins_data) < 2:
            return pd.DataFrame(columns=['email', 'role'])
        
        # Cria um DataFrame a partir dos dados da planilha
        permissions_df = pd.DataFrame(admins_data[1:], columns=admins_data[0])
        
        # Garante que as colunas essenciais existam e normaliza os dados
        if 'email' in permissions_df.columns:
            permissions_df['email'] = permissions_df['email'].str.lower().str.strip()
        else:
            # Se não houver coluna 'email', o sistema de permissões não pode funcionar
            st.error("A planilha 'ADM' não contém a coluna 'email'. As permissões não podem ser verificadas.")
            return pd.DataFrame(columns=['email', 'role'])

        if 'role' in permissions_df.columns:
            permissions_df['role'] = permissions_df['role'].str.lower().str.strip().fillna('viewer')
        else:
            # Se a coluna 'role' não existir, assume que todos são 'viewer' por segurança
            st.warning("A planilha 'ADM' não contém a coluna 'role'. Todos os usuários terão permissão de visualização.")
            permissions_df['role'] = 'viewer' 
            
        return permissions_df[['email', 'role']]

    except Exception as e:
        st.error(f"Erro crítico ao carregar permissões de usuário: {e}")
        return pd.DataFrame(columns=['email', 'role'])

def get_user_role() -> str:
    """
    Retorna o papel (role) do usuário logado.
    O padrão para usuários não listados na planilha ADM é 'viewer'.
    """
    user_email = get_user_email()
    if not user_email:
        return 'viewer' # Padrão para não logado

    permissions_df = get_user_permissions()
    if permissions_df.empty:
        return 'viewer'

    # Procura pelo e-mail do usuário no DataFrame de permissões
    user_entry = permissions_df[permissions_df['email'] == user_email]
    
    if not user_entry.empty:
        # Se encontrou, retorna o papel da primeira ocorrência
        return user_entry.iloc[0]['role']
    
    # Se o usuário logado não está na lista, ele é um 'viewer' por padrão
    return 'viewer'

def is_admin() -> bool:
    """Verifica se o usuário tem o papel de 'admin'."""
    return get_user_role() == 'admin'

def can_edit() -> bool:
    """Verifica se o usuário tem permissão para editar (admin OU editor)."""
    return get_user_role() in ['admin', 'editor']

def check_permission(level: str = 'editor') -> bool:
    """
    Função principal de verificação. Bloqueia a execução e exibe um erro se a
    permissão não for atendida.
    
    Args:
        level (str): O nível mínimo de permissão necessário ('admin' ou 'editor').
                     O padrão é 'editor'.
    """
    if level == 'admin':
        if not is_admin():
            st.error("Você não tem permissão de Administrador para acessar esta funcionalidade.")
            return False
    elif level == 'editor':
        if not can_edit():
            st.error("Você não tem permissão para adicionar ou modificar dados. Contate um administrador.")
            return False
        
    return True




