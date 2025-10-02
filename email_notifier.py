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

# Adiciona o diretório raiz ao path
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
        raise ValueError(f"Variáveis de ambiente ausentes: {', '.join(missing)}. Verifique os Secrets.")
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
    ✅ CORRIGIDO: Categoriza os vencimentos com tratamento robusto de erros
    """
    try:
        today = date.today()
        
        # ✅ Verificações de segurança
        if not employee_manager.data_loaded_successfully:
            logger.warning("Dados do EmployeeManager não foram carregados")
            return _get_empty_categories()
        
        if not docs_manager.data_loaded_successfully:
            logger.warning("Dados do CompanyDocsManager não foram carregados")
            return _get_empty_categories()
        
        if employee_manager.companies_df.empty:
            logger.warning("DataFrame de empresas está vazio")
            return _get_empty_categories()
            
        active_companies = employee_manager.companies_df[
            employee_manager.companies_df['status'].str.lower() == 'ativo'
        ]
        
        if active_companies.empty:
            logger.info("Nenhuma empresa ativa encontrada")
            return _get_empty_categories()
        
        # ✅ Processa funcionários ativos
        active_employees = pd.DataFrame()
        if not employee_manager.employees_df.empty:
            active_employees = employee_manager.employees_df[
                (employee_manager.employees_df['status'].str.lower() == 'ativo') &
                (employee_manager.employees_df['empresa_id'].isin(active_companies['id']))
            ]

        # --- Processamento de Treinamentos ---
        latest_trainings = pd.DataFrame()
        if not employee_manager.training_df.empty and not active_employees.empty:
            trainings_actives = employee_manager.training_df[
                employee_manager.training_df['funcionario_id'].isin(active_employees['id'])
            ]
            if not trainings_actives.empty and 'vencimento' in trainings_actives.columns:
                trainings_actives['vencimento_dt'] = pd.to_datetime(
                    trainings_actives['vencimento'], errors='coerce'
                ).dt.date
                trainings_actives.dropna(subset=['vencimento_dt'], inplace=True)
                
                if not trainings_actives.empty:
                    latest_trainings = trainings_actives.sort_values(
                        'data', ascending=False
                    ).groupby(['funcionario_id', 'norma']).head(1).copy()
        
        # --- Processamento de ASOs ---
        latest_asos = pd.DataFrame()
        if not employee_manager.aso_df.empty and not active_employees.empty:
            asos_actives = employee_manager.aso_df[
                employee_manager.aso_df['funcionario_id'].isin(active_employees['id'])
            ]
            if not asos_actives.empty and 'vencimento' in asos_actives.columns:
                aptitude_asos = asos_actives[
                    ~asos_actives['tipo_aso'].str.lower().isin(['demissional'])
                ].copy()
                
                if not aptitude_asos.empty:
                    aptitude_asos['vencimento_dt'] = pd.to_datetime(
                        aptitude_asos['vencimento'], errors='coerce'
                    ).dt.date
                    aptitude_asos.dropna(subset=['vencimento_dt'], inplace=True)
                    
                    if not aptitude_asos.empty:
                        latest_asos = aptitude_asos.sort_values(
                            'data_aso', ascending=False
                        ).groupby('funcionario_id').head(1).copy()

        # --- Processamento de Documentos da Empresa ---
        latest_company_docs = pd.DataFrame()
        if not docs_manager.docs_df.empty:
            docs_actives = docs_manager.docs_df[
                docs_manager.docs_df['empresa_id'].isin(active_companies['id'])
            ]
            if not docs_actives.empty and 'vencimento' in docs_actives.columns:
                docs_actives['vencimento_dt'] = pd.to_datetime(
                    docs_actives['vencimento'], errors='coerce'
                ).dt.date
                docs_actives.dropna(subset=['vencimento_dt'], inplace=True)
                
                if not docs_actives.empty:
                    latest_company_docs = docs_actives.sort_values(
                        'data_emissao', ascending=False
                    ).groupby(['empresa_id', 'tipo_documento']).head(1).copy()

        # --- Filtros de Vencimento ---
        vencidos_tr = latest_trainings[
            latest_trainings['vencimento_dt'] < today
        ] if not latest_trainings.empty else pd.DataFrame()
        
        vence_15_tr = latest_trainings[
            (latest_trainings['vencimento_dt'] >= today) & 
            (latest_trainings['vencimento_dt'] <= today + timedelta(days=15))
        ] if not latest_trainings.empty else pd.DataFrame()
        
        vence_45_tr = latest_trainings[
            (latest_trainings['vencimento_dt'] > today + timedelta(days=15)) & 
            (latest_trainings['vencimento_dt'] <= today + timedelta(days=45))
        ] if not latest_trainings.empty else pd.DataFrame()
        
        vencidos_aso = latest_asos[
            latest_asos['vencimento_dt'] < today
        ] if not latest_asos.empty else pd.DataFrame()
        
        vence_15_aso = latest_asos[
            (latest_asos['vencimento_dt'] >= today) & 
            (latest_asos['vencimento_dt'] <= today + timedelta(days=15))
        ] if not latest_asos.empty else pd.DataFrame()
        
        vence_45_aso = latest_asos[
            (latest_asos['vencimento_dt'] > today + timedelta(days=15)) & 
            (latest_asos['vencimento_dt'] <= today + timedelta(days=45))
        ] if not latest_asos.empty else pd.DataFrame()

        vencidos_docs = latest_company_docs[
            latest_company_docs['vencimento_dt'] < today
        ] if not latest_company_docs.empty else pd.DataFrame()
        
        vence_30_docs = latest_company_docs[
            (latest_company_docs['vencimento_dt'] >= today) & 
            (latest_company_docs['vencimento_dt'] <= today + timedelta(days=30))
        ] if not latest_company_docs.empty else pd.DataFrame()

        # --- Adiciona informações de nome/empresa ---
        if not active_employees.empty:
            employee_id_to_name = active_employees.set_index('id')['nome']
            employee_id_to_company_name = active_employees.set_index('id')['empresa_id'].map(
                active_companies.set_index('id')['nome']
            )

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
        logger.error(f"Erro crítico ao categorizar vencimentos: {e}", exc_info=True)
        return _get_empty_categories()

def format_email_body(categorized_data: dict) -> str:
    """
    ✅ MELHORADO: Layout moderno e profissional com design responsivo
    """
    
    # ✅ CSS Moderno e Profissional
    html_style = """
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 14px;
            line-height: 1.6;
            color: #333333;
            background-color: #f5f5f5;
        }
        
        .email-container {
            max-width: 900px;
            margin: 0 auto;
            background-color: #ffffff;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        /* Header */
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 8px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        .header .subtitle {
            font-size: 14px;
            opacity: 0.95;
            font-weight: 300;
        }
        
        /* Summary Cards */
        .summary-section {
            padding: 30px;
            background-color: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }
        
        .summary-cards {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            justify-content: center;
        }
        
        .summary-card {
            flex: 1;
            min-width: 200px;
            background: white;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            border-left: 4px solid #667eea;
        }
        
        .summary-card.critical {
            border-left-color: #dc3545;
        }
        
        .summary-card.warning {
            border-left-color: #ffc107;
        }
        
        .summary-card.info {
            border-left-color: #17a2b8;
        }
        
        .summary-card .number {
            font-size: 32px;
            font-weight: 700;
            color: #667eea;
            margin-bottom: 5px;
        }
        
        .summary-card.critical .number {
            color: #dc3545;
        }
        
        .summary-card.warning .number {
            color: #ffc107;
        }
        
        .summary-card .label {
            font-size: 13px;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Content Section */
        .content-section {
            padding: 30px;
        }
        
        .category-block {
            margin-bottom: 35px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }
        
        .category-header {
            padding: 15px 20px;
            font-size: 16px;
            font-weight: 600;
            color: white;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .category-header.critical {
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
        }
        
        .category-header.warning {
            background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);
        }
        
        .category-header.info {
            background: linear-gradient(135deg, #17a2b8 0%, #138496 100%);
        }
        
        .category-header .badge {
            background: rgba(255,255,255,0.25);
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 13px;
            font-weight: 600;
        }
        
        table { 
            border-collapse: collapse;
            width: 100%;
            font-size: 13px;
        }
        
        th {
            background-color: #f8f9fa;
            color: #495057;
            font-weight: 600;
            text-align: left;
            padding: 12px 15px;
            border-bottom: 2px solid #dee2e6;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
        }
        
        td { 
            padding: 12px 15px;
            border-bottom: 1px solid #f1f3f5;
            color: #495057;
        }
        
        tr:hover {
            background-color: #f8f9fa;
        }
        
        tr:last-child td {
            border-bottom: none;
        }
        
        /* Status badges na tabela */
        .status-vencido {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            background-color: #fee;
            color: #c00;
            font-size: 11px;
            font-weight: 600;
        }
        
        .status-proximo {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            background-color: #fff3cd;
            color: #856404;
            font-size: 11px;
            font-weight: 600;
        }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 60px 30px;
            color: #6c757d;
        }
        
        .empty-state-icon {
            font-size: 64px;
            margin-bottom: 20px;
            opacity: 0.5;
        }
        
        .empty-state h2 {
            font-size: 24px;
            color: #28a745;
            margin-bottom: 10px;
        }
        
        .empty-state p {
            font-size: 15px;
            color: #6c757d;
        }
        
        /* Footer */
        .footer {
            background-color: #f8f9fa;
            padding: 25px 30px;
            text-align: center;
            border-top: 1px solid #dee2e6;
        }
        
        .footer-content {
            font-size: 13px;
            color: #6c757d;
            line-height: 1.8;
        }
        
        .footer-logo {
            font-weight: 700;
            color: #667eea;
            font-size: 16px;
            margin-bottom: 10px;
        }
        
        .footer-divider {
            height: 1px;
            background: linear-gradient(to right, transparent, #dee2e6, transparent);
            margin: 15px 0;
        }
        
        /* Responsive */
        @media only screen and (max-width: 600px) {
            .summary-cards {
                flex-direction: column;
            }
            
            .summary-card {
                min-width: 100%;
            }
            
            table {
                font-size: 12px;
            }
            
            th, td {
                padding: 8px 10px;
            }
        }
    </style>
    """
    
    # ✅ Calcula estatísticas gerais
    total_critical = 0
    total_warning = 0
    total_info = 0
    
    for category_name, df in categorized_data.items():
        if not df.empty:
            count = len(df)
            if 'vencido' in category_name.lower():
                total_critical += count
            elif '15 dias' in category_name.lower() or '30 dias' in category_name.lower():
                total_warning += count
            else:
                total_info += count
    
    has_content = (total_critical + total_warning + total_info) > 0
    
    # ✅ Início do HTML
    html_body = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        {html_style}
    </head>
    <body>
        <div class="email-container">
            <!-- Header -->
            <div class="header">
                <h1>🔔 Relatório de Vencimentos - SEGMA-SIS</h1>
                <div class="subtitle">Relatório Consolidado • {date.today().strftime('%d/%m/%Y')}</div>
            </div>
    """
    
    # ✅ Cards de Resumo
    if has_content:
        html_body += f"""
            <div class="summary-section">
                <div class="summary-cards">
                    <div class="summary-card critical">
                        <div class="number">{total_critical}</div>
                        <div class="label">🔴 Vencidos</div>
                    </div>
                    <div class="summary-card warning">
                        <div class="number">{total_warning}</div>
                        <div class="label">⚠️ Vencendo em Breve</div>
                    </div>
                    <div class="summary-card info">
                        <div class="number">{total_info}</div>
                        <div class="label">📋 Para Monitorar</div>
                    </div>
                </div>
            </div>
            
            <div class="content-section">
        """
    
    # ✅ Configuração das categorias com cores
    report_configs = {
        "Documentos da Empresa Vencidos": {
            "cols": ['unidade', 'empresa', 'tipo_documento', 'vencimento'],
            "priority": "critical",
            "icon": "🔴"
        },
        "ASOs Vencidos": {
            "cols": ['unidade', 'empresa', 'nome_funcionario', 'tipo_aso', 'vencimento'],
            "priority": "critical",
            "icon": "🔴"
        },
        "Treinamentos Vencidos": {
            "cols": ['unidade', 'empresa', 'nome_funcionario', 'norma', 'vencimento'],
            "priority": "critical",
            "icon": "🔴"
        },
        "Documentos da Empresa que vencem nos próximos 30 dias": {
            "cols": ['unidade', 'empresa', 'tipo_documento', 'vencimento'],
            "priority": "warning",
            "icon": "⚠️"
        },
        "ASOs que vencem em até 15 dias": {
            "cols": ['unidade', 'empresa', 'nome_funcionario', 'tipo_aso', 'vencimento'],
            "priority": "warning",
            "icon": "⚠️"
        },
        "Treinamentos que vencem em até 15 dias": {
            "cols": ['unidade', 'empresa', 'nome_funcionario', 'norma', 'vencimento'],
            "priority": "warning",
            "icon": "⚠️"
        },
        "ASOs que vencem entre 16 e 45 dias": {
            "cols": ['unidade', 'empresa', 'nome_funcionario', 'tipo_aso', 'vencimento'],
            "priority": "info",
            "icon": "📋"
        },
        "Treinamentos que vencem entre 16 e 45 dias": {
            "cols": ['unidade', 'empresa', 'nome_funcionario', 'norma', 'vencimento'],
            "priority": "info",
            "icon": "📋"
        },
    }
    
    # ✅ Renderiza cada categoria
    for category_name, config in report_configs.items():
        if category_name in categorized_data and not categorized_data[category_name].empty:
            data_df = categorized_data[category_name]
            count = len(data_df)
            priority = config['priority']
            icon = config['icon']
            
            html_body += f"""
                <div class="category-block">
                    <div class="category-header {priority}">
                        <span>{icon} {category_name}</span>
                        <span class="badge">{count} item{'ns' if count != 1 else ''}</span>
                    </div>
            """
            
            try:
                df_display = data_df.copy()
                
                # Formatação de datas
                if 'vencimento' in df_display.columns:
                    df_display['vencimento'] = pd.to_datetime(
                        df_display['vencimento'], errors='coerce', dayfirst=True
                    ).dt.strftime('%d/%m/%Y')
                    df_display = df_display.dropna(subset=['vencimento'])
                
                # Seleciona colunas para exibir
                cols_to_show = [col for col in config['cols'] if col in df_display.columns]
                
                if cols_to_show:
                    # Renomeia colunas para português
                    column_names = {
                        'unidade': 'Unidade',
                        'empresa': 'Empresa',
                        'tipo_documento': 'Documento',
                        'nome_funcionario': 'Funcionário',
                        'tipo_aso': 'Tipo',
                        'norma': 'Norma',
                        'vencimento': 'Vencimento'
                    }
                    
                    df_display = df_display[cols_to_show].rename(columns=column_names)
                    
                    # Converte para HTML com estilo
                    html_table = df_display.to_html(
                        index=False, 
                        border=0, 
                        na_rep='N/A',
                        escape=False,
                        classes='data-table'
                    )
                    
                    html_body += html_table
                else:
                    html_body += "<p style='padding: 20px; text-align: center; color: #6c757d;'>Estrutura de dados incompatível</p>"
                    
            except Exception as e:
                logger.error(f"Erro ao processar categoria '{category_name}': {e}")
                html_body += f"<p style='padding: 20px; text-align: center; color: #dc3545;'>Erro ao processar dados: {str(e)}</p>"
            
            html_body += "</div>"
    
    # ✅ Se não há conteúdo
    if not has_content:
        html_body += """
            <div class="empty-state">
                <div class="empty-state-icon">✅</div>
                <h2>Tudo em Ordem!</h2>
                <p>Não há pendências de vencimentos em nenhuma unidade operacional.</p>
                <p style="margin-top: 10px; font-size: 13px;">Todos os documentos estão em dia. Continue o bom trabalho! 🎉</p>
            </div>
        """
    else:
        html_body += "</div>"  # Fecha content-section
    
    # ✅ Footer
    html_body += """
            <div class="footer">
                <div class="footer-logo">SEGMA-SIS</div>
                <div class="footer-divider"></div>
                <div class="footer-content">
                    Este é um e-mail automático gerado pelo sistema SEGMA-SIS.<br>
                    Por favor, não responda esta mensagem.<br><br>
                    <strong>Dúvidas?</strong> Entre em contato com o administrador do sistema.
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_body

def send_smtp_email(html_body: str, config: dict):
    """✅ Envia o email via SMTP"""
    message = MIMEMultipart("alternative")
    message["Subject"] = f"📊 Relatório SEGMA-SIS - {date.today().strftime('%d/%m/%Y')}"
    message["From"] = f"SEGMA-SIS Sistema <{config['sender_email']}>"
    message["To"] = config["receiver_email"]
    message["Reply-To"] = "noreply@segma-sis.com"
    
    message.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        logger.info(f"Conectando ao servidor SMTP {config['smtp_server']}...")
        with smtplib.SMTP_SSL(config["smtp_server"], config["smtp_port"], context=context) as server:
            logger.info("Fazendo login...")
            server.login(config["sender_email"], config["sender_password"])
            logger.info(f"Enviando e-mail para {config['receiver_email']}...")
            server.sendmail(config["sender_email"], config["receiver_email"].split(','), message.as_string())
            logger.info("✅ E-mail enviado com sucesso!")
    except Exception as e:
        logger.error(f"❌ Falha ao enviar e-mail via SMTP: {e}")
        raise

def main():
    """✅ CORRIGIDO: Função principal com tratamento robusto de erros"""
    logger.info("🚀 Iniciando script de notificação de vencimentos...")
    
    try:
        config = get_smtp_config_from_env()
        
        matrix_manager = MatrixManager()
        all_units = matrix_manager.get_all_units()
        
        if not all_units:
            logger.warning("⚠️ Nenhuma unidade encontrada na matriz. Encerrando.")
            return
        
        all_units_categorized_data = {}
        successful_units = 0
        
        for unit in all_units:
            unit_name = unit.get('nome_unidade')
            spreadsheet_id = unit.get('spreadsheet_id')
            folder_id = unit.get('folder_id')
            
            if not spreadsheet_id:
                logger.warning(f"⚠️ Unidade '{unit_name}' sem spreadsheet_id. Pulando.")
                continue
            
            logger.info(f"📊 Processando unidade: {unit_name}")
            
            try:
                # ✅ CORREÇÃO: Garante que folder_id seja string
                folder_id_safe = str(folder_id) if folder_id else ""
                
                # ✅ Cria managers com parâmetros explícitos
                employee_manager = EmployeeManager(
                    spreadsheet_id=spreadsheet_id, 
                    folder_id=folder_id_safe
                )
                docs_manager = CompanyDocsManager(
                    spreadsheet_id=spreadsheet_id, 
                    folder_id=folder_id_safe
                )
                
                # ✅ Verifica se os managers foram inicializados corretamente
                if not employee_manager.data_loaded_successfully:
                    logger.error(f"❌ Falha ao carregar dados de funcionários para '{unit_name}'")
                    continue
                    
                if not docs_manager.data_loaded_successfully:
                    logger.error(f"❌ Falha ao carregar dados de documentos para '{unit_name}'")
                    continue
                
                # Categoriza os dados
                categorized_data = categorize_expirations_for_unit(employee_manager, docs_manager)
                
                # Adiciona nome da unidade a todos os DataFrames
                for category_name, category_df in categorized_data.items():
                    if not category_df.empty:
                        try:
                            category_df['unidade'] = unit_name
                        except Exception as e:
                            logger.error(f"❌ Erro ao adicionar nome da unidade '{unit_name}': {e}")
                
                all_units_categorized_data[unit_name] = categorized_data
                successful_units += 1
                logger.info(f"✅ Unidade '{unit_name}' processada com sucesso.")
                
            except Exception as e:
                logger.error(f"❌ Erro ao processar unidade '{unit_name}': {e}", exc_info=True)
                continue

        if successful_units == 0:
            logger.error("❌ Nenhuma unidade foi processada com sucesso. Encerrando.")
            return

        logger.info(f"✅ Total de {successful_units} unidades processadas com sucesso.")

        # ✅ Consolida dados de todas as unidades
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

        # ✅ Verifica se há pendências
        has_pendencies = any(not df.empty for df in final_report_data.values())
        
        if not has_pendencies:
            logger.info("ℹ️ Nenhuma pendência encontrada. E-mail não será enviado.")
        else:
            logger.info("📧 Pendências encontradas. Gerando e enviando e-mail...")
            email_body = format_email_body(final_report_data)
            send_smtp_email(email_body, config)
            logger.info("✅ E-mail enviado com sucesso!")
        
        logger.info("🎉 Script finalizado com sucesso.")

    except Exception as e:
        logger.error(f"💥 Erro fatal no script: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
