import streamlit as st
from operations.employee import EmployeeManager
from email_notifier import load_email_config, categorize_trainings, format_email_body, send_notification_email
from operations.employee import EmployeeManager
from auth.auth_utils import check_admin_permission

def check_and_send_notification_trigger():
    """
    Verifica os query params da URL em busca de um gatilho secreto.
    Se encontrado, executa a rotina de envio de e-mail e PARA a execução do script.
    """
    try:
        query_params = st.query_params
        trigger_secret = st.secrets.get("scheduler", {}).get("TRIGGER_SECRET")

        if not trigger_secret or query_params.get("trigger") != trigger_secret:
            return # Não faz nada se o gatilho não estiver presente ou correto

        st.success("Gatilho de notificação recebido! Processando...")

        config = load_email_config()
        employee_manager = EmployeeManager()
        categorized_data = categorize_trainings(employee_manager)

        if not any(not df.empty for df in categorized_data.values()):
            st.info("Nenhuma pendência encontrada. E-mail não será enviado.")
        else:
            email_body = format_email_body(categorized_data)
            send_notification_email(email_body, config)
            st.info("E-mail de relatório enviado com sucesso!")

        # Para a execução para não renderizar a UI para o robô
        st.stop()

    except Exception as e:
        st.error(f"Erro durante a execução do gatilho de notificação: {e}")
        st.stop() # Para a execução em caso de erro também
