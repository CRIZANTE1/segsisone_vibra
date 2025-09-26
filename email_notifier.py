import os
import sys
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta
import pandas as pd
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Adiciona o diretório raiz ao path para encontrar os módulos
root_dir = os.path.dirname(os.path.abspath(__file__))
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

def _get_empty_categories():
    """Retorna um dicionário com todas as categorias vazias."""
    return {
        "Treinamentos Vencidos": pd.DataFrame(), 
        "Treinamentos que vencem em até 15 dias": pd.DataFrame(), 
        "Treinamentos que vencem entre 16 e 45 dias": pd.DataFrame(),
        "ASOs Vencidos": pd.DataFrame(), 
        "ASOs que vencem em até 15 dias": pd.DataFrame(), 
        "ASOs que vencem entre 16 e 45 dias": pd.DataFrame(),
        "Documentos da Empresa Vencidos": pd.DataFrame(), 
        "Documentos da Empresa que vencem nos próximos 30 dias": pd.DataFrame(),
    }

def categorize_expirations_for_unit(employee_manager: EmployeeManager, docs_manager: CompanyDocsManager):
    """
    Categoriza os vencimentos para uma única unidade com a lógica de ASO corrigida.
    """
    try:
        today = date.today()
        
        # Verificar se os dados foram carregados corretamente
        if not employee_manager.data_loaded_successfully:
            logger.warning("Dados do EmployeeManager não foram carregados corretamente")
            return _get_empty_categories()
        
        if not docs_manager.data_loaded_successfully:
            logger.warning("Dados do CompanyDocsManager não foram carregados corretamente")
            return _get_empty_categories()
        
        # Verificar se os DataFrames existem e não estão vazios
        if employee_manager.companies_df.empty:
            logger.warning("DataFrame de empresas está vazio")
            return _get_empty_categories()
            
        active_companies = employee_manager.companies_df[employee_manager.companies_df['status'].str.lower() == 'ativo']
        
        # Verificar se há funcionários para processar
        if employee_manager.employees_df.empty:
            logger.warning("DataFrame de funcionários está vazio")
            active_employees = pd.DataFrame()
        else:
            active_employees = employee_manager.employees_df[
                (employee_manager.employees_df['status'].str.lower() == 'ativo') &
                (employee_manager.employees_df['empresa_id'].isin(active_companies['id']))
            ]

        # --- Processamento de Treinamentos ---
        latest_trainings = pd.DataFrame()
        if not employee_manager.training_df.empty and not active_employees.empty:
            trainings_actives = employee_manager.training_df[employee_manager.training_df['funcionario_id'].isin(active_employees['id'])]
            if not trainings_actives.empty:
                latest_trainings = trainings_actives.sort_values('data', ascending=False).groupby(['funcionario_id', 'norma']).head(1).copy()
                # Verificar se a coluna vencimento existe e é válida
                if 'vencimento' in latest_trainings.columns:
                    latest_trainings['vencimento_dt'] = pd.to_datetime(latest_trainings['vencimento'], errors='coerce').dt.date
                    latest_trainings.dropna(subset=['vencimento_dt'], inplace=True)
                else:
                    logger.warning("Coluna 'vencimento' não encontrada em treinamentos")
                    latest_trainings = pd.DataFrame()
            
        # --- Processamento de ASOs ---
        latest_asos = pd.DataFrame()
        if not employee_manager.aso_df.empty and not active_employees.empty:
            asos_actives = employee_manager.aso_df[employee_manager.aso_df['funcionario_id'].isin(active_employees['id'])]
            if not asos_actives.empty:
                aptitude_asos = asos_actives[~asos_actives['tipo_aso'].str.lower().isin(['demissional'])].copy()
                if not aptitude_asos.empty:
                    latest_asos = aptitude_asos.sort_values('data_aso', ascending=False).groupby('funcionario_id').head(1).copy()
                    # Verificar se a coluna vencimento existe e é válida
                    if 'vencimento' in latest_asos.columns:
                        latest_asos['vencimento_dt'] = pd.to_datetime(latest_asos['vencimento'], errors='coerce').dt.date
                        latest_asos.dropna(subset=['vencimento_dt'], inplace=True)
                    else:
                        logger.warning("Coluna 'vencimento' não encontrada em ASOs")
                        latest_asos = pd.DataFrame()

        # --- Processamento de Documentos da Empresa ---
        latest_company_docs = pd.DataFrame()
        if not docs_manager.docs_df.empty:
            docs_actives = docs_manager.docs_df[docs_manager.docs_df['empresa_id'].isin(active_companies['id'])]
            if not docs_actives.empty:
                latest_company_docs = docs_actives.sort_values('data_emissao', ascending=False).groupby(['empresa_id', 'tipo_documento']).head(1).copy()
                # Verificar se a coluna vencimento existe e é válida
                if 'vencimento' in latest_company_docs.columns:
                    latest_company_docs['vencimento_dt'] = pd.to_datetime(latest_company_docs['vencimento'], errors='coerce').dt.date
                    latest_company_docs.dropna(subset=['vencimento_dt'], inplace=True)
                else:
                    logger.warning("Coluna 'vencimento' não encontrada em documentos da empresa")
                    latest_company_docs = pd.DataFrame()

        # --- Filtros de Vencimento com verificações de segurança ---
        vencidos_tr = latest_trainings[latest_trainings['vencimento_dt'] < today] if not latest_trainings.empty else pd.DataFrame()
        vence_15_tr = latest_trainings[(latest_trainings['vencimento_dt'] >= today) & (latest_trainings['vencimento_dt'] <= today + timedelta(days=15))] if not latest_trainings.empty else pd.DataFrame()
        vence_45_tr = latest_trainings[(latest_trainings['vencimento_dt'] > today + timedelta(days=15)) & (latest_trainings['vencimento_dt'] <= today + timedelta(days=45))] if not latest_trainings.empty else pd.DataFrame()
        
        vencidos_aso = latest_asos[latest_asos['vencimento_dt'] < today] if not latest_asos.empty else pd.DataFrame()
        vence_15_aso = latest_asos[(latest_asos['vencimento_dt'] >= today) & (latest_asos['vencimento_dt'] <= today + timedelta(days=15))] if not latest_asos.empty else pd.DataFrame()
        vence_45_aso = latest_asos[(latest_asos['vencimento_dt'] > today + timedelta(days=15)) & (latest_asos['vencimento_dt'] <= today + timedelta(days=45))] if not latest_asos.empty else pd.DataFrame()

        vencidos_docs = latest_company_docs[latest_company_docs['vencimento_dt'] < today] if not latest_company_docs.empty else pd.DataFrame()
        vence_30_docs = latest_company_docs[(latest_company_docs['vencimento_dt'] >= today) & (latest_company_docs['vencimento_dt'] <= today + timedelta(days=30))] if not latest_company_docs.empty else pd.DataFrame()

        # --- Adiciona informações de nome/empresa com verificações de segurança ---
        if not active_employees.empty:
            employee_id_to_name = active_employees.set_index('id')['nome']
            employee_id_to_company_name = active_employees.set_index('id')['empresa_id'].map(active_companies.set_index('id')['nome'])

            for df in [vencidos_tr, vence_15_tr, vence_45_tr, vencidos_aso, vence_15_aso, vence_45_aso]:
                if not df.empty and 'funcionario_id' in df.columns:
                    try:
                        df.loc[:, 'nome_funcionario'] = df['funcionario_id'].map(employee_id_to_name)
                        df.loc[:, 'empresa'] = df['funcionario_id'].map(employee_id_to_company_name)
                    except Exception as e:
                        logger.error(f"Erro ao adicionar informações de funcionário: {e}")

        if not active_companies.empty:
            company_id_to_name = active_companies.set_index('id')['nome']
            for df in [vencidos_docs, vence_30_docs]:
                if not df.empty and 'empresa_id' in df.columns:
                    try:
                        df.loc[:, 'empresa'] = df['empresa_id'].map(company_id_to_name)
                    except Exception as e:
                        logger.error(f"Erro ao adicionar informações de empresa: {e}")

        return {
            "Treinamentos Vencidos": vencidos_tr, 
            "Treinamentos que vencem em até 15 dias": vence_15_tr, 
            "Treinamentos que vencem entre 16 e 45 dias": vence_45_tr,
            "ASOs Vencidos": vencidos_aso, 
            "ASOs que vencem em até 15 dias": vence_15_aso, 
            "ASOs que vencem entre 16 e 45 dias": vence_45_aso,
            "Documentos da Empresa Vencidos": vencidos_docs, 
            "Documentos da Empresa que vencem nos próximos 30 dias": vence_30_docs,
        }
    except Exception as e:
        logger.error(f"Erro crítico ao categorizar vencimentos: {e}")
        return _get_empty_categories()

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
            
            try:
                df_display = data_df.copy()
                # Formatação mais segura das datas
                if 'vencimento' in df_display.columns:
                    df_display['vencimento'] = pd.to_datetime(df_display['vencimento'], errors='coerce', dayfirst=True).dt.strftime('%d/%m/%Y')
                    # Remove linhas com datas inválidas
                    df_display = df_display.dropna(subset=['vencimento'])

                cols_to_show = [col for col in config.get("cols", df_display.columns) if col in df_display.columns]
                if cols_to_show:  # Verificar se há colunas para mostrar
                    html_table = df_display[cols_to_show].to_html(index=False, border=0, na_rep='N/A', escape=False)
                    html_body += html_table
                else:
                    html_body += "<p>Dados disponíveis, mas estrutura de colunas incompatível.</p>"
            except Exception as e:
                logger.error(f"Erro ao processar dados da categoria '{title}': {e}")
                html_body += f"<p>Erro ao processar dados desta categoria: {str(e)}</p>"
            
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
        logger.info(f"Conectando ao servidor SMTP {config['smtp_server']}...")
        with smtplib.SMTP_SSL(config["smtp_server"], config["smtp_port"], context=context) as server:
            logger.info("Fazendo login...")
            server.login(config["sender_email"], config["sender_password"])
            logger.info(f"Enviando e-mail para {config['receiver_email']}...")
            server.sendmail(config["sender_email"], config["receiver_email"].split(','), message.as_string())
            logger.info("E-mail enviado com sucesso!")
    except Exception as e:
        logger.error(f"Falha ao enviar e-mail via SMTP: {e}")
        raise

