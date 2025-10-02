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

def get_smtp_config():
    """
    Lê a configuração SMTP tanto de variáveis de ambiente (GitHub Actions)
    quanto de arquivo local para desenvolvimento.
    """
    # Tenta ler de variáveis de ambiente (modo GitHub Actions)
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    global_receiver_email = os.getenv("RECEIVER_EMAIL")
    
    # Se não encontrar, tenta carregar de um arquivo local (para testes)
    if not all([sender_email, sender_password, global_receiver_email]):
        try:
            # Tenta carregar de um arquivo .env local
            from dotenv import load_dotenv
            load_dotenv()
            
            sender_email = os.getenv("SENDER_EMAIL")
            sender_password = os.getenv("SENDER_PASSWORD")
            global_receiver_email = os.getenv("RECEIVER_EMAIL")
        except ImportError:
            pass
    
    # Validação final
    if not all([sender_email, sender_password, global_receiver_email]):
        raise ValueError(
            "Configurações de e-mail não encontradas. "
            "Configure as variáveis de ambiente: SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL"
        )
    
    config = {
        "smtp_server": "smtp.gmail.com", 
        "smtp_port": 465, 
        "sender_email": sender_email,
        "sender_password": sender_password,
        "global_receiver_email": global_receiver_email
    }
    
    logger.info(f"✅ Configuração SMTP carregada. Remetente: {sender_email}")
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
        ].copy()
        
        if active_companies.empty:
            logger.info("Nenhuma empresa ativa encontrada")
            return _get_empty_categories()
        
        # ✅ Processa funcionários ativos
        active_employees = pd.DataFrame()
        if not employee_manager.employees_df.empty:
            active_employees = employee_manager.employees_df[
                (employee_manager.employees_df['status'].str.lower() == 'ativo') &
                (employee_manager.employees_df['empresa_id'].isin(active_companies['id']))
            ].copy()

        # --- Processamento de Treinamentos ---
        latest_trainings = pd.DataFrame()
        if not employee_manager.training_df.empty and not active_employees.empty:
            trainings_actives = employee_manager.training_df[
                employee_manager.training_df['funcionario_id'].isin(active_employees['id'])
            ].copy()
            
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
            ].copy()
            
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
            ].copy()
            
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
        ].copy() if not latest_trainings.empty else pd.DataFrame()
        
        vence_15_tr = latest_trainings[
            (latest_trainings['vencimento_dt'] >= today) & 
            (latest_trainings['vencimento_dt'] <= today + timedelta(days=15))
        ].copy() if not latest_trainings.empty else pd.DataFrame()
        
        vence_45_tr = latest_trainings[
            (latest_trainings['vencimento_dt'] > today + timedelta(days=15)) & 
            (latest_trainings['vencimento_dt'] <= today + timedelta(days=45))
        ].copy() if not latest_trainings.empty else pd.DataFrame()
        
        vencidos_aso = latest_asos[
            latest_asos['vencimento_dt'] < today
        ].copy() if not latest_asos.empty else pd.DataFrame()
        
        vence_15_aso = latest_asos[
            (latest_asos['vencimento_dt'] >= today) & 
            (latest_asos['vencimento_dt'] <= today + timedelta(days=15))
        ].copy() if not latest_asos.empty else pd.DataFrame()
        
        vence_45_aso = latest_asos[
            (latest_asos['vencimento_dt'] > today + timedelta(days=15)) & 
            (latest_asos['vencimento_dt'] <= today + timedelta(days=45))
        ].copy() if not latest_asos.empty else pd.DataFrame()

        vencidos_docs = latest_company_docs[
            latest_company_docs['vencimento_dt'] < today
        ].copy() if not latest_company_docs.empty else pd.DataFrame()
        
        vence_30_docs = latest_company_docs[
            (latest_company_docs['vencimento_dt'] >= today) & 
            (latest_company_docs['vencimento_dt'] <= today + timedelta(days=30))
        ].copy() if not latest_company_docs.empty else pd.DataFrame()

        # --- Adiciona informações de nome/empresa ---
        if not active_employees.empty:
            employee_id_to_name = active_employees.set_index('id')['nome']
            employee_id_to_company_name = active_employees.set_index('id')['empresa_id'].map(
                active_companies.set_index('id')['nome']
            )

            for df in [vencidos_tr, vence_15_tr, vence_45_tr, vencidos_aso, vence_15_aso, vence_45_aso]:
                if not df.empty and 'funcionario_id' in df.columns:
                    try:
                        df['nome_funcionario'] = df['funcionario_id'].map(employee_id_to_name)
                        df['empresa'] = df['funcionario_id'].map(employee_id_to_company_name)
                    except Exception as e:
                        logger.error(f"Erro ao adicionar informações de funcionário: {e}")

        if not active_companies.empty:
            company_id_to_name = active_companies.set_index('id')['nome']
            for df in [vencidos_docs, vence_30_docs]:
                if not df.empty and 'empresa_id' in df.columns:
                    try:
                        df['empresa'] = df['empresa_id'].map(company_id_to_name)
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

