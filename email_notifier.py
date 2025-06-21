import os
import sys
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta
import pandas as pd

# Adiciona o diretório raiz ao PYTHONPATH para encontrar os módulos do projeto
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# A importação do EmployeeManager é a única dependência de código do seu projeto
from operations.employee import EmployeeManager

# --- FUNÇÕES DE LÓGICA ---

def get_smtp_config_from_env():
    """Lê a configuração SMTP a partir de variáveis de ambiente."""
    
    config = {
        "smtp_server": "smtp.gmail.com", # Fixo para o Gmail
        "smtp_port": 465, # Porta para conexão SSL
        "sender_email": os.getenv("SENDER_EMAIL"),
        "sender_password": os.getenv("SENDER_PASSWORD"),
        "receiver_email": os.getenv("RECEIVER_EMAIL")
    }
    
    # Valida se as credenciais de e-mail foram encontradas no ambiente
    if not all([config["sender_email"], config["sender_password"], config["receiver_email"]]):
        missing = [key for key, value in config.items() if not value and "email" in key or "password" in key]
        raise ValueError(f"Variáveis de ambiente de e-mail ausentes: {', '.join(missing)}. Verifique os Secrets do GitHub.")
        
    return config

def categorize_expirations(employee_manager: EmployeeManager):
    """Carrega e categoriza TODOS os documentos (treinamentos, ASOs e docs da empresa) por data de vencimento."""
    
    today = date.today()
    
    # --- Processamento de Treinamentos ---
    trainings_df = employee_manager.training_df.copy()
    categorized_trainings = {}
    if not trainings_df.empty:
        trainings_df['vencimento_dt'] = pd.to_datetime(trainings_df['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        trainings_df.dropna(subset=['vencimento_dt'], inplace=True)
        
        vencidos_tr = trainings_df[trainings_df['vencimento_dt'] < today]
        vence_15_tr = trainings_df[(trainings_df['vencimento_dt'] >= today) & (trainings_df['vencimento_dt'] <= today + timedelta(days=15))]
        vence_30_tr = trainings_df[(trainings_df['vencimento_dt'] > today + timedelta(days=15)) & (trainings_df['vencimento_dt'] <= today + timedelta(days=30))]
        vence_60_tr = trainings_df[(trainings_df['vencimento_dt'] > today + timedelta(days=30)) & (trainings_df['vencimento_dt'] <= today + timedelta(days=60))]
        vence_90_tr = trainings_df[(trainings_df['vencimento_dt'] > today + timedelta(days=60)) & (trainings_df['vencimento_dt'] <= today + timedelta(days=90))]
        
        dfs_to_process_tr = [vencidos_tr, vence_15_tr, vence_30_tr, vence_60_tr, vence_90_tr]
        for df in dfs_to_process_tr:
            if not df.empty:
                df['nome_funcionario'] = df['funcionario_id'].apply(employee_manager.get_employee_name)
                df['empresa'] = df['funcionario_id'].apply(
                    lambda fid: employee_manager.get_company_name(
                        employee_manager.employees_df[employee_manager.employees_df['id'] == str(fid)]['empresa_id'].iloc[0]
                    ) if not employee_manager.employees_df[employee_manager.employees_df['id'] == str(fid)].empty else 'N/A'
                )
        
        categorized_trainings = {
            "Treinamentos Vencidos": vencidos_tr,
            "Treinamentos que vencem em até 15 dias": vence_15_tr,
            "Treinamentos que vencem entre 16 e 30 dias": vence_30_tr,
            "Treinamentos que vencem entre 31 e 60 dias": vence_60_tr,
            "Treinamentos que vencem entre 61 e 90 dias": vence_90_tr,
        }

    # --- Processamento de ASOs ---
    asos_df = employee_manager.aso_df.copy()
    categorized_asos = {}
    if not asos_df.empty:
        asos_df['vencimento_dt'] = pd.to_datetime(asos_df['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        asos_df.dropna(subset=['vencimento_dt'], inplace=True)

        vencidos_aso = asos_df[asos_df['vencimento_dt'] < today]
        vence_15_aso = asos_df[(asos_df['vencimento_dt'] >= today) & (asos_df['vencimento_dt'] <= today + timedelta(days=15))]
        vence_30_aso = asos_df[(asos_df['vencimento_dt'] > today + timedelta(days=15)) & (asos_df['vencimento_dt'] <= today + timedelta(days=30))]
        
        dfs_to_process_aso = [vencidos_aso, vence_15_aso, vence_30_aso]
        for df in dfs_to_process_aso:
             if not df.empty:
                df['nome_funcionario'] = df['funcionario_id'].apply(employee_manager.get_employee_name)
                df['empresa'] = df['funcionario_id'].apply(
                    lambda fid: employee_manager.get_company_name(
                        employee_manager.employees_df[employee_manager.employees_df['id'] == str(fid)]['empresa_id'].iloc[0]
                    ) if not employee_manager.employees_df[employee_manager.employees_df['id'] == str(fid)].empty else 'N/A'
                )
        
        categorized_asos = {
            "ASOs Vencidos": vencidos_aso,
            "ASOs que vencem em até 15 dias": vence_15_aso,
            "ASOs que vencem entre 16 e 30 dias": vence_30_aso,
        }

    # --- Processamento de Documentos da Empresa ---
    from operations.company_docs import CompanyDocsManager
    docs_manager = CompanyDocsManager()
    company_docs_df = docs_manager.docs_df.copy()
    categorized_company_docs = {}
    
    if not company_docs_df.empty:
        company_docs_df['vencimento_dt'] = pd.to_datetime(company_docs_df['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        company_docs_df.dropna(subset=['vencimento_dt'], inplace=True)

        vencidos_docs = company_docs_df[company_docs_df['vencimento_dt'] < today]
        vence_30_docs = company_docs_df[(company_docs_df['vencimento_dt'] >= today) & (company_docs_df['vencimento_dt'] <= today + timedelta(days=30))]
        
        for df in [vencidos_docs, vence_30_docs]:
            if not df.empty:
                df['empresa'] = df['empresa_id'].apply(employee_manager.get_company_name)
        
        categorized_company_docs = {
            "Documentos da Empresa Vencidos": vencidos_docs,
            "Documentos da Empresa que vencem nos próximos 30 dias": vence_30_docs,
        }

    # Combina todos os resultados em um único dicionário para o e-mail
    all_categorized_data = {**categorized_trainings, **categorized_asos, **categorized_company_docs}
    return all_categorized_data

def format_email_body(categorized_data: dict) -> str:
    """Cria o corpo do e-mail em HTML com todas as categorias de vencimento."""
    html = """
    <html><head><style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; margin: 0; padding: 0; background-color: #f4f4f4; }
        .container { padding: 20px; }
        h1 { color: #0d47a1; text-align: center; }
        h2 { color: #1565c0; border-bottom: 2px solid #90caf9; padding-bottom: 5px; margin-top: 30px;}
        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; box-shadow: 0 2px 3px rgba(0,0,0,0.1); background-color: white; }
        th, td { border: 1px solid #e0e0e0; padding: 10px; text-align: left; }
        th { background-color: #1e88e5; color: white; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .vencido { color: #d32f2f; font-weight: bold; }
        .vence-15 { color: #e65100; font-weight: bold; }
        .vence-30 { color: #f57c00; font-weight: bold; }
        .vence-60 { color: #fbc02d; }
        .vence-90 { color: #7cb342; }
    </style></head><body><div class="container">
    <h1>Relatório de Vencimentos - SEGMA-SIS</h1>
    <p style="text-align: center;">Relatório automático gerado em """ + date.today().strftime('%d/%m/%Y') + """.</p>
    """
    has_content = False
    
    report_configs = {
        "Documentos da Empresa Vencidos": {"class": "vencido", "cols": ['empresa', 'tipo_documento', 'vencimento']},
        "Documentos da Empresa que vencem nos próximos 30 dias": {"class": "vence-30", "cols": ['empresa', 'tipo_documento', 'vencimento']},
        "Treinamentos Vencidos": {"class": "vencido", "cols": ['empresa', 'nome_funcionario', 'norma', 'modulo', 'vencimento']},
        "ASOs Vencidos": {"class": "vencido", "cols": ['empresa', 'nome_funcionario', 'tipo_aso', 'cargo', 'vencimento']},
        "Treinamentos que vencem em até 15 dias": {"class": "vence-15", "cols": ['empresa', 'nome_funcionario', 'norma', 'modulo', 'vencimento']},
        "ASOs que vencem em até 15 dias": {"class": "vence-15", "cols": ['empresa', 'nome_funcionario', 'tipo_aso', 'cargo', 'vencimento']},
        "Treinamentos que vencem entre 16 e 30 dias": {"class": "vence-30", "cols": ['empresa', 'nome_funcionario', 'norma', 'modulo', 'vencimento']},
        "ASOs que vencem entre 16 e 30 dias": {"class": "vence-30", "cols": ['empresa', 'nome_funcionario', 'tipo_aso', 'cargo', 'vencimento']},
        "Treinamentos que vencem entre 31 e 60 dias": {"class": "vence-60", "cols": ['empresa', 'nome_funcionario', 'norma', 'modulo', 'vencimento']},
        "Treinamentos que vencem entre 61 e 90 dias": {"class": "vence-90", "cols": ['empresa', 'nome_funcionario', 'norma', 'modulo', 'vencimento']},
    }

    display_order = [
        "Documentos da Empresa Vencidos", "Treinamentos Vencidos", "ASOs Vencidos",
        "Documentos da Empresa que vencem nos próximos 30 dias",
        "Treinamentos que vencem em até 15 dias", "ASOs que vencem em até 15 dias",
        "Treinamentos que vencem entre 16 e 30 dias", "ASOs que vencem entre 16 e 30 dias",
        "Treinamentos que vencem entre 31 e 60 dias", "Treinamentos que vencem entre 61 e 90 dias",
    ]

    for title in display_order:
        if title in categorized_data and not categorized_data[title].empty:
            has_content = True
            df = categorized_data[title]
            config = report_configs[title]
            html += f'<h2 class="{config["class"]}">{title} ({len(df)})</h2>'
            cols_to_show = [col for col in config["cols"] if col in df.columns]
            df_display = df[cols_to_show]
            html += df_display.to_html(index=False, border=0, na_rep='N/A', classes='table table-striped')
    
    if not has_content:
        html += "<h2>Nenhuma pendência encontrada!</h2><p>Todos os documentos estão em dia para os próximos 90 dias.</p>"
        
    html += "</div></body></html>"
    return html

def send_smtp_email(html_body: str, config: dict):
    """Envia o e-mail formatado usando SMTP e Senha de App."""
    
    message = MIMEMultipart("alternative")
    message["Subject"] = f"Alerta de Vencimentos - SEGMA-SIS - {date.today().strftime('%d/%m/%Y')}"
    message["From"] = config["sender_email"]
    message["To"] = config["receiver_email"]
    message.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        print(f"Conectando ao servidor SMTP {config['smtp_server']}...")
        with smtplib.SMTP_SSL(config["smtp_server"], config["smtp_port"], context=context) as server:
            print("Fazendo login...")
            server.login(config["sender_email"], config["sender_password"])
            print("Enviando e-mail...")
            server.sendmail(config["sender_email"], config["receiver_email"], message.as_string())
            print("E-mail enviado com sucesso!")
    except Exception as e:
        print(f"Falha ao enviar e-mail via SMTP: {e}")
        raise

def main():
    """Função principal do script, executada pela GitHub Action."""
    print("Iniciando script de notificação...")
    try:
        config = get_smtp_config_from_env()
        
        # A inicialização do EmployeeManager aciona a cadeia de dependências
        # que lê as credenciais do Google Sheets a partir das variáveis de ambiente.
        employee_manager = EmployeeManager()
        categorized_data = categorize_expirations(employee_manager)

        if not any(not df.empty for df in categorized_data.values()):
            print("Nenhuma pendência encontrada. E-mail não será enviado.")
        else:
            email_body = format_email_body(categorized_data)
            send_smtp_email(email_body, config)
        
        print("Script finalizado com sucesso.")

    except Exception as e:
        print(f"Erro fatal no script: {e}")
        # Termina com código de erro 1 para a GitHub Action falhar e notificar o erro
        sys.exit(1) 

if __name__ == "__main__":
    main()
