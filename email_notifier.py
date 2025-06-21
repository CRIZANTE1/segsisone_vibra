import os
import sys
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta
import pandas as pd
from operations.employee import EmployeeManager
from datetime import date 

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)



def get_smtp_config_from_env():
    """Lê a configuração SMTP a partir de variáveis de ambiente."""
    
    config = {
        "smtp_server": "smtp.gmail.com", 
        "smtp_port": 465, 
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
    """
    Carrega e categoriza os documentos mais recentes, alertando sobre vencimentos
    apenas se não houver um substituto válido.
    """
    
    today = date.today()
    
    # --- Processamento Inteligente de Treinamentos ---
    trainings_df = employee_manager.training_df.copy()
    latest_trainings = pd.DataFrame()
    if not trainings_df.empty:
        # Garante que a coluna 'modulo' exista para o agrupamento
        if 'modulo' not in trainings_df.columns:
            trainings_df['modulo'] = 'N/A'
        trainings_df['modulo'] = trainings_df['modulo'].fillna('N/A')
        
        trainings_df['data_dt'] = pd.to_datetime(trainings_df['data'], format='%d/%m/%Y', errors='coerce')
        trainings_df.dropna(subset=['data_dt'], inplace=True)
        
        # Agrupa por funcionário e tipo de treinamento, e pega apenas o mais recente de cada grupo
        latest_trainings = trainings_df.sort_values('data_dt', ascending=False).groupby(['funcionario_id', 'norma', 'modulo']).head(1)
        latest_trainings['vencimento_dt'] = pd.to_datetime(latest_trainings['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        latest_trainings.dropna(subset=['vencimento_dt'], inplace=True)
        
    # --- Processamento Inteligente de ASOs ---
    asos_df = employee_manager.aso_df.copy()
    latest_asos = pd.DataFrame()
    if not asos_df.empty:
        if 'tipo_aso' not in asos_df.columns:
            asos_df['tipo_aso'] = 'N/A'
        asos_df['tipo_aso'] = asos_df['tipo_aso'].fillna('N/A')

        asos_df['data_aso_dt'] = pd.to_datetime(asos_df['data_aso'], format='%d/%m/%Y', errors='coerce')
        asos_df.dropna(subset=['data_aso_dt'], inplace=True)
        
        # Agrupa por funcionário e tipo de ASO, e pega apenas o mais recente de cada grupo
        latest_asos = asos_df.sort_values('data_aso_dt', ascending=False).groupby(['funcionario_id', 'tipo_aso']).head(1)
        latest_asos['vencimento_dt'] = pd.to_datetime(latest_asos['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        latest_asos.dropna(subset=['vencimento_dt'], inplace=True)

    # --- Processamento Inteligente de Documentos da Empresa ---
    from operations.company_docs import CompanyDocsManager
    docs_manager = CompanyDocsManager()
    company_docs_df = docs_manager.docs_df.copy()
    latest_company_docs = pd.DataFrame()
    if not company_docs_df.empty:
        company_docs_df['data_emissao_dt'] = pd.to_datetime(company_docs_df['data_emissao'], format='%d/%m/%Y', errors='coerce')
        company_docs_df.dropna(subset=['data_emissao_dt'], inplace=True)

        # Agrupa por empresa e tipo de documento, e pega apenas o mais recente de cada grupo
        latest_company_docs = company_docs_df.sort_values('data_emissao_dt', ascending=False).groupby(['empresa_id', 'tipo_documento']).head(1)
        latest_company_docs['vencimento_dt'] = pd.to_datetime(latest_company_docs['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        latest_company_docs.dropna(subset=['vencimento_dt'], inplace=True)

    # --- Agora, filtramos os vencimentos APENAS dos documentos mais recentes ---
    
    # Filtros de Treinamentos
    vencidos_tr = latest_trainings[latest_trainings['vencimento_dt'] < today]
    vence_15_tr = latest_trainings[(latest_trainings['vencimento_dt'] >= today) & (latest_trainings['vencimento_dt'] <= today + timedelta(days=15))]
    vence_30_tr = latest_trainings[(latest_trainings['vencimento_dt'] > today + timedelta(days=15)) & (latest_trainings['vencimento_dt'] <= today + timedelta(days=30))]
    vence_60_tr = latest_trainings[(latest_trainings['vencimento_dt'] > today + timedelta(days=30)) & (latest_trainings['vencimento_dt'] <= today + timedelta(days=60))]
    vence_90_tr = latest_trainings[(latest_trainings['vencimento_dt'] > today + timedelta(days=60)) & (latest_trainings['vencimento_dt'] <= today + timedelta(days=90))]
    
    # Filtros de ASOs
    vencidos_aso = latest_asos[latest_asos['vencimento_dt'] < today]
    vence_15_aso = latest_asos[(latest_asos['vencimento_dt'] >= today) & (latest_asos['vencimento_dt'] <= today + timedelta(days=15))]
    vence_30_aso = latest_asos[(latest_asos['vencimento_dt'] > today + timedelta(days=15)) & (latest_asos['vencimento_dt'] <= today + timedelta(days=30))]

    # Filtros de Documentos da Empresa
    vencidos_docs = latest_company_docs[latest_company_docs['vencimento_dt'] < today]
    vence_30_docs = latest_company_docs[(latest_company_docs['vencimento_dt'] >= today) & (latest_company_docs['vencimento_dt'] <= today + timedelta(days=30))]

    # --- Adiciona informações de nome/empresa aos dataframes filtrados ---
    for df in [vencidos_tr, vence_15_tr, vence_30_tr, vence_60_tr, vence_90_tr, vencidos_aso, vence_15_aso, vence_30_aso]:
        if not df.empty:
            df['nome_funcionario'] = df['funcionario_id'].apply(employee_manager.get_employee_name)
            df['empresa'] = df['funcionario_id'].apply(
                lambda fid: employee_manager.get_company_name(
                    employee_manager.employees_df[employee_manager.employees_df['id'] == str(fid)]['empresa_id'].iloc[0]
                ) if not employee_manager.employees_df[employee_manager.employees_df['id'] == str(fid)].empty else 'N/A'
            )
            
    for df in [vencidos_docs, vence_30_docs]:
        if not df.empty:
            df['empresa'] = df['empresa_id'].apply(employee_manager.get_company_name)

    # --- Monta o dicionário final para o e-mail ---
    all_categorized_data = {
        "Treinamentos Vencidos": vencidos_tr,
        "Treinamentos que vencem em até 15 dias": vence_15_tr,
        "Treinamentos que vencem entre 16 e 30 dias": vence_30_tr,
        "Treinamentos que vencem entre 31 e 60 dias": vence_60_tr,
        "Treinamentos que vencem entre 61 e 90 dias": vence_90_tr,
        "ASOs Vencidos": vencidos_aso,
        "ASOs que vencem em até 15 dias": vence_15_aso,
        "ASOs que vencem entre 16 e 30 dias": vence_30_aso,
        "Documentos da Empresa Vencidos": vencidos_docs,
        "Documentos da Empresa que vencem nos próximos 30 dias": vence_30_docs,
    }
    
    return all_categorized_data

def format_email_body(categorized_data: dict) -> str:
    """Cria o corpo do e-mail em HTML com um tema moderno, fontes menores e tabelas em tons de cinza."""
    
    html_style = """
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji';
            font-size: 14px;
            line-height: 1.6;
            color: #333;
            margin: 0; 
            padding: 0; 
            background-color: #f7f7f7; 
        }
        .container { 
            max-width: 800px;
            margin: 20px auto;
            padding: 20px;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        }
        h1 { 
            font-size: 24px;
            color: #2c3e50; 
            text-align: center;
            border-bottom: 1px solid #ecf0f1;
            padding-bottom: 15px;
            margin-bottom: 10px;
        }
        h2 { 
            font-size: 18px;
            color: #34495e; 
            margin-top: 35px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }
        p.subtitle {
            text-align: center;
            color: #7f8c8d;
            font-size: 12px;
            margin-bottom: 30px;
        }
        table { 
            border-collapse: collapse; 
            width: 100%; 
            margin-bottom: 25px;
            font-size: 13px; /* Fonte da tabela menor */
        }
        th, td { 
            border: 1px solid #dddddd; 
            padding: 8px 12px; /* Espaçamento interno da célula */
            text-align: left; 
        }
        th { 
            background-color: #f2f2f2; /* Cabeçalho cinza claro */
            color: #333;
            font-weight: 600; /* Fonte do cabeçalho semi-bold */
        }
        tr:nth-child(even) { 
            background-color: #fafafa; 
        }
        /* Estilos de Alerta com cores e ícones */
        .vencido { color: #c0392b; }
        .vence-15 { color: #d35400; }
        .vence-30 { color: #f39c12; }
        .vence-60 { color: #7f8c8d; }
        .vence-90 { color: #95a5a6; }

        h2::before {
            display: inline-block;
            margin-right: 8px;
            font-weight: bold;
        }
        h2.vencido::before { content: '🔴'; }
        h2.vence-15::before { content: '🟠'; }
        h2.vence-30::before { content: '🟡'; }
        h2.vence-60::before { content: '🔵'; }
        h2.vence-90::before { content: '⚪'; }

    </style>
    """

    html_body = f"""
    <html><head>{html_style}</head><body><div class="container">
    <h1>Relatório de Vencimentos - SEGMA-SIS</h1>
    <p class="subtitle">Relatório automático gerado em {date.today().strftime('%d/%m/%Y')}</p>
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
        "Treinamentos que vencem entre 31 e 60 dias",
        "Treinamentos que vencem entre 61 e 90 dias",
    ]

    for title in display_order:
        if title in categorized_data and not categorized_data[title].empty:
            has_content = True
            df = categorized_data[title]
            config = report_configs[title]
            
            html_body += f'<h2 class="{config["class"]}">{title} ({len(df)})</h2>'
            
            cols_to_show = [col for col in config["cols"] if col in df.columns]
            df_display = df[cols_to_show]
            
            # Adiciona o método to_html com o render_links=True para transformar URLs em links clicáveis
            html_body += df_display.to_html(index=False, border=0, na_rep='N/A', classes='table', render_links=True)
    
    if not has_content:
        html_body += "<h2>Nenhuma pendência encontrada!</h2><p>Todos os documentos estão em dia para os próximos 90 dias.</p>"
        
    html_body += "</div></body></html>"
    return html_body
    
def main():
    """Função principal do script, executada pela GitHub Action."""
    print("Iniciando script de notificação...")
    try:
        config = get_smtp_config_from_env()
        
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
        sys.exit(1) 

if __name__ == "__main__":
    main()
