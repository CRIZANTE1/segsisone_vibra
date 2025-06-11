import streamlit as st
from operations.sheet import SheetOperations
from gdrive.config import ADM_SHEET_NAME

def is_oidc_available():
    """Verifica se o login OIDC está configurado e disponível"""
    try:
        return hasattr(st.user, 'is_logged_in')
    except Exception:
        return False

def is_user_logged_in():
    """Verifica se o usuário está logado"""
    try:
        return st.user.is_logged_in
    except Exception:
        return False

def get_user_display_name():
    """Retorna o nome de exibição do usuário"""
    try:
        if hasattr(st.user, 'name'):
            return st.user.name
        elif hasattr(st.user, 'email'):
            return st.user.email
        return "Usuário"
    except Exception:
        return "Usuário"

def get_user_role():
    """Retorna o papel do usuário (admin ou usuário normal)"""
    try:
        if hasattr(st.user, 'role'):
            return st.user.role
        return "user"  # Default role if not specified
    except Exception:
        return "user"  # Default role if an error occurs

def is_admin():
    """Verifica se o usuário atual é um administrador"""
    try:
        if not is_user_logged_in():
            return False
            
        user_name = get_user_display_name()
        if not user_name:
            return False
            
        # Carregar lista de administradores
        sheet_ops = SheetOperations()
        admins_data = sheet_ops.carregar_dados_aba(ADM_SHEET_NAME)
        
        if not admins_data or len(admins_data) < 2:  # Precisa ter cabeçalho e pelo menos um admin
            return False
            
        # Verificar se o nome do usuário está na lista de admins
        admin_names = [row[0] for row in admins_data[1:]]  # Pula o cabeçalho
        return user_name.lower() in [name.lower() for name in admin_names]
        
    except Exception as e:
        st.error(f"Erro ao verificar permissões de administrador: {str(e)}")
        return False

def check_admin_permission():
    """Verifica se o usuário tem permissão de administrador e mostra mensagem de erro se não tiver"""
    if not is_admin():
        st.error("Você não tem permissão para realizar esta ação. Apenas administradores podem editar dados.")
        return False
    return True





