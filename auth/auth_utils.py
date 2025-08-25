import streamlit as st
from gdrive.matrix_manager import MatrixManager

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
    Verifica o usuário na Planilha Matriz, carrega o contexto do tenant,
    armazena as informações na sessão e registra o evento de login.
    Esta função é a única fonte da verdade para as permissões.
    """
    user_email = get_user_email()
    if not user_email:
        return False

    # Se o usuário já foi autenticado nesta sessão, não faz nada.
    if st.session_state.get('authenticated_user_email') == user_email:
        return True

    # Usa o MatrixManager para buscar informações na planilha de controle global.
    matrix_manager = MatrixManager()
    user_info = matrix_manager.get_user_info(user_email)

    if not user_info:
        st.error(f"Acesso negado. Seu e-mail ({user_email}) não está autorizado a usar este sistema.")
        st.session_state.clear() # Limpa a sessão para segurança
        return False

    # Armazena as informações do usuário na sessão.
    st.session_state.role = user_info.get('role', 'viewer') # Padrão de segurança
    unit_name = user_info.get('unidade_associada')

    if unit_name == '*':
        st.session_state.unit_name = 'Global'
        st.session_state.spreadsheet_id = None
        st.session_state.folder_id = None
    else:
        unit_info = matrix_manager.get_unit_info(unit_name)
        if not unit_info:
            st.error(f"Erro de configuração: A unidade '{unit_name}' associada ao seu usuário não foi encontrada na Planilha Matriz.")
            st.session_state.clear()
            return False
        st.session_state.unit_name = unit_info.get('nome_unidade')
        st.session_state.spreadsheet_id = unit_info.get('spreadsheet_id')
        st.session_state.folder_id = unit_info.get('folder_id')

    # Marca o usuário como autenticado para esta sessão.
    st.session_state.authenticated_user_email = user_email
    
    # --- FUNCIONALIDADE RESTAURADA AQUI ---
    # Importa a função de log e registra o evento de login bem-sucedido.
    from operations.audit_logger import log_action
    log_action(
        action="USER_LOGIN",
        details={
            "message": f"Usuário '{user_email}' logado com sucesso.",
            "assigned_role": st.session_state.role,
            "initial_unit": st.session_state.unit_name
        }
    )
    
    return True

def get_user_role() -> str:
    """
    Retorna o papel (role) do usuário que foi definido durante a autenticação.
    Se a autenticação ainda não ocorreu, retorna 'viewer' como padrão seguro.
    """

    return st.session_state.get('role', 'viewer')

def is_admin() -> bool:
    """Verifica se o usuário tem o papel de 'admin'."""
    return get_user_role() == 'admin'

def can_edit() -> bool:
    """Verifica se o usuário tem permissão para editar."""
    return get_user_role() in ['admin', 'editor']

def check_permission(level: str = 'editor'):
    """
    Verifica o nível de permissão e bloqueia a página se não for atendido.
    Retorna True se a permissão for concedida, para consistência.
    """
    if level == 'admin':
        if not is_admin():
            st.error("Acesso restrito a Administradores.")
            st.stop()
    elif level == 'editor':
        if not can_edit():
            st.error("Você não tem permissão para editar. Contate um administrador.")
            st.stop()
    return True
