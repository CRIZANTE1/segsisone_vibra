import os
import sys
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta
import pandas as pd

# Adiciona o diretório raiz ao path para encontrar os módulos
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from operations.employee import EmployeeManager
from operations.company_docs import CompanyDocsManager
from gdrive.matrix_manager import MatrixManager

def get_smtp_config_from_env():
    """Lê a configuração SMTP a partir de variáveis de ambiente."""
    config = {
        "smtp_server": "smtp.gmail.com", 
        "smtp_port": 465, 
        "sender_email": os.getenv("SENDER_EMAIL"),
        "sender_password": os.getenv("SENDER_PASSWORD"),
        "receiver_email": os.getenv("RECEIVER_EMAIL")
    }
    if not all([config["sender_email"], config["sender_password"], config["receiver_email"]]):
        missing = [key for key, value in config.items() if not value and ("email" in key or "password" in key)]
        raise ValueError(f"Variáveis de ambiente de e-mail ausentes: {', '.join(missing)}. Verifique os Secrets.")
    return config

def categorize_expirations_for_unit(employee_manager: EmployeeManager, docs_manager: CompanyDocsManager):
    """
    Categoriza os vencimentos para uma única unidade com a lógica de ASO corrigida.
    """
    today = date.today()
    
    active_companies = employee_manager.companies_df[employee_manager.companies_df['status'].str.lower() == 'ativo']
    active_employees = employee_manager.employees_df[
        (employee_manager.employees_df['status'].str.lower() == 'ativo') &
        (employee_manager.employees_df['empresa_id'].isin(active_companies['id']))
    ]

    # --- Processamento de Treinamentos ---
    trainings_actives = employee_manager.training_df[employee_manager.training_df['funcionario_id'].isin(active_employees['id'])]
    latest_trainings = pd.DataFrame()
    if not trainings_actives.empty:
        latest_trainings = trainings_actives.sort_values('data', ascending=False).groupby(['funcionario_id', 'norma']).head(1).copy()
        latest_trainings['vencimento_dt'] = latest_trainings['vencimento'].dt.date
        latest_trainings.dropna(subset=['vencimento_dt'], inplace=True)
        
    # --- Processamento de ASOs ---
    asos_actives = employee_manager.aso_df[employee_manager.aso_df['funcionario_id'].isin(active_employees['id'])]
    latest_asos = pd.DataFrame()
    if not asos_actives.empty:
        aptitude_asos = asos_actives[~asos_actives['tipo_aso'].str.lower().isin(['demissional'])].copy()
        if not aptitude_asos.empty:
            latest_asos = aptitude_asos.sort_values('data_aso', ascending=False).groupby('funcionario_id').head(1).copy()
            latest_asos['vencimento_dt'] = latest_asos['vencimento'].dt.date
            latest_asos.dropna(subset=['vencimento_dt'], inplace=True)

    # --- Processamento de Documentos da Empresa ---
    docs_actives = docs_manager.docs_df[docs_manager.docs_df['empresa_id'].isin(active_companies['id'])]
    latest_company_docs = pd.DataFrame()
    if not docs_actives.empty:
        latest_company_docs = docs_actives.sort_values('data_emissao', ascending=False).groupby(['empresa_id', 'tipo_documento']).head(1).copy()
        latest_company_docs['vencimento_dt'] = latest_company_docs['vencimento'].dt.date
        latest_company_docs.dropna(subset=['vencimento_dt'], inplace=True)

    # --- Filtros de Vencimento ---
    vencidos_tr = latest_trainings[latest_trainings['vencimento_dt'] < today]
    vence_15_tr = latest_trainings[(latest_trainings['vencimento_dt'] >= today) & (latest_trainings['vencimento_dt'] <= today + timedelta(days=15))]
    vence_45_tr = latest_trainings[(latest_trainings['vencimento_dt'] > today + timedelta(days=15)) & (latest_trainings['vencimento_dt'] <= today + timedelta(days=45))]
    
    vencidos_aso = latest_asos[latest_asos['vencimento_dt'] < today]
    vence_15_aso = latest_asos[(latest_asos['vencimento_dt'] >= today) & (latest_asos['vencimento_dt'] <= today + timedelta(days=15))]
    vence_45_aso = latest_asos[(latest_asos['vencimento_dt'] > today + timedelta(days=15)) & (latest_asos['vencimento_dt'] <= today + timedelta(days=45))]

    vencidos_docs = latest_company_docs[latest_company_docs['vencimento_dt'] < today]
    vence_30_docs = latest_company_docs[(latest_company_docs['vencimento_dt'] >= today) & (latest_company_docs['vencimento_dt'] <= today + timedelta(days=30))]

    # --- Adiciona informações de nome/empresa ---
    if not active_employees.empty:
        employee_id_to_name = active_employees.set_index('id')['nome']
        employee_id_to_company_name = active_employees.set_index('id')['empresa_id'].map(active_companies.set_index('id')['nome'])

        for df in [vencidos_tr, vence_15_tr, vence_45_tr, vencidos_aso, vence_15_aso, vence_45_aso]:
            if not df.empty:
                df.loc[:, 'nome_funcionario'] = df['funcionario_id'].map(employee_id_to_name)
                df.loc[:, 'empresa'] = df['funcionario_id'].map(employee_id_to_company_name)

    if not active_companies.empty:
        for df in [vencidos_docs, vence_30_docs]:
            if not df.empty:
                df.loc[:, 'empresa'] = df['empresa_id'].map(active_companies.set_index('id')['nome'])

    return {
        "Treinamentos Vencidos": vencidos_tr, "Treinamentos que vencem em até 15 dias": vence_15_tr, "Treinamentos que vencem entre 16 e 45 dias": vence_45_tr,
        "ASOs Vencidos": vencidos_aso, "ASOs que vencem em até 15 dias": vence_15_aso, "ASOs que vencem entre 16 e 45 dias": vence_45_aso,
        "Documentos da Empresa Vencidos": vencidos_docs, "Documentos da Empresa que vencem nos próximos 30 dias": vence_30_docs,
    }

