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
    Template com identidade visual ISF IA
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
            max-width: 800px; 
            margin: 0 auto; 
            background-color: white; 
            border-radius: 10px; 
            overflow: hidden; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
        }
        .header { 
            background: linear-gradient(135deg, #667eea, #764ba2); 
            color: white; 
            padding: 20px; 
            text-align: center; 
        }
        .header.global {
            background: linear-gradient(135deg, #dc3545, #c82333);
        }
        .header h1 { 
            margin: 0; 
            font-size: 24px; 
        }
        .header p { 
            margin: 5px 0 0 0; 
            font-size: 14px; 
        }
        .content { 
            padding: 30px; 
        }
        .alert-box { 
            background-color: #fff3cd; 
            border: 1px solid #ffeaa7; 
            border-radius: 5px; 
            padding: 15px; 
            margin: 20px 0; 
        }
        .alert-box h3 {
            margin: 0 0 10px 0;
            font-size: 16px;
        }
        .alert-box p {
            margin: 0;
        }
        .summary-box { 
            background-color: #d1ecf1; 
            border: 1px solid #bee5eb; 
            border-radius: 5px; 
            padding: 15px; 
            margin: 20px 0; 
        }
        .summary-box h4 {
            margin: 0 0 10px 0;
        }
        table { 
            width: 100%; 
            border-collapse: collapse; 
            margin: 20px 0; 
        }
        th, td { 
            border: 1px solid #ddd; 
            padding: 12px; 
            text-align: left; 
        }
        th { 
            background-color: #f8f9fa; 
            font-weight: bold; 
            color: #495057; 
        }
        tbody tr:nth-child(even) { 
            background-color: #f8f9fa; 
        }
        tbody tr:hover { 
            background-color: #e9ecef; 
        }
        .priority-critical { 
            color: #dc3545; 
            font-weight: bold; 
        }
        .priority-high { 
            color: #fd7e14; 
            font-weight: bold; 
        }
        .priority-medium { 
            color: #ffc107; 
            font-weight: bold; 
        }
        .action-button { 
            display: inline-block; 
            background-color: #007bff; 
            color: white; 
            padding: 12px 25px; 
            text-decoration: none; 
            border-radius: 5px; 
            margin: 20px 0; 
            font-weight: bold; 
        }
        .action-button:hover { 
            background-color: #0056b3; 
        }
        .footer { 
            background-color: #f8f9fa; 
            padding: 20px; 
            text-align: center; 
            font-size: 12px; 
            color: #6c757d; 
            border-top: 1px solid #dee2e6; 
        }
        .icon { 
            font-size: 18px; 
            margin-right: 8px; 
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
    total_items = total_critical + total_warning + total_info
    
    # Define título
    if is_global:
        title = "Relatório Global Consolidado - SEGMA-SIS"
        subtitle = f"Visão de todas as unidades - {date.today().strftime('%d/%m/%Y')}"
        header_class = "header global"
    elif unit_name:
        title = f"Alerta de Vencimentos - {unit_name}"
        subtitle = f"Documentos necessitando atenção - {date.today().strftime('%d/%m/%Y')}"
        header_class = "header"
    else:
        title = "Relatório de Conformidade - SEGMA-SIS"
        subtitle = f"Sistema de Gestão - {date.today().strftime('%d/%m/%Y')}"
        header_class = "header"
    
    # Inicia HTML
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
        </div>
        
        <div class="content">
            <p>Olá,</p>
    """
    
    if has_content:
        html_body += f"""
            <div class="alert-box">
                <h3>Resumo do Alerta</h3>
                <p><strong>{total_items} documento(s)</strong> necessitam de atenção.</p>
            </div>
        """
        
        # Configuração de colunas
        base_cols_docs = ['empresa', 'tipo_documento', 'vencimento']
        base_cols_aso = ['empresa', 'nome_funcionario', 'tipo_aso', 'vencimento']
        base_cols_treinamento = ['empresa', 'nome_funcionario', 'norma', 'vencimento']
        
        if is_global:
            base_cols_docs = ['unidade'] + base_cols_docs
            base_cols_aso = ['unidade'] + base_cols_aso
            base_cols_treinamento = ['unidade'] + base_cols_treinamento
        
        configs = {
            "Documentos da Empresa Vencidos": {
                "cols": base_cols_docs,
                "title": "Documentos da Empresa Vencidos",
                "icon": "🔴"
            },
            "ASOs Vencidos": {
                "cols": base_cols_aso,
                "title": "ASOs Vencidos",
                "icon": "🔴"
            },
            "Treinamentos Vencidos": {
                "cols": base_cols_treinamento,
                "title": "Treinamentos Vencidos",
                "icon": "🔴"
            },
            "Documentos da Empresa que vencem nos próximos 30 dias": {
                "cols": base_cols_docs,
                "title": "Documentos da Empresa - Próximos 30 dias",
                "icon": "🟡"
            },
            "ASOs que vencem em até 15 dias": {
                "cols": base_cols_aso,
                "title": "ASOs - Próximos 15 dias",
                "icon": "🟡"
            },
            "Treinamentos que vencem em até 15 dias": {
                "cols": base_cols_treinamento,
                "title": "Treinamentos - Próximos 15 dias",
                "icon": "🟡"
            },
            "ASOs que vencem entre 16 e 45 dias": {
                "cols": base_cols_aso,
                "title": "ASOs - 16 a 45 dias",
                "icon": "🟢"
            },
            "Treinamentos que vencem entre 16 e 45 dias": {
                "cols": base_cols_treinamento,
                "title": "Treinamentos - 16 a 45 dias",
                "icon": "🟢"
            },
        }
        
        # Renderiza tabelas
        for category_name, config in configs.items():
            if category_name in categorized_data and not categorized_data[category_name].empty:
                df = categorized_data[category_name]
                
                html_body += f"""
            <h3>{config['icon']} {config['title']}</h3>
            <table>
                <thead>
                    <tr>
                """
                
                # Cabeçalhos
                column_names = {
                    'unidade': 'Unidade',
                    'empresa': 'Empresa',
                    'tipo_documento': 'Documento',
                    'nome_funcionario': 'Funcionário',
                    'tipo_aso': 'Tipo',
                    'norma': 'Norma',
                    'vencimento': 'Vencimento'
                }
                
                try:
                    df_display = df.copy()
                    
                    if 'vencimento' in df_display.columns:
                        df_display['vencimento'] = pd.to_datetime(
                            df_display['vencimento'], errors='coerce', dayfirst=True
                        ).dt.strftime('%d/%m/%Y')
                        df_display = df_display.dropna(subset=['vencimento'])
                    
                    cols_to_show = [col for col in config['cols'] if col in df_display.columns]
                    
                    if cols_to_show:
                        df_display = df_display[cols_to_show]
                        
                        # Headers
                        for col in cols_to_show:
                            html_body += f"<th>{column_names.get(col, col)}</th>"
                        
                        html_body += """
                    </tr>
                </thead>
                <tbody>
                        """
                        
                        # Linhas
                        for _, row in df_display.iterrows():
                            html_body += "<tr>"
                            for col in cols_to_show:
                                value = row[col] if pd.notna(row[col]) else 'N/A'
                                html_body += f"<td>{value}</td>"
                            html_body += "</tr>"
                        
                        html_body += """
                </tbody>
            </table>
                        """
                    
                except Exception as e:
                    logger.error(f"Erro ao renderizar '{category_name}': {e}")
                    html_body += f"<p>Erro ao processar dados: {str(e)}</p></table>"
        
        # Action box
        html_body += """
            <div class="summary-box">
                <h4>Ação Necessária</h4>
                <p>Acesse o sistema para regularizar as pendências e manter a conformidade:</p>
                <a href="https://segma-sis.streamlit.app" class="action-button">Acessar Sistema SEGMA-SIS</a>
            </div>

            <div class="alert-box">
                <h4>Importante</h4>
                <ul>
                    <li>Documentos vencidos comprometem a conformidade</li>
                    <li>Não conformidades podem gerar multas em auditorias</li>
                    <li>Regularize as pendências com antecedência</li>
                </ul>
            </div>
        """
    else:
        html_body += """
            <div class="summary-box">
                <h4>Tudo em Ordem!</h4>
                <p>Não há pendências de vencimentos nesta unidade.</p>
                <p>Continue o excelente trabalho mantendo a conformidade!</p>
            </div>
        """
    
    html_body += """
            <p>Atenciosamente,<br>
            <strong>Equipe SEGMA-SIS</strong></p>
        </div>
        
        <div class="footer">
            <p>Esta é uma notificação automática do sistema de gestão SEGMA-SIS.<br>
            Para alterar a frequência dos alertas, acesse seu perfil no sistema.</p>
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
    ✅ CORRIGIDO: Função principal com validação rigorosa de dados
    """
    logger.info("🚀 Iniciando script de notificação de vencimentos...")
    
    try:
        config = get_smtp_config()
        
        matrix_manager = MatrixManager()
        all_units = matrix_manager.get_all_units()
        
        if not all_units:
            logger.warning("⚠️ Nenhuma unidade encontrada na matriz. Encerrando.")
            return
        
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
                
                # ✅ VALIDAÇÃO 1: Dados carregados
                if not employee_manager.data_loaded_successfully:
                    logger.warning(f"⚠️ Dados de funcionários não carregados para '{unit_name}'.")
                    successful_units += 1
                    continue
                    
                if not docs_manager.data_loaded_successfully:
                    logger.warning(f"⚠️ Dados de documentos não carregados para '{unit_name}'.")
                    successful_units += 1
                    continue
                
                # ✅ VALIDAÇÃO 2: Empresas existem
                if employee_manager.companies_df.empty:
                    logger.info(f"ℹ️ Unidade '{unit_name}' sem empresas cadastradas.")
                    successful_units += 1
                    continue
                
                # ✅ VALIDAÇÃO 3: Empresas ativas existem
                active_companies = employee_manager.companies_df[
                    employee_manager.companies_df['status'].str.lower() == 'ativo'
                ].copy()
                
                if active_companies.empty:
                    logger.info(f"ℹ️ Unidade '{unit_name}' sem empresas ativas.")
                    successful_units += 1
                    continue
                
                # ✅ VALIDAÇÃO 4: Funcionários ativos existem
                if not employee_manager.employees_df.empty:
                    active_employees = employee_manager.employees_df[
                        (employee_manager.employees_df['status'].str.lower() == 'ativo') &
                        (employee_manager.employees_df['empresa_id'].isin(active_companies['id']))
                    ].copy()
                else:
                    active_employees = pd.DataFrame()
                
                # ✅ VALIDAÇÃO 5: Há algo para verificar
                has_employees = not active_employees.empty
                has_docs = not docs_manager.docs_df.empty
                
                if not has_employees and not has_docs:
                    logger.info(f"ℹ️ Unidade '{unit_name}' sem funcionários ativos nem documentos.")
                    successful_units += 1
                    continue
                
                # Categoriza os dados
                categorized_data = categorize_expirations_for_unit(employee_manager, docs_manager)
                
                # ✅ VALIDAÇÃO 6: Contagem rigorosa de pendências
                total_items = 0
                for category_name, category_df in categorized_data.items():
                    if not category_df.empty:
                        # ✅ CRÍTICO: Valida que os dados são REALMENTE desta unidade
                        # Remove qualquer linha que não seja desta unidade (por segurança)
                        if 'unidade' in category_df.columns:
                            category_df_clean = category_df[category_df['unidade'] == unit_name].copy()
                            total_items += len(category_df_clean)
                        else:
                            total_items += len(category_df)
                
                if total_items == 0:
                    logger.info(f"ℹ️ Unidade '{unit_name}' processada - nenhuma pendência encontrada.")
                    successful_units += 1
                    continue
                
                # ✅ Adiciona nome da unidade ANTES de armazenar
                for category_name, category_df in categorized_data.items():
                    if not category_df.empty:
                        try:
                            # Remove coluna 'unidade' se existir (para evitar duplicação)
                            if 'unidade' in category_df.columns:
                                category_df.drop(columns=['unidade'], inplace=True)
                            # Adiciona novamente
                            category_df['unidade'] = unit_name
                        except Exception as e:
                            logger.error(f"❌ Erro ao processar unidade '{unit_name}': {e}")
                
                # ✅ Armazena apenas se tiver pendências
                all_units_categorized_data[unit_name] = categorized_data
                units_with_pendencies[unit_name] = {
                    'data': categorized_data,
                    'email': unit_email
                }
                
                logger.info(f"✅ Unidade '{unit_name}' tem {total_items} pendência(s).")
                successful_units += 1
                
            except Exception as e:
                logger.error(f"❌ Erro ao processar unidade '{unit_name}': {e}", exc_info=True)
                continue

        if successful_units == 0:
            logger.error("❌ Nenhuma unidade processada com sucesso.")
            return

        logger.info(f"✅ Total de {successful_units} unidades processadas.")
        logger.info(f"📊 Unidades com pendências: {len(units_with_pendencies)}")

        # ========================================
        # PARTE 1: ENVIO DE E-MAILS POR UNIDADE
        # ========================================
        emails_sent_to_units = 0
        
        if units_with_pendencies:
            logger.info(f"📧 Iniciando envio para {len(units_with_pendencies)} unidade(s)...")
            
            for unit_name, unit_info in units_with_pendencies.items():
                unit_email = unit_info.get('email')
                unit_data = unit_info.get('data')
                
                if not unit_email or pd.isna(unit_email):
                    logger.warning(f"⚠️ Unidade '{unit_name}' sem e-mail configurado.")
                    continue
                
                try:
                    logger.info(f"📧 Gerando e-mail para: {unit_name}")
                    
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
                    logger.info(f"✅ E-mail enviado para '{unit_name}'")
                    
                except Exception as e:
                    logger.error(f"❌ Falha no envio para '{unit_name}': {e}")
                    continue
            
            logger.info(f"✅ {emails_sent_to_units} e-mail(s) enviado(s).")
        else:
            logger.info("ℹ️ Nenhuma unidade com pendências.")

        # ========================================
        # PARTE 2: E-MAIL GLOBAL
        # ========================================
        
        if not all_units_categorized_data:
            logger.info("ℹ️ Nenhuma pendência global. E-mail não será enviado.")
            logger.info("🎉 Script finalizado.")
            return
        
        logger.info("📧 Gerando relatório global...")
        
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

        has_global_pendencies = any(not df.empty for df in final_report_data.values())
        
        if not has_global_pendencies:
            logger.info("ℹ️ Consolidação resultou em zero pendências.")
        else:
            try:
                logger.info("📧 Gerando e-mail global...")
                
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
                
                logger.info(f"✅ E-mail global enviado!")
                
            except Exception as e:
                logger.error(f"❌ Falha no e-mail global: {e}")
        
        # ========================================
        # RESUMO FINAL
        # ========================================
        logger.info("=" * 60)
        logger.info("📊 RESUMO DA EXECUÇÃO:")
        logger.info(f"   • Unidades processadas: {successful_units}")
        logger.info(f"   • Unidades com pendências: {len(units_with_pendencies)}")
        logger.info(f"   • E-mails enviados: {emails_sent_to_units}")
        logger.info(f"   • E-mail global: {'Sim' if has_global_pendencies else 'Não'}")
        logger.info("=" * 60)
        logger.info("🎉 Script finalizado.")

    except Exception as e:
        logger.error(f"💥 Erro fatal: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
