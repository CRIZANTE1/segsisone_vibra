import streamlit as st
import sys
import os

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Importa as funções do seu script de notificação
from email_notifier import load_email_config, categorize_trainings, format_email_body, send_notification_email
from operations.employee import EmployeeManager
from auth.auth_utils import check_admin_permission

st.set_page_config(page_title="Notificações", page_icon="📧", layout="centered")

st.title("📧 Envio de Notificações de Vencimento")

# Garante que apenas administradores possam ver e usar esta página
if not check_admin_permission():
    st.error("Você não tem permissão para acessar esta página.")
    st.stop()

st.info("Esta página permite enviar manualmente o relatório de vencimentos de treinamentos por e-mail.")

# Inicializa o EmployeeManager
if 'employee_manager' not in st.session_state:
    st.session_state.employee_manager = EmployeeManager()

employee_manager = st.session_state.employee_manager

# Carrega e exibe um preview dos dados que serão enviados
try:
    st.subheader("Pré-visualização do Relatório")
    
    with st.spinner("Analisando vencimentos..."):
        categorized_data = categorize_trainings(employee_manager)
        html_body = format_email_body(categorized_data)

    if not any(not df.empty for df in categorized_data.values()):
        st.success("Nenhuma pendência encontrada! Todos os treinamentos estão em dia.")
    else:
        # Mostra o corpo do e-mail como uma prévia na página
        with st.container(height=400):
            st.html(html_body)

    st.markdown("---")

    if st.button("🚀 Enviar Relatório por E-mail", type="primary"):
        try:
            with st.spinner("Enviando e-mail..."):
                config = load_email_config()
                send_notification_email(html_body, config)
            st.success("E-mail de notificação enviado com sucesso!")
        except Exception as e:
            st.error(f"Ocorreu um erro ao enviar o e-mail: {e}")

except Exception as e:
    st.error(f"Ocorreu um erro ao gerar o relatório: {e}")
    st.info("Verifique se as credenciais do Google Sheets e do e-mail estão configuradas corretamente nos Secrets.")

def not_gat():
  # Verifique se o gatilho está nos query params da URL
    query_params = st.query_params
    # Carregue o trigger_secret dos seus secrets do Streamlit
    trigger_secret = st.secrets.get("scheduler", {}).get("TRIGGER_SECRET")

    if trigger_secret and query_params.get("trigger") == trigger_secret:
        st.success("Gatilho de e-mail recebido! Iniciando envio.")
        try:
            from email_notifier import load_email_config, categorize_trainings, format_email_body, send_notification_email
            
            config = load_email_config()
            employee_manager = st.session_state.employee_manager # Reutiliza o manager já iniciado
            
            categorized_data = categorize_trainings(employee_manager)
            
            if any(not df.empty for df in categorized_data.values()):
                email_body = format_email_body(categorized_data)
                send_notification_email(email_body, config)
                st.info("E-mail enviado.")
            else:
                st.info("Nenhuma pendência, e-mail não enviado.")

        except Exception as e:
            st.error(f"Erro no gatilho de e-mail: {e}")
