import streamlit as st
import pandas as pd
from datetime import datetime, date
from operations.incident_manager import get_incident_manager
from gdrive.matrix_manager import get_matrix_manager

@st.cache_data(ttl=300)
def load_admin_dashboard_data():
    """
    Carrega e prepara todos os dados necessários para o dashboard do administrador.
    """
    incident_manager = get_incident_manager()
    matrix_manager = get_matrix_manager()

    all_actions_df = incident_manager.get_all_action_plans()
    all_incidents_df = incident_manager.get_all_incidents()
    all_units = matrix_manager.get_all_units()
    
    # Une as ações com as descrições para ter mais contexto
    blocking_actions_df = incident_manager.get_all_blocking_actions()
    if not all_actions_df.empty and not blocking_actions_df.empty:
        action_plan_with_desc = pd.merge(
            all_actions_df,
            blocking_actions_df[['id', 'descricao_acao']],
            left_on='id_acao_bloqueio',
            right_on='id',
            how='left'
        )
    else:
        action_plan_with_desc = all_actions_df
        if 'descricao_acao' not in action_plan_with_desc.columns:
            action_plan_with_desc['descricao_acao'] = "Descrição não disponível"
    
    action_plan_with_desc['descricao_acao'].fillna("Descrição não disponível", inplace=True)

    return action_plan_with_desc, all_incidents_df, all_units

def display_admin_summary_dashboard():
    """
    Calcula e exibe o dashboard de resumo executivo para o Administrador Global.
    """
    st.header("Dashboard de Resumo Executivo Global")

    action_plan_df, incidents_df, units_list = load_admin_dashboard_data()

    if not units_list:
        st.info("Nenhuma unidade operacional encontrada. Cadastre usuários e associe-os a unidades.")
        return

    # --- 1. Métricas Gerais ---
    total_units = len(units_list)
    total_incidents = len(incidents_df)
    total_actions = len(action_plan_df)

    col1, col2, col3 = st.columns(3)
    col1.metric("Unidades Operacionais", total_units)
    col2.metric("Total de Incidentes Globais", total_incidents)
    col3.metric("Total de Ações de Abrangência", total_actions)
    st.divider()

    # --- 2. Cálculo de Pendências (Ações com Prazo Vencido) ---
    if action_plan_df.empty:
        st.success("🎉 Nenhuma ação de abrangência registrada no sistema.")
        return

    # Filtra apenas as ações que ainda não foram concluídas ou canceladas
    pending_actions = action_plan_df[~action_plan_df['status'].str.lower().isin(['concluído', 'cancelado'])].copy()
    
    if pending_actions.empty:
        st.success("🎉 Parabéns! Todas as ações de abrangência foram concluídas.")
        return

    # Converte a coluna de prazo para datetime e encontra as vencidas
    pending_actions['prazo_dt'] = pd.to_datetime(pending_actions['prazo_inicial'], format="%d/%m/%Y", errors='coerce')
    overdue_actions = pending_actions.dropna(subset=['prazo_dt'])[pending_actions['prazo_dt'].dt.date < date.today()]

    total_pendencies = len(overdue_actions)
    if total_pendencies == 0:
        st.success("✅ Ótimo trabalho! Nenhuma ação de abrangência com prazo vencido.")
        return
        
    st.error(f"Atenção! Existem {total_pendencies} ações de abrangência com o prazo vencido no sistema.", icon="⚠️")
    st.divider()

    # --- 3. Gráfico de Barras de Pendências por Unidade ---
    st.subheader("Gráfico de Ações Vencidas por Unidade Operacional")
    
    overdue_counts_by_unit = overdue_actions.groupby('unidade_operacional').size()
    
    if overdue_counts_by_unit.empty:
        st.info("Nenhuma pendência encontrada para gerar o gráfico.")
        return

    st.bar_chart(overdue_counts_by_unit)
    
    with st.expander("Ver tabela de dados de pendências"):
        st.dataframe(overdue_counts_by_unit.reset_index(name='Ações Vencidas'), width='stretch', hide_index=True)

    # --- 4. Detalhamento da Unidade Mais Crítica ---
    most_critical_unit = overdue_counts_by_unit.idxmax()
    st.subheader(f"🔍 Detalhes da Unidade Mais Crítica: {most_critical_unit}")

    critical_unit_details = overdue_actions[overdue_actions['unidade_operacional'] == most_critical_unit]

    if critical_unit_details.empty:
        st.info(f"Não foi possível carregar detalhes para a unidade '{most_critical_unit}'.")
    else:
        st.write(f"Abaixo estão as {len(critical_unit_details)} ações com prazo vencido para esta unidade:")
        
        display_df = critical_unit_details[['descricao_acao', 'responsavel_email', 'prazo_inicial', 'status']].copy()
        
        st.dataframe(
            display_df.rename(columns={
                'descricao_acao': 'Descrição da Ação',
                'responsavel_email': 'Responsável',
                'prazo_inicial': 'Prazo Vencido',
                'status': 'Status Atual'
            }),
            width='stretch',
            hide_index=True
        )