def format_email_body(categorized_data: dict) -> str:
    html_style = """
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; }
        .container { max-width: 950px; margin: 20px auto; padding: 20px; background-color: #ffffff; border-radius: 8px; }
        h1 { font-size: 24px; text-align: center; }
        h2 { font-size: 18px; color: #34495e; margin-top: 35px; border-bottom: 2px solid #e0e0e0; padding-bottom: 5px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 25px; font-size: 13px; }
        th, td { border: 1px solid #dddddd; padding: 8px 12px; text-align: left; }
        th { background-color: #f2f2f2; }
        .footer { margin-top: 30px; font-size: 12px; color: #666; text-align: center; }
    </style>
    """
    html_body = f"""
    <html><head>{html_style}</head><body><div class="container">
    <h1>Relatório de Vencimentos - SEGMA-SIS (Consolidado)</h1>
    <p style="text-align:center;">Relatório automático gerado em {date.today().strftime('%d/%m/%Y')}</p>
    """
    has_content = False
    
    report_order = [
        "Documentos da Empresa Vencidos", "ASOs Vencidos", "Treinamentos Vencidos",
        "Documentos da Empresa que vencem nos próximos 30 dias",
        "ASOs que vencem em até 15 dias", "Treinamentos que vencem em até 15 dias",
        "ASOs que vencem entre 16 e 45 dias", "Treinamentos que vencem entre 16 e 45 dias"
    ]

    report_configs = {
        "Documentos da Empresa Vencidos": {"cols": ['unidade', 'empresa', 'tipo_documento', 'vencimento']},
        "Documentos da Empresa que vencem nos próximos 30 dias": {"cols": ['unidade', 'empresa', 'tipo_documento', 'vencimento']},
        "ASOs Vencidos": {"cols": ['unidade', 'empresa', 'nome_funcionario', 'tipo_aso', 'vencimento']},
        "Treinamentos Vencidos": {"cols": ['unidade', 'empresa', 'nome_funcionario', 'norma', 'vencimento']},
        "ASOs que vencem em até 15 dias": {"cols": ['unidade', 'empresa', 'nome_funcionario', 'tipo_aso', 'vencimento']},
        "Treinamentos que vencem em até 15 dias": {"cols": ['unidade', 'empresa', 'nome_funcionario', 'norma', 'vencimento']},
        "ASOs que vencem entre 16 e 45 dias": {"cols": ['unidade', 'empresa', 'nome_funcionario', 'tipo_aso', 'vencimento']},
        "Treinamentos que vencem entre 16 e 45 dias": {"cols": ['unidade', 'empresa', 'nome_funcionario', 'norma', 'vencimento']},
    }
    
    for title in report_order:
        if title in categorized_data and not categorized_data[title].empty:
            data_df = categorized_data[title]
            has_content = True
            config = report_configs.get(title, {})
            html_body += f'<h2>{title} ({len(data_df)})</h2>'
            
            df_display = data_df.copy()
            if 'vencimento' in df_display.columns:
                df_display['vencimento'] = pd.to_datetime(df_display['vencimento'], dayfirst=True).dt.strftime('%d/%m/%Y')

            cols_to_show = [col for col in config.get("cols", df_display.columns) if col in df_display.columns]
            html_body += df_display[cols_to_show].to_html(index=False, border=0, na_rep='N/A')
            
    if not has_content:
        html_body += "<h2>Nenhuma pendência encontrada!</h2><p>Todos os documentos de todas as unidades estão em dia.</p>"
    
    # Adiciona rodapé sem identificar o remetente
    html_body += """
    <div class="footer">
        <hr>
        <p>Este é um e-mail automático do sistema SEGMA-SIS. Por favor, não responda.</p>
        <p>Para dúvidas sobre este relatório, entre em contato com o administrador do sistema.</p>
    </div>
    """
    
    html_body += "</div></body></html>"
    return html_body

