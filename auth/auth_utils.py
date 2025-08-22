import streamlit as st
from operations.matrix_manager import MatrixManager # Import the new manager

def is_oidc_available():
    """Verifica se o login OIDC está configurado e disponível."""
    return hasattr(st, 'user') and hasattr(st.user, 'is_logged_in')

def is_user_logged_in():
    """Verifica se o usuário está logado."""
    return is_oidc_available() and st.user.is_logged_in

def get_user_email() -> str | None:
    """Retorna o e-mail do usuário logado."""
    if is_user_logged_in() and hasattr(st.user, 'email'):
        return st.user.email.lower().strip()
    return None

def get_user_display_name() -> str:
    """Retorna o nome de exibição do usuário."""
    if is_user_logged_in() and hasattr(st.user, 'name'):
        return st.user.name
    return get_user_email() or "Usuário Desconhecido"

def authenticate_user() -> bool:
    """
    Verifica o usuário na Planilha Matriz, busca as informações do seu tenant
    e as armazena na sessão. Esta função é o coração da arquitetura multi-tenant.
    """
    user_email = get_user_email()
    if not user_email:
        return False

    # Se já autenticado E um contexto de unidade já foi definido (pelo Super Admin ou login normal),
    # não faz nada. Isso permite que o Super Admin troque de contexto.
    if st.session_state.get('authenticated') and st.session_state.get('unit_name') is not None:
        return True

    matrix_manager = MatrixManager()
    user_info = matrix_manager.get_user_info(user_email)

    if not user_info:
        st.error(f"Seu e-mail ({user_email}) não foi encontrado na lista de usuários autorizados.")
        st.stop()
        return False

    unit_name = user_info.get('unidade_associada')
    role = user_info.get('role', 'viewer')

    # Admin global tem acesso a tudo, mas não tem uma planilha específica neste contexto.
    # O painel de Super Admin cuidará de sua lógica.
    if unit_name == '*':
        st.session_state.role = 'admin'
        st.session_state.unit_name = 'Global'
        st.session_state.spreadsheet_id = None # Admins globais não têm uma planilha de tenant
        st.session_state.folder_id = None
        st.session_state.authenticated = True
        return True

    unit_info = matrix_manager.get_unit_info(unit_name)
    if not unit_info:
        st.error(f"A unidade '{unit_name}' associada ao seu usuário não foi encontrada.")
        st.stop()
        return False

    st.session_state.role = role
    st.session_state.unit_name = unit_info.get('nome_unidade')
    st.session_state.spreadsheet_id = unit_info.get('spreadsheet_id')
    st.session_state.folder_id = unit_info.get('folder_id')
    st.session_state.authenticated = True

    return True

def get_user_role() -> str:
    """Retorna o papel (role) do usuário da sessão."""
    return st.session_state.get('role', 'viewer')

def is_admin() -> bool:
    """Verifica se o usuário tem o papel de 'admin'."""
    return get_user_role() == 'admin'

def can_edit() -> bool:
    """Verifica se o usuário tem permissão para editar."""
    return get_user_role() in ['admin', 'editor']

def check_permission(level: str = 'editor'):
    """Verifica o nível de permissão e bloqueia a página se não for atendido."""
    if level == 'admin':
        if not is_admin():
            st.error("Acesso restrito a Administradores.")
            st.stop()
    elif level == 'editor':
        if not can_edit():
            st.error("Você não tem permissão para editar. Contate um administrador.")
            st.stop()