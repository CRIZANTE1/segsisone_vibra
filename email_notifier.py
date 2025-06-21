import os
import sys
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta
import pandas as pd
import streamlit as st
import json

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Imports do seu projeto
from operations.employee import EmployeeManager
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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


def categorize_expirations(employee_manager: EmployeeManager):
    """Carrega e categoriza TODOS os documentos (treinamentos e ASOs) por data de vencimento."""
    
    today = date.today()
    
    # --- Processamento de Treinamentos ---
    trainings_df = employee_manager.training_df.copy()
    categorized_trainings = {}
    if not trainings_df.empty:
        trainings_df['vencimento_dt'] = pd.to_datetime(trainings_df['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        trainings_df.dropna(subset=['vencimento_dt'], inplace=True)
        
        vencidos_tr = trainings_df[trainings_df['vencimento_dt'] < today]
        vence_30_tr = trainings_df[(trainings_df['vencimento_dt'] >= today) & (trainings_df['vencimento_dt'] <= today + timedelta(days=30))]
        vence_60_tr = trainings_df[(trainings_df['vencimento_dt'] > today + timedelta(days=30)) & (trainings_df['vencimento_dt'] <= today + timedelta(days=60))]
        
        for df in [vencidos_tr, vence_30_tr, vence_60_tr]:
            if not df.empty:
                df['nome_funcionario'] = df['funcionario_id'].apply(employee_manager.get_employee_name)
                df['empresa'] = df['funcionario_id'].apply(
                    lambda fid: employee_manager.get_company_name(
                        employee_manager.employees_df[employee_manager.employees_df['id'] == str(fid)]['empresa_id'].iloc[0]
                    ) if not employee_manager.employees_df[employee_manager.employees_df['id'] == str(fid)].empty else 'N/A'
                )
        
        categorized_trainings = {
            "Treinamentos Vencidos": vencidos_tr,
            "Treinamentos que vencem nos próximos 30 dias": vence_30_tr,
            "Treinamentos que vencem entre 31 e 60 dias": vence_60_tr,
        }

    # --- Processamento de ASOs ---
    asos_df = employee_manager.aso_df.copy()
    categorized_asos = {}
    if not asos_df.empty:
        asos_df['vencimento_dt'] = pd.to_datetime(asos_df['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        asos_df.dropna(subset=['vencimento_dt'], inplace=True)

        # Filtra apenas os ASOs que vencem nos próximos 30 dias
        vence_30_aso = asos_df[(asos_df['vencimento_dt'] >= today) & (asos_df['vencimento_dt'] <= today + timedelta(days=30))]

        if not vence_30_aso.empty:
            vence_30_aso['nome_funcionario'] = vence_30_aso['funcionario_id'].apply(employee_manager.get_employee_name)
            vence_30_aso['empresa'] = vence_30_aso['funcionario_id'].apply(
                lambda fid: employee_manager.get_company_name(
                    employee_manager.employees_df[employee_manager.employees_df['id'] == str(fid)]['empresa_id'].iloc[0]
                ) if not employee_manager.employees_df[employee_manager.employees_df['id'] == str(fid)].empty else 'N/A'
            )
        
        categorized_asos = {
            "ASOs que vencem nos próximos 30 dias": vence_30_aso
        }

    # Combina os resultados dos dois dicionários
    all_categorized_data = {**categorized_trainings, **categorized_asos}
    
    return all_categorized_data


def format_email_body(categorized_data: dict) -> str:
    """Cria o corpo do e-mail em HTML a partir dos dados categorizados (Treinamentos e ASOs)."""
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
        .vence-30 { color: #f57c00; font-weight: bold; } /* Destaque para 30 dias */
        .vence-60 { color: #fbc02d; }
    </style></head><body>
    <h1>Relatório de Vencimentos - SEGMA-SIS</h1>
    <p>Relatório automático gerado em """ + date.today().strftime('%d/%m/%Y') + """.</p>
    """
    has_content = False
    
    report_configs = {
        "Treinamentos Vencidos": {"class": "vencidos", "cols": ['empresa', 'nome_funcionario', 'norma', 'modulo', 'vencimento']},
        "Treinamentos que vencem nos próximos 30 dias": {"class": "vence-30", "cols": ['empresa', 'nome_funcionario', 'norma', 'modulo', 'vencimento']},
        "ASOs que vencem nos próximos 30 dias": {"class": "vence-30", "cols": ['empresa', 'nome_funcionario', 'tipo_aso', 'cargo', 'vencimento']},
        "Treinamentos que vencem entre 31 e 60 dias": {"class": "vence-60", "cols": ['empresa', 'nome_funcionario', 'norma', 'modulo', 'vencimento']},
    }

    # Garante uma ordem de exibição lógica no e-mail
    display_order = [
        "Treinamentos Vencidos", 
        "Treinamentos que vencem nos próximos 30 dias", 
        "ASOs que vencem nos próximos 30 dias",
        "Treinamentos que vencem entre 31 e 60 dias"
    ]

    for title in display_order:
        if title in categorized_data and not categorized_data[title].empty:
            has_content = True
            df = categorized_data[title]
            config = report_configs[title]
            
            html += f'<h2 class="{config["class"]}">{title} ({len(df)})</h2>'
            
            cols_to_show = [col for col in config["cols"] if col in df.columns]
            df_display = df[cols_to_show]
            
            html += df_display.to_html(index=False, border=0, classes='table table-striped')
    
    if not has_content:
        html += "<h2>Nenhuma pendência encontrada!</h2><p>Todos os documentos estão em dia.</p>"
        
    html += "</body></html>"
    return html


def send_notification_email(html_body: str, config: dict):
    """Envia o e-mail formatado usando a API do Gmail com uma Conta de Serviço."""
    sender_email = config["sender_email"]
    receiver_email = config["receiver_email"]
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    
    try:
        # Reutiliza as credenciais da conta de serviço já configuradas para o gsheets
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
        message["Subject"] = f"Alerta de Vencimentos - SEGMA-SIS - {date.today().strftime('%d/%m/%Y')}"
        message.attach(MIMEText(html_body, "html"))

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        print("Enviando e-mail via API do Gmail...")
        send_message = (service.users().messages().send(userId="me", body=create_message).execute())
        print(f'E-mail enviado com sucesso. Message Id: {send_message["id"]}')

    except HttpError as error:
        print(f'Ocorreu um erro na API do Gmail: {error}')
        st.error(f'Ocorreu um erro na API do Gmail: {error}')
        raise
    except Exception as e:
        print(f"Falha ao enviar e-mail: {e}")
        st.error(f"Falha ao enviar e-mail: {e}")
        raise


def check_and_send_notification_trigger():
    """
    Verifica os query params da URL em busca de um gatilho secreto.
    Se encontrado, executa a rotina de envio de e-mail e PARA a execução do script.
    """
    try:
        query_params = st.query_params
        trigger_secret = st.secrets.get("scheduler", {}).get("trigger_secret")
       
        if not trigger_secret or query_params.get("trigger") != trigger_secret:
            return

        st.set_page_config(layout="centered")
        st.success("Gatilho de notificação recebido! Processando...")

        config = load_email_config()
        employee_manager = EmployeeManager()
        categorized_data = categorize_expirations(employee_manager)

        if not any(not df.empty for df in categorized_data.values()):
            st.info("Nenhuma pendência encontrada. E-mail não será enviado.")
        else:
            email_body = format_email_body(categorized_data)
            send_notification_email(email_body, config)
            st.info("E-mail de relatório enviado com sucesso!")

        st.stop()

    except Exception as e:
        st.error(f"Erro durante a execução do gatilho de notificação: {e}")
        st.stop()