def format_email_body(categorized_data: dict, unit_name: str = None, is_global: bool = False) -> str:
    """
    ✅ REDESENHADO: Template moderno inspirado no ISF IA
    """
    
    html_style = """
    <style>
        body { 
            font-family: Arial, sans-serif; 
            line-height: 1.6; 
            margin: 0; 
            padding: 20px; 
            background-color: #f4f4f4; 
        }
        .container { 
            max-width: 900px; 
            margin: 0 auto; 
            background-color: white; 
            border-radius: 10px; 
            overflow: hidden; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
        }
        .header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            padding: 30px; 
            text-align: center; 
        }
        .header.global {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        .header h1 { 
            font-size: 32px; 
            font-weight: bold; 
            margin: 0 0 10px 0; 
        }
        .header p { 
            font-size: 16px; 
            margin: 0; 
            opacity: 0.95; 
        }
        .header .unit-badge {
            display: inline-block;
            background: rgba(255,255,255,0.25);
            padding: 8px 20px;
            border-radius: 20px;
            margin-top: 15px;
            font-weight: bold;
            font-size: 14px;
        }
        .content { 
            padding: 30px; 
        }
        .alert-box { 
            background-color: #fff3cd; 
            border: 1px solid #ffeaa7; 
            border-radius: 8px; 
            padding: 20px; 
            margin: 25px 0; 
        }
        .alert-box h3 {
            margin: 0 0 10px 0;
            color: #856404;
            font-size: 18px;
        }
        .alert-box p {
            margin: 0;
            color: #856404;
        }
        .summary-cards { 
            display: flex; 
            gap: 15px; 
            margin: 25px 0; 
            flex-wrap: wrap;
        }
        .summary-card { 
            flex: 1; 
            min-width: 180px;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-left: 4px solid #667eea;
            border-radius: 8px; 
            padding: 20px; 
            text-align: center; 
        }
        .summary-card.critical { 
            border-left-color: #dc3545; 
            background: linear-gradient(135deg, #fee 0%, #fdd 100%);
        }
        .summary-card.warning { 
            border-left-color: #ffc107; 
            background: linear-gradient(135deg, #fff9e6 0%, #fff3cd 100%);
        }
        .summary-card .number { 
            font-size: 36px; 
            font-weight: bold; 
            color: #dc3545; 
            margin-bottom: 5px; 
        }
        .summary-card.warning .number { 
            color: #fd7e14; 
        }
        .summary-card .label { 
            font-size: 13px; 
            color: #495057; 
            font-weight: 600;
            text-transform: uppercase; 
        }
        .category-section {
            margin: 30px 0;
        }
        .category-header { 
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white; 
            padding: 15px 20px; 
            border-radius: 8px 8px 0 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 18px;
            font-weight: bold;
        }
        .category-header.warning {
            background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);
        }
        .category-header.info {
            background: linear-gradient(135deg, #17a2b8 0%, #138496 100%);
        }
        .category-header .badge {
            background: rgba(255,255,255,0.3);
            padding: 5px 15px;
            border-radius: 15px;
            font-size: 14px;
        }
        table { 
            width: 100%; 
            border-collapse: collapse; 
            margin: 0;
            background: white;
        }
        th { 
            background-color: #f8f9fa; 
            color: #495057; 
            font-weight: bold; 
            text-align: left; 
            padding: 14px 16px; 
            border: 1px solid #dee2e6;
            font-size: 12px;
            text-transform: uppercase;
        }
        td { 
            padding: 14px 16px; 
            border: 1px solid #dee2e6; 
            color: #495057; 
        }
        tbody tr:nth-child(even) { 
            background-color: #f8f9fa; 
        }
        tbody tr:hover { 
            background-color: #e9ecef; 
        }
        .table-wrapper {
            border-radius: 0 0 8px 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .action-box { 
            background-color: #d1ecf1; 
            border: 1px solid #bee5eb; 
            border-radius: 8px; 
            padding: 20px; 
            margin: 25px 0; 
            text-align: center;
        }
        .action-box h4 {
            margin: 0 0 15px 0;
            color: #0c5460;
            font-size: 18px;
        }
        .action-button { 
            display: inline-block; 
            background: linear-gradient(135deg, #007bff 0%, #0056b3 100%);
            color: white; 
            padding: 14px 30px; 
            text-decoration: none; 
            border-radius: 25px; 
            margin: 15px 0; 
            font-weight: bold; 
            font-size: 16px;
            box-shadow: 0 3px 6px rgba(0,0,0,0.2);
        }
        .action-button:hover { 
            background: linear-gradient(135deg, #0056b3 0%, #003d82 100%);
        }
        .empty-state {
            text-align: center;
            padding: 60px 30px;
        }
        .empty-state-icon {
            font-size: 72px;
            margin-bottom: 20px;
        }
        .empty-state h2 {
            color: #28a745;
            font-size: 28px;
            margin-bottom: 10px;
        }
        .empty-state p {
            color: #6c757d;
            font-size: 16px;
        }
        .footer { 
            background-color: #f8f9fa; 
            padding: 25px; 
            text-align: center; 
            font-size: 13px; 
            color: #6c757d; 
            border-top: 1px solid #dee2e6; 
        }
        .footer-logo {
            font-weight: bold;
            color: #667eea;
            font-size: 18px;
            margin-bottom: 10px;
        }
        @media only screen and (max-width: 600px) {
            .summary-cards { flex-direction: column; }
            .summary-card { min-width: 100%; }
            table { font-size: 12px; }
            th, td { padding: 10px; }
        }
    </style>
    """
    
    # Calcula estatísticas
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
    
    # Define título baseado no tipo
    if is_global:
        title = "📊 Relatório Global Consolidado"
        subtitle = f"Visão de Todas as Unidades • {date.today().strftime('%d/%m/%Y')}"
        header_class = "header global"
    elif unit_name:
        title = f"⏰ Alerta de Vencimentos - {unit_name}"
        subtitle = f"Ações necessárias nos próximos dias"
        header_class = "header"
    else:
        title = "📋 Relatório de Conformidade"
        subtitle = f"Relatório do Sistema • {date.today().strftime('%d/%m/%Y')}"
        header_class = "header"
    
    # Monta HTML
    html_body = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {html_style}
