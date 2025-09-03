import streamlit as st
import pandas as pd
from datetime import date
from operations.employee import EmployeeManager


def calculate_overall_metrics(employee_manager: EmployeeManager) -> dict:
    today = date.today()
    metrics = {
        'total_companies': 0,
        'companies_with_pendencies': 0,
        'total_pendencies': 0,
        'most_pendent_company': ('Nenhuma', 0)
    }

    companies_df = employee_manager.companies_df
    if companies_df.empty:
        return metrics

    metrics['total_companies'] = len(companies_df)
    pendencies_by_company = {}
    
    # Garante que a variável sempre exista, mesmo que vazia.
    if not employee_manager.employees_df.empty:
        employee_to_company = employee_manager.employees_df.set_index('id')['empresa_id']
    else:
        employee_to_company = pd.Series(dtype=str) # Cria uma Series vazia, mas definida

    # Processar ASOs Vencidos
    if not employee_manager.aso_df.empty:
        asos = employee_manager.aso_df.copy()
        # Garante que a coluna de data exista antes de usar
        if 'vencimento' in asos.columns:
            asos['vencimento_dt'] = pd.to_datetime(asos['vencimento'], errors='coerce').dt.date
            latest_asos = asos[~asos['tipo_aso'].str.lower().isin(['demissional'])].dropna(subset=['vencimento_dt'])
            if not latest_asos.empty:
                latest_asos = latest_asos.sort_values('data_aso', ascending=False).groupby('funcionario_id').head(1)
                expired_asos = latest_asos[latest_asos['vencimento_dt'] < today].copy()
                
                # Adiciona a verificação de segurança
                if not expired_asos.empty and not employee_to_company.empty:
                    expired_asos['empresa_id'] = expired_asos['funcionario_id'].map(employee_to_company)
                    aso_pendencies = expired_asos.groupby('empresa_id').size()
                    for company_id, count in aso_pendencies.items():
                        pendencies_by_company[company_id] = pendencies_by_company.get(company_id, 0) + count

    # Processar Treinamentos Vencidos
    if not employee_manager.training_df.empty:
        trainings = employee_manager.training_df.copy()
        # Garante que a coluna de data exista antes de usar
        if 'vencimento' in trainings.columns:
            trainings['vencimento_dt'] = pd.to_datetime(trainings['vencimento'], errors='coerce').dt.date
            latest_trainings = trainings.dropna(subset=['vencimento_dt'])
            if not latest_trainings.empty:
                latest_trainings = latest_trainings.sort_values('data', ascending=False).groupby(['funcionario_id', 'norma']).head(1)
                expired_trainings = latest_trainings[latest_trainings['vencimento_dt'] < today].copy()
                
                # Adiciona a verificação de segurança
                if not expired_trainings.empty and not employee_to_company.empty:
                    expired_trainings['empresa_id'] = expired_trainings['funcionario_id'].map(employee_to_company)
                    training_pendencies = expired_trainings.groupby('empresa_id').size()
                    for company_id, count in training_pendencies.items():
                        pendencies_by_company[company_id] = pendencies_by_company.get(company_id, 0) + count

    if pendencies_by_company:
        metrics['companies_with_pendencies'] = len(pendencies_by_company)
        metrics['total_pendencies'] = sum(pendencies_by_company.values())
        most_pendent_id = max(pendencies_by_company, key=pendencies_by_company.get)
        company_name = employee_manager.get_company_name(most_pendent_id) or f"ID: {most_pendent_id}"
        metrics['most_pendent_company'] = (company_name, pendencies_by_company[most_pendent_id])

    return metrics

def display_minimalist_metrics(employee_manager: EmployeeManager):
    """
    Calcula e exibe as métricas de pendências em um formato visualmente
    aprimorado, com ícones, cores e informações mais claras.
    """
    metrics = calculate_overall_metrics(employee_manager)
    
    st.markdown("---")
    
    
    # 1. Indicador de Saúde Geral
    total_companies = metrics['total_companies']
    companies_with_pendencies = metrics['companies_with_pendencies']
    
    if total_companies > 0:
        health_score = 100 * (1 - (companies_with_pendencies / total_companies))
        if health_score == 100:
            st.success(f"**Saúde Geral: Excelente ({health_score:.0f}%)**")
            st.write("Parabéns! Nenhuma empresa possui pendências de documentos.")
        elif health_score >= 75:
            st.info(f"**Saúde Geral: Bom ({health_score:.0f}%)**")
        else:
            st.error(f"**Saúde Geral: Atenção Necessária ({health_score:.0f}%)**")

    # 2. Métricas Detalhadas em Colunas
    col1, col2, col3 = st.columns(3)
    
    # Coluna 1: Empresas com Pendências
    delta_color_companies = "inverse" if companies_with_pendencies > 0 else "off"
    col1.metric(
        label="🚨 Empresas com Pendências",
        value=f"{companies_with_pendencies}",
        delta=f"de {total_companies} empresas",
        delta_color=delta_color_companies,
        help="Número de empresas com pelo menos um documento vencido."
    )
    
    # Coluna 2: Total de Pendências
    total_pendencies = metrics['total_pendencies']
    delta_color_pendencies = "inverse" if total_pendencies > 0 else "off"
    col2.metric(
        label="⚠️ Total de Documentos Vencidos",
        value=f"{total_pendencies}",
        delta="itens (ASOs + Treinamentos)",
        delta_color=delta_color_pendencies,
        help="Soma de todos os documentos vencidos em todas as empresas."
    )
    
    # Coluna 3: Empresa Mais Crítica (agora com mais detalhes)
    most_pendent_name, most_pendent_count = metrics['most_pendent_company']
    delta_color_critical = "off" if most_pendent_count == 0 else "inverse"
    col3.metric(
        label="🔥 Ponto de Atenção Principal",
        value=most_pendent_name,
        delta=f"{most_pendent_count} pendência(s)",
        delta_color=delta_color_critical,
        help="A empresa que atualmente concentra o maior número de pendências."
    )
    
    st.markdown("---")
