import streamlit as st
from .auth_utils import is_oidc_available, is_user_logged_in, get_user_display_name

def show_login_page():
        
    if not is_oidc_available():
        st.error("O sistema OIDC não está disponível!")
        st.markdown("""
        ### Requisitos para o Sistema de Login OIDC
        
        Para configurar corretamente o sistema de login OIDC:
        
        1. Verifique se o Streamlit está na versão 1.44.0 ou superior
        2. Confirme se a biblioteca Authlib está instalada (>= 1.3.2)
        3. Configure o arquivo `.streamlit/secrets.toml` com as credenciais corretas
        4. Gere um `cookie_secret` forte e aleatório
        
        O sistema agora requer OIDC para funcionar.
        """)
        return False
        
    if not is_user_logged_in():
        st.markdown("### Acesso ao Sistema")
        st.write("Por favor, faça login para acessar o sistema.")
        if st.button("Fazer Login com Google"):
            try:
                st.login()
            except Exception as e:
                st.error(f"Erro ao iniciar login: {str(e)}")
                st.warning("Verifique se as configurações OIDC estão corretas no arquivo secrets.toml")
        return False
        
    return True

def show_user_header():
    """Mostra o cabeçalho com informações do usuário"""
    st.write(f"Bem-vindo, {get_user_display_name()}!")
    
def show_sidebar():
    """Mostra e configura toda a barra lateral de forma minimalista."""
    with st.sidebar:
        st.title("SSO AI 🛡️")
        
        st.divider()

        st.write(f"Usuário:")
        st.info(f"**{get_user_display_name()}**")

        st.write("") 
        
        if st.button("Sair do Sistema", use_container_width=True):
            try:
                st.logout()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao fazer logout: {str(e)}")
                # Limpa o session_state como um fallback
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

        st.caption("v1.0.1")