</head>
<body>
    <div class="container">
        <div class="{header_class}">
            <h1>{title}</h1>
            <p>{subtitle}</p>
    """
    
    if not is_global and unit_name:
        html_body += f'<div class="unit-badge">📍 {unit_name}</div>'
    
    html_body += """
        </div>
        
        <div class="content">
    """
    
    if has_content:
        html_body += f"""
            <div class="alert-box">
                <h3>📋 Resumo do Alerta</h3>
                <p><strong>{total_critical + total_warning + total_info} item(ns)</strong> necessitam de atenção.</p>
            </div>

            <div class="summary-cards">
                <div class="summary-card critical">
                    <div class="number">{total_critical}</div>
                    <div class="label">🔴 Vencidos</div>
                </div>
                <div class="summary-card warning">
                    <div class="number">{total_warning}</div>
                    <div class="label">⚠️ Vencendo em Breve</div>
                </div>
                <div class="summary-card">
                    <div class="number">{total_info}</div>
                    <div class="label">📋 Para Monitorar</div>
                </div>
            </div>
        """
    
    # Configuração de colunas
    base_cols_docs_empresa = ['empresa', 'tipo_documento', 'vencimento']
    base_cols_aso = ['empresa', 'nome_funcionario', 'tipo_aso', 'vencimento']
    base_cols_treinamento = ['empresa', 'nome_funcionario', 'norma', 'vencimento']
    
    if is_global:
        base_cols_docs_empresa = ['unidade'] + base_cols_docs_empresa
        base_cols_aso = ['unidade'] + base_cols_aso
        base_cols_treinamento = ['unidade'] + base_cols_treinamento
    
    report_configs = {
        "Documentos da Empresa Vencidos": {
            "cols": base_cols_docs_empresa,
            "priority": "critical",
            "icon": "🔴",
            "title": "Documentos da Empresa Vencidos"
        },
        "ASOs Vencidos": {
            "cols": base_cols_aso,
            "priority": "critical",
            "icon": "🔴",
            "title": "ASOs Vencidos"
        },
        "Treinamentos Vencidos": {
            "cols": base_cols_treinamento,
            "priority": "critical",
            "icon": "🔴",
            "title": "Treinamentos Vencidos"
        },
        "Documentos da Empresa que vencem nos próximos 30 dias": {
            "cols": base_cols_docs_empresa,
            "priority": "warning",
            "icon": "⚠️",
            "title": "Docs. Empresa - Próximos 30 dias"
        },
        "ASOs que vencem em até 15 dias": {
            "cols": base_cols_aso,
            "priority": "warning",
            "icon": "⚠️",
            "title": "ASOs - Próximos 15 dias"
        },
        "Treinamentos que vencem em até 15 dias": {
            "cols": base_cols_treinamento,
            "priority": "warning",
            "icon": "⚠️",
            "title": "Treinamentos - Próximos 15 dias"
        },
        "ASOs que vencem entre 16 e 45 dias": {
            "cols": base_cols_aso,
            "priority": "info",
            "icon": "📋",
            "title": "ASOs - 16 a 45 dias"
        },
        "Treinamentos que vencem entre 16 e 45 dias": {
            "cols": base_cols_treinamento,
            "priority": "info",
            "icon": "📋",
            "title": "Treinamentos - 16 a 45 dias"
        },
    }
    
    # Renderiza categorias
    for category_name, config in report_configs.items():
        if category_name in categorized_data and not categorized_data[category_name].empty:
            data_df = categorized_data[category_name]
            count = len(data_df)
            priority = config['priority']
            icon = config['icon']
            display_title = config['title']
            
            html_body += f"""
            <div class="category-section">
                <div class="category-header {priority}">
                    <span>{icon} {display_title}</span>
                    <span class="badge">{count} item{'ns' if count != 1 else ''}</span>
                </div>
                <div class="table-wrapper">
            """
            
            try:
                df_display = data_df.copy()
                
                if 'vencimento' in df_display.columns:
                    df_display['vencimento'] = pd.to_datetime(
                        df_display['vencimento'], errors='coerce', dayfirst=True
                    ).dt.strftime('%d/%m/%Y')
                    df_display = df_display.dropna(subset=['vencimento'])
                
                cols_to_show = [col for col in config['cols'] if col in df_display.columns]
                
                if cols_to_show:
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
                    
                    html_table = df_display.to_html(
                        index=False, 
                        border=0, 
                        na_rep='N/A',
                        escape=True,
                        classes='data-table'
                    )
                    
                    html_body += html_table
                else:
                    html_body += "<p style='padding: 20px; text-align: center; color: #6c757d;'>Dados incompatíveis</p>"
                    
            except Exception as e:
                logger.error(f"Erro ao processar '{category_name}': {e}")
                html_body += f"<p style='padding: 20px; text-align: center; color: #dc3545;'>Erro: {str(e)}</p>"
            
            html_body += """
                </div>
            </div>
            """
    
    # Empty state ou action box
    if not has_content:
        html_body += """
            <div class="empty-state">
                <div class="empty-state-icon">✅</div>
                <h2>Tudo em Ordem!</h2>
                <p>Não há pendências de vencimentos.</p>
                <p style="margin-top: 10px;">Continue o excelente trabalho mantendo a conformidade! 🎉</p>
            </div>
        """
    else:
        html_body += """
            <div class="action-box">
                <h4>🎯 Ação Necessária</h4>
                <p>Acesse o sistema para regularizar as pendências e manter a conformidade:</p>
                <a href="https://segma-sis.streamlit.app" class="action-button">🚀 Acessar SEGMA-SIS</a>
            </div>
        """
    
    html_body += """
            <p style="margin-top: 30px;">Atenciosamente,<br>
            <strong>Sistema SEGMA-SIS</strong></p>
        </div>
        
        <div class="footer">
            <div class="footer-logo">SEGMA-SIS</div>
            <p>Esta é uma notificação automática do sistema de gestão.<br>
            Para alterar a frequência dos alertas, acesse as configurações do sistema.</p>
        </div>
    </div>
