import streamlit as st
import sys
import os

# Adiciona o diretório raiz ao PYTHONPATH
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Importa SOMENTE o necessário para o envio de e-mail
from email_notifier import load_email_config, categorize_expirations, format_email_body, send_notification_email
from operations.employee import EmployeeManager

def handle_webhook():
    """
    Este script é o endpoint exclusivo para o gatilho.
    Ele não renderiza UI, apenas executa a lógica de notificação.
    """
    st.set_page_config(layout="centered")
    st.title("Webhook Handler")
    st.write("Processando requisição...")

    try:
        config = load_email_config()
        employee_manager = EmployeeManager()
        categorized_data = categorize_expirations(employee_manager)

        if not any(not df.empty for df in categorized_data.values()):
            st.success("Nenhuma pendência encontrada. E-mail não será enviado.")
        else:
            email_body = format_email_body(categorized_data)
            send_notification_email(email_body, config)
            st.success("E-mail de relatório enviado com sucesso!")

    except Exception as e:
        st.error(f"Erro durante a execução do webhook: {e}")

if __name__ == "__main__":
    handle_webhook()
