import smtplib
import ssl
import os
import sys
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta
import pandas as pd
from dotenv import load_dotenv
import streamlit as st
import json

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Importa o EmployeeManager do seu projeto.
# Este import deve ocorrer APÓS a configuração do sys.path.
from operations.employee import EmployeeManager
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Carrega as variáveis de ambiente (para execução local, se houver um .env)
load_dotenv()

# --- FUNÇÕES DE LÓGICA ---

def load_email_config():
    """Carrega a configuração de e-mail a partir dos Secrets do Streamlit."""
    try:
        config = {
            "sender_email": st.secrets.email.sender,
            "receiver_email": st.secrets.email.receiver,
        }
        # Valida se as configurações necessárias estão presentes
        if not all(config.values()):
            missing = [key for key, value in config.items() if not value]
            raise ValueError(f"Configurações de e-mail ausentes nos Secrets: {', '.join(missing)}")
        return config
    except (AttributeError, KeyError) as e:
        raise ValueError(f"Estrutura de Secrets para e-mail inválida. Verifique [email] em seu secrets.toml. Erro: {e}")


def categorize_trainings(employee_manager: EmployeeManager):
    """Carrega e categoriza os treinamentos por data de vencimento."""
    trainings_df = employee_manager.training_df.copy()
    if trainings_df.empty:
        return {}

    trainings_df['vencimento_dt'] = pd.to_datetime(trainings_df['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
    trainings_df.dropna(subset=['vencimento_dt'], inplace=True)

    today = date.today()
    
    vencidos = trainings_df[trainings_df['vencimento_dt'] < today]
    vence_30_dias = trainings_df[(trainings_df['vencimento_dt'] >= today) & (trainings_df['vencimento_dt'] <= today + timedelta(days=30))]
    vence_60_dias = trainings_df[(trainings_df['vencimento_dt'] > today + timedelta(days=30)) & (trainings_df['vencimento_dt'] <= today + timedelta(days=60))]

    for df in [vencidos, vence_30_dias, vence_60_dias]:
        if not df.empty:
            df['nome_funcionario'] = df['funcionario_id'].apply(employee_manager.get_employee_name)
            df['empresa'] = df['funcionario_id'].apply(
                lambda fid: employee_manager.get_company_name(
                    employee_manager.employees_df[employee_manager.employees_df['id'] == str(fid)]['empresa_id'].iloc[0]
                ) if not employee_manager.employees_df[employee_manager.employees_df['id'] == str(fid)].empty else 'N/A'
            )

    return {
        "Vencidos": vencidos,
        "Vencem nos próximos 30 dias": vence_30_dias,
        "Vencem entre 31 e 60 dias": vence_60_dias,
    }


def format_email_body(categorized_data: dict) -> str:
    """Cria o corpo do e-mail em HTML a partir dos dados categorizados."""
    html = """
    <html><head><style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; }
        h1 { color: #0d47a1; }
        h2 { color: #1565c0; border-bottom: 2px solid #90caf9; padding-bottom: 5px; margin-top: 30px;}
        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; box-shadow: 0 2px 3px rgba(0,0,0,0.1); }
        th, td { border: 1px solid #e0e0e0; padding: 10px; text-align: left; }
        th { background-color: #1e88e5; color: white; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .vencidos { color: #d32f2f; font-weight: bold; }
        .vence-30 { color: #f57c00; }
        .vence-60 { color: #fbc02d; }
    </style></head><body>
    <h1>Relatório de Vencimento de Treinamentos</h1>
    <p>Relatório automático gerado em """ + date.today().strftime('%d/%m/%Y') + """.</p>
    """
    has_content = False
    color_map = {"Vencidos": "vencidos", "Vencem nos próximos 30 dias": "vence-30", "Vencem entre 31 e 60 dias": "vence-60"}
    cols_to_show = ['empresa', 'nome_funcionario', 'norma', 'modulo', 'vencimento']

    for title, df in categorized_data.items():
        if not df.empty:
            has_content = True
            color_class = color_map.get(title, "")
            html += f'<h2 class="{color_class}">{title} ({len(df)})</h2>'
            df_display = df[[col for col in cols_to_show if col in df.columns]]
            html += df_display.to_html(index=False, border=0, classes='table table-striped')
    
    if not has_content:
        html += "<h2>Nenhuma pendência encontrada!</h2><p>Todos os treinamentos estão em dia.</p>"
        
    html += "</body></html>"
    return html


def send_notification_email(html_body: str, config: dict):
    """Envia o e-mail formatado usando a API do Gmail com uma Conta de Serviço."""
    sender_email = config["sender_email"]
    receiver_email = config["receiver_email"]
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    
    try:
        # Reutiliza as credenciais do gsheets, que é a mesma conta de serviço
        creds_dict = st.secrets.connections.gsheets
        
        creds = Credentials.from_service_account_info(
            creds_dict, 
            scopes=SCOPES,
            subject=sender_email
        )
        service = build('gmail', 'v1', credentials=creds)

        message = MIMEMultipart("alternative")
        message["To"] = receiver_email
        message["From"] = sender_email
        message["Subject"] = f"Alerta de Vencimentos de Treinamentos - {date.today().strftime('%d/%m/%Y')}"
        message.attach(MIMEText(html_body, "html"))

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        print("Enviando e-mail via API do Gmail...")
        send_message = (service.users().messages().send(userId="me", body=create_message).execute())
        print(f'E-mail enviado com sucesso. Message Id: {send_message["id"]}')

    except HttpError as error:
        print(f'Ocorreu um erro na API do Gmail: {error}')
        st.error(f'Ocorreu um erro na API do Gmail: {error}') # Mostra no log do Streamlit
        raise
    except Exception as e:
        print(f"Falha ao enviar e-mail: {e}")
        st.error(f"Falha ao enviar e-mail: {e}") # Mostra no log do Streamlit
        raise

def check_and_send_notification_trigger():
    """
    Verifica os query params da URL em busca de um gatilho secreto.
    Se encontrado, executa a rotina de envio de e-mail e PARA a execução do script.
    """
    try:
        query_params = st.query_params
        trigger_secret = st.secrets.get("scheduler", {}).get("trigger_secret")

        # Se o trigger_secret não estiver configurado ou não for correspondente, não faz nada.
        if not trigger_secret or query_params.get("trigger") != trigger_secret:
            return

        # --- GATILHO ACIONADO ---
        st.set_page_config(layout="centered") # Configura uma página mínima para a resposta
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

        # Para a execução para não renderizar a UI normal para o robô
        st.stop()

    except Exception as e:
        # Em caso de erro, exibe o erro e para.
        st.error(f"Erro durante a execução do gatilho de notificação: {e}")
        st.stop()