</body>
</html>
    """
    
    return html_body
    
def send_smtp_email(html_body: str, config: dict, receiver_email: str, subject_suffix: str = ""):
    """
    ✅ MODIFICADO: Envia e-mail com destinatário configurável
    
    Args:
        html_body: Corpo HTML do e-mail
        config: Dicionário de configuração SMTP
        receiver_email: E-mail do destinatário
        subject_suffix: Sufixo adicional para o assunto (ex: nome da unidade)
    """
    base_subject = f"📊 Relatório SEGMA-SIS - {date.today().strftime('%d/%m/%Y')}"
    subject = f"{base_subject} - {subject_suffix}" if subject_suffix else base_subject
    
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"SEGMA-SIS Sistema <{config['sender_email']}>"
    message["To"] = receiver_email
    message["Reply-To"] = "noreply@segma-sis.com"
    
    message.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    try:
        logger.info(f"Conectando ao servidor SMTP {config['smtp_server']}...")
        with smtplib.SMTP_SSL(config["smtp_server"], config["smtp_port"], context=context) as server:
            logger.info("Fazendo login...")
            server.login(config["sender_email"], config["sender_password"])
            logger.info(f"Enviando e-mail para {receiver_email}...")
            server.sendmail(config["sender_email"], receiver_email.split(','), message.as_string())
            logger.info(f"✅ E-mail enviado com sucesso para {receiver_email}!")
    except Exception as e:
        logger.error(f"❌ Falha ao enviar e-mail para {receiver_email}: {e}")
        raise

def main():
    """
    ✅ CORRIGIDO: Função principal com envio segmentado de e-mails
    """
    logger.info("🚀 Iniciando script de notificação de vencimentos...")
    
    try:
        config = get_smtp_config()
        
        matrix_manager = MatrixManager()
        all_units = matrix_manager.get_all_units()
        
        if not all_units:
            logger.warning("⚠️ Nenhuma unidade encontrada na matriz. Encerrando.")
            return
        
        # ✅ Dicionário para armazenar dados de cada unidade
        all_units_categorized_data = {}
        units_with_pendencies = {}
        successful_units = 0
        
        for unit in all_units:
            unit_name = unit.get('nome_unidade')
            spreadsheet_id = unit.get('spreadsheet_id')
            folder_id = unit.get('folder_id')
            unit_email = unit.get('email_contato')
            
            if not spreadsheet_id:
                logger.warning(f"⚠️ Unidade '{unit_name}' sem spreadsheet_id. Pulando.")
                continue
            
            logger.info(f"📊 Processando unidade: {unit_name}")
            
            try:
                folder_id_safe = str(folder_id) if folder_id else ""
                
                employee_manager = EmployeeManager(
                    spreadsheet_id=spreadsheet_id, 
                    folder_id=folder_id_safe
                )
                docs_manager = CompanyDocsManager(
                    spreadsheet_id=spreadsheet_id, 
                    folder_id=folder_id_safe
                )
                
                # ✅ CORREÇÃO CRÍTICA: Verifica se há DADOS antes de processar
                if not employee_manager.data_loaded_successfully:
                    logger.warning(f"⚠️ Dados de funcionários não carregados para '{unit_name}'. Pulando.")
                    continue
                    
                if not docs_manager.data_loaded_successfully:
                    logger.warning(f"⚠️ Dados de documentos não carregados para '{unit_name}'. Pulando.")
                    continue
                
                # ✅ CORREÇÃO CRÍTICA: Verifica se há empresas ANTES de categorizar
                if employee_manager.companies_df.empty:
                    logger.info(f"ℹ️ Unidade '{unit_name}' não possui empresas cadastradas. Pulando.")
                    successful_units += 1  # Conta como processada, mas sem dados
                    continue
                
                # ✅ CORREÇÃO CRÍTICA: Verifica se há empresas ATIVAS
                active_companies = employee_manager.companies_df[
                    employee_manager.companies_df['status'].str.lower() == 'ativo'
                ]
                
                if active_companies.empty:
                    logger.info(f"ℹ️ Unidade '{unit_name}' não possui empresas ativas. Pulando.")
                    successful_units += 1  # Conta como processada, mas sem dados
                    continue
                
                # Categoriza os dados
                categorized_data = categorize_expirations_for_unit(employee_manager, docs_manager)
                
                # ✅ CORREÇÃO CRÍTICA: Verifica se realmente há pendências
                has_pendencies = False
                for category_name, category_df in categorized_data.items():
                    if not category_df.empty:
                        has_pendencies = True
                        break
                
                if has_pendencies:
                    # Adiciona nome da unidade a todos os DataFrames
                    for category_name, category_df in categorized_data.items():
                        if not category_df.empty:
                            try:
                                category_df['unidade'] = unit_name
                            except Exception as e:
                                logger.error(f"❌ Erro ao adicionar nome da unidade '{unit_name}': {e}")
                    
                    # ✅ SOMENTE adiciona se tiver pendências
                    all_units_categorized_data[unit_name] = categorized_data
                    units_with_pendencies[unit_name] = {
                        'data': categorized_data,
                        'email': unit_email
                    }
                    
                    logger.info(f"✅ Unidade '{unit_name}' tem {sum(len(df) for df in categorized_data.values() if not df.empty)} pendência(s).")
                else:
                    logger.info(f"ℹ️ Unidade '{unit_name}' processada - nenhuma pendência encontrada.")
                
                successful_units += 1
                
            except Exception as e:
                logger.error(f"❌ Erro ao processar unidade '{unit_name}': {e}", exc_info=True)
                continue

        if successful_units == 0:
            logger.error("❌ Nenhuma unidade foi processada com sucesso. Encerrando.")
            return

        logger.info(f"✅ Total de {successful_units} unidades processadas.")
        logger.info(f"📊 Unidades com pendências: {len(units_with_pendencies)}")

        # ========================================
        # PARTE 1: ENVIO DE E-MAILS POR UNIDADE
        # ========================================
        emails_sent_to_units = 0
        
        if units_with_pendencies:
            logger.info(f"📧 Iniciando envio de e-mails para {len(units_with_pendencies)} unidade(s) com pendências...")
            
            for unit_name, unit_info in units_with_pendencies.items():
                unit_email = unit_info.get('email')
                unit_data = unit_info.get('data')
                
                if not unit_email or pd.isna(unit_email):
                    logger.warning(f"⚠️ Unidade '{unit_name}' não possui e-mail configurado. Pulando envio individual.")
                    continue
                
                try:
                    logger.info(f"📧 Gerando e-mail para unidade: {unit_name}")
                    
                    email_body = format_email_body(
                        categorized_data=unit_data,
                        unit_name=unit_name,
                        is_global=False
                    )
                    
                    send_smtp_email(
                        html_body=email_body,
                        config=config,
                        receiver_email=unit_email,
                        subject_suffix=f"Unidade {unit_name}"
                    )
                    
                    emails_sent_to_units += 1
                    logger.info(f"✅ E-mail enviado com sucesso para '{unit_name}' ({unit_email})")
                    
                except Exception as e:
                    logger.error(f"❌ Falha ao enviar e-mail para unidade '{unit_name}': {e}")
                    continue
            
            logger.info(f"✅ {emails_sent_to_units} e-mail(s) enviado(s) para unidades específicas.")
        else:
            logger.info("ℹ️ Nenhuma unidade possui pendências. E-mails individuais não serão enviados.")

        # ========================================
        # PARTE 2: ENVIO DO E-MAIL GLOBAL CONSOLIDADO
        # ========================================
        
        # ✅ CORREÇÃO CRÍTICA: Só consolida se houver pendências
        if not all_units_categorized_data:
            logger.info("ℹ️ Nenhuma unidade possui pendências. E-mail global não será enviado.")
            logger.info("🎉 Script finalizado com sucesso.")
            return
        
        logger.info("📧 Gerando relatório global consolidado...")
        
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

        # ✅ Verifica se há pendências para o relatório global
        has_global_pendencies = any(not df.empty for df in final_report_data.values())
        
        if not has_global_pendencies:
            logger.info("ℹ️ Nenhuma pendência encontrada globalmente após consolidação. E-mail global não será enviado.")
        else:
            try:
                logger.info("📧 Gerando e-mail global consolidado...")
                
                global_email_body = format_email_body(
                    categorized_data=final_report_data,
                    unit_name=None,
                    is_global=True
                )
                
                send_smtp_email(
                    html_body=global_email_body,
                    config=config,
                    receiver_email=config['global_receiver_email'],
                    subject_suffix="Relatório Global Consolidado"
                )
                
                logger.info(f"✅ E-mail global enviado com sucesso para {config['global_receiver_email']}!")
                
            except Exception as e:
                logger.error(f"❌ Falha ao enviar e-mail global: {e}")
        
        # ========================================
        # RESUMO FINAL
        # ========================================
        logger.info("=" * 60)
        logger.info("📊 RESUMO DA EXECUÇÃO:")
        logger.info(f"   • Unidades processadas: {successful_units}")
        logger.info(f"   • Unidades com pendências: {len(units_with_pendencies)}")
        logger.info(f"   • E-mails enviados para unidades: {emails_sent_to_units}")
        logger.info(f"   • E-mail global enviado: {'Sim' if has_global_pendencies else 'Não (sem pendências)'}")
        logger.info("=" * 60)
        logger.info("🎉 Script finalizado com sucesso.")

    except Exception as e:
        logger.error(f"💥 Erro fatal no script: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