def send_smtp_email(html_body: str, config: dict):
    message = MIMEMultipart("alternative")
    # Configurar o e-mail como "noreply" sem identificar o remetente
    message["Subject"] = f"Relatório de Vencimentos SEGMA-SIS - {date.today().strftime('%d/%m/%Y')}"
    message["From"] = f"SEGMA-SIS Sistema <{config['sender_email']}>"
    message["To"] = config["receiver_email"]
    message["Reply-To"] = "noreply@exemplo.com"  # E-mail fictício para noreply
    
    message.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        print(f"Conectando ao servidor SMTP {config['smtp_server']}...")
        with smtplib.SMTP_SSL(config["smtp_server"], config["smtp_port"], context=context) as server:
            print("Fazendo login...")
            server.login(config["sender_email"], config["sender_password"])
            print(f"Enviando e-mail para {config['receiver_email']}...")
            server.sendmail(config["sender_email"], config["receiver_email"].split(','), message.as_string())
            print("E-mail enviado com sucesso!")
    except Exception as e:
        print(f"Falha ao enviar e-mail via SMTP: {e}")
        raise

def main():
    """Função principal que itera sobre todas as unidades e envia um único e-mail consolidado."""
    print("Iniciando script de notificação de vencimentos...")
    try:
        config = get_smtp_config_from_env()
        
        matrix_manager = MatrixManager()
        all_units = matrix_manager.get_all_units()
        
        all_units_categorized_data = {}
        
        for unit in all_units:
            unit_name, spreadsheet_id, folder_id = unit.get('nome_unidade'), unit.get('spreadsheet_id'), unit.get('folder_id')
            if not spreadsheet_id:
                print(f"AVISO: Unidade '{unit_name}' sem spreadsheet_id. Pulando.")
                continue
            
            print(f"\n--- Processando unidade: {unit_name} ---")
            
            # CORREÇÃO: Adicionar o folder_id ou usar uma string vazia como fallback
            employee_manager = EmployeeManager(spreadsheet_id, folder_id or "")
            docs_manager = CompanyDocsManager(spreadsheet_id, folder_id or "")
            
            categorized_data = categorize_expirations_for_unit(employee_manager, docs_manager)
            
            for category in categorized_data.values():
                if not category.empty:
                    category['unidade'] = unit_name
            
            all_units_categorized_data[unit_name] = categorized_data

        consolidated_data = {}
        for unit_name, unit_data in all_units_categorized_data.items():
            for category_name, df in unit_data.items():
                if category_name not in consolidated_data:
                    consolidated_data[category_name] = []
                if not df.empty:
                    consolidated_data[category_name].append(df)
        
        final_report_data = {
            name: pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
            for name, dfs in consolidated_data.items()
        }

        if not any(not df.empty for df in final_report_data.values()):
            print("Nenhuma pendência encontrada em todas as unidades. E-mail não será enviado.")
        else:
            print("Pendências encontradas, gerando e-mail consolidado.")
            email_body = format_email_body(final_report_data)
            send_smtp_email(email_body, config)
        
        print("Script finalizado com sucesso.")

    except Exception as e:
        print(f"Erro fatal no script: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