def main():
    """Função principal que itera sobre todas as unidades e envia um único e-mail consolidado."""
    logger.info("Iniciando script de notificação de vencimentos...")
    try:
        config = get_smtp_config_from_env()
        
        matrix_manager = MatrixManager()
        all_units = matrix_manager.get_all_units()
        
        if not all_units:
            logger.warning("Nenhuma unidade encontrada na matriz. Encerrando.")
            return
        
        all_units_categorized_data = {}
        successful_units = 0
        
        for unit in all_units:
            unit_name = unit.get('nome_unidade')
            spreadsheet_id = unit.get('spreadsheet_id')
            folder_id = unit.get('folder_id')
            
            if not spreadsheet_id:
                logger.warning(f"Unidade '{unit_name}' sem spreadsheet_id. Pulando.")
                continue
            
            logger.info(f"--- Processando unidade: {unit_name} ---")
            
            try:
                # CORREÇÃO PRINCIPAL: Garantir que folder_id seja uma string
                folder_id_safe = folder_id if folder_id else ""
                
                # Criar os managers com parâmetros explícitos
                employee_manager = EmployeeManager(
                    spreadsheet_id=spreadsheet_id, 
                    folder_id=folder_id_safe
                )
                docs_manager = CompanyDocsManager(
                    spreadsheet_id=spreadsheet_id, 
                    folder_id=folder_id_safe
                )
                
                # Verificar se os managers foram inicializados corretamente
                if not employee_manager.data_loaded_successfully:
                    logger.error(f"Falha ao carregar dados de funcionários para unidade '{unit_name}'")
                    continue
                    
                if not docs_manager.data_loaded_successfully:
                    logger.error(f"Falha ao carregar dados de documentos para unidade '{unit_name}'")
                    continue
                
                categorized_data = categorize_expirations_for_unit(employee_manager, docs_manager)
                
                # Adicionar nome da unidade a todos os DataFrames não vazios
                for category_name, category_df in categorized_data.items():
                    if not category_df.empty:
                        try:
                            category_df['unidade'] = unit_name
                        except Exception as e:
                            logger.error(f"Erro ao adicionar nome da unidade '{unit_name}' à categoria '{category_name}': {e}")
                
                all_units_categorized_data[unit_name] = categorized_data
                successful_units += 1
                logger.info(f"Unidade '{unit_name}' processada com sucesso.")
                
            except Exception as e:
                logger.error(f"Erro ao processar unidade '{unit_name}': {e}")
                continue

        if successful_units == 0:
            logger.error("Nenhuma unidade foi processada com sucesso. Encerrando.")
            return

        logger.info(f"Total de {successful_units} unidades processadas com sucesso.")

        # Consolidar dados de todas as unidades
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

        # Verificar se há pendências para enviar o e-mail
        if not any(not df.empty for df in final_report_data.values()):
            logger.info("Nenhuma pendência encontrada em todas as unidades. E-mail não será enviado.")
        else:
            logger.info("Pendências encontradas, gerando e-mail consolidado.")
            email_body = format_email_body(final_report_data)
            send_smtp_email(email_body, config)
        
        logger.info("Script finalizado com sucesso.")

    except Exception as e:
        logger.error(f"Erro fatal no script: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()