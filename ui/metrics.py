import streamlit as st
import pandas as pd
from datetime import date
from operations.employee import EmployeeManager

def calculate_overall_metrics(employee_manager: EmployeeManager) -> dict:
    """
    Calcula as métricas de pendências para TODAS as empresas.
    
    Args:
        employee_manager: Uma instância da classe EmployeeManager que já contém
                          os DataFrames carregados (aso_df, training_df).

    Returns:
        Um dicionário com as métricas calculadas.
    """
    today = date.today()
    metrics = {
        'total_companies': 0,
        'companies_with_pendencies': 0,
        'total_pendencies': 0,
        'most_pendent_company': ('Nenhuma', 0) # (Nome da empresa, contagem)
    }

    companies_df = employee_manager.companies_df
    if companies_df.empty:
        return metrics

    metrics['total_companies'] = len(companies_df)
    
    pendencies_by_company = {}

    # Processar ASOs Vencidos
    if not employee_manager.aso_df.empty:
        asos = employee_manager.aso_df.copy()
        asos['vencimento_dt'] = pd.to_datetime(asos['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        asos.dropna(subset=['vencimento_dt'], inplace=True)
        
        # Pega o ASO mais recente de cada funcionário (que não seja demissional)
        latest_asos = asos[~asos['tipo_aso'].str.lower().isin(['demissional'])]
        latest_asos = latest_asos.sort_values('data_aso', ascending=False).groupby('funcionario_id').head(1)
        
        expired_asos = latest_asos[latest_asos['vencimento_dt'] < today]
        
        if not expired_asos.empty:
            # Mapeia funcionário -> empresa
            employee_to_company = employee_manager.employees_df.set_index('id')['empresa_id']
            expired_asos['empresa_id'] = expired_asos['funcionario_id'].map(employee_to_company)
            
            aso_pendencies = expired_asos.groupby('empresa_id').size()
            for company_id, count in aso_pendencies.items():
                pendencies_by_company[company_id] = pendencies_by_company.get(company_id, 0) + count

    # Processar Treinamentos Vencidos
    if not employee_manager.training_df.empty:
        trainings = employee_manager.training_df.copy()
        trainings['vencimento_dt'] = pd.to_datetime(trainings['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
        trainings.dropna(subset=['vencimento_dt'], inplace=True)
        
        # Pega o treinamento mais recente de cada tipo (por norma)
        latest_trainings = trainings.sort_values('data', ascending=False).groupby(['funcionario_id', 'norma']).head(1)
        
        expired_trainings = latest_trainings[latest_trainings['vencimento_dt'] < today]
        
        if not expired_trainings.empty:
            expired_trainings.loc[:, 'empresa_id'] = expired_trainings['funcionario_id'].map(employee_to_company)
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
    Calcula e exibe as métricas de pendências em um formato minimalista.
    """
    metrics = calculate_overall_metrics(employee_manager)
    
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    col1.metric(
        label="Empresas com Pendências",
        value=f"{metrics['companies_with_pendencies']} de {metrics['total_companies']}",
        help="Número de empresas que possuem pelo menos um documento vencido (ASO ou Treinamento)."
    )
    
    col2.metric(
        label="Total de Pendências",
        value=metrics['total_pendencies'],
        help="Soma de todos os ASOs e Treinamentos vencidos em todas as empresas."
    )
    
    col3.metric(
        label="Empresa Mais Crítica",
        value=metrics['most_pendent_company'][0],
        help=f"A empresa com o maior número de pendências ({metrics['most_pendent_company'][1]} itens)."
    )
    st.markdown("---")
