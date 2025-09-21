# front/admin_dashboard.py

import streamlit as st
import pandas as pd
from datetime import datetime, date
from operations.incident_manager import get_incident_manager
from gdrive.matrix_manager import get_matrix_manager

@st.cache_data(ttl=300)
def load_aggregated_data():
    """
    Carrega e prepara todos os dados necessários para o dashboard do administrador.
    No nosso sistema, isso significa carregar todas as ações, incidentes e usuários/unidades.
    """
    incident_manager = get_incident_manager()
    matrix_manager = get_matrix_manager()

    # Carrega os DataFrames principais
    action_plan_df = incident_manager.get_all_action_plans()
    incidents_df = incident_manager.get_all_incidents()
    users_df = matrix_manager.get_all_users_df()
    
    # Une as ações com suas descrições para ter mais contexto no detalhamento
    blocking_actions_df = incident_manager.get_all_blocking_actions()
    if not action_plan_df.empty and not blocking_actions_df.empty:
        action_plan_with_desc = pd.merge(
            action_plan_df,
            blocking_actions_df[['id', 'descricao_acao']],
            left_on='id_acao_bloqueio',
            right_on='id',
            how='left'
        )
    else:
        action_plan_with_desc = action_plan_df
        if 'descricao_acao' not in action_plan_with_desc.columns:
            action_plan_with_desc['descricao_acao'] = "Descrição não disponível"
    
    # Garante que a coluna de descrição nunca seja nula
    action_plan_with_desc['descricao_acao'] = action_plan_with_desc['descricao_acao'].fillna("Descrição não disponível")

    return action_plan_with_desc, incidents_df, users_df

def display_admin_summary_dashboard():
    """
    Calcula e exibe o dashboard de resumo executivo adaptado para o sistema SSBA_VIBRA.
    """
    st.header("Dashboard de Resumo Executivo Global")

    action_plan_df, incidents_df, users_df = load_aggregated_data()

    if users_df.empty:
        st.info("Nenhum usuário (e, portanto, nenhuma unidade) cadastrado. Não há dados para exibir.")
        return

    # --- 1. Métricas Gerais ---
    # Filtra para obter apenas unidades operacionais únicas (exclui admin global '*')
    operational_units = users_df[users_df['unidade_associada'] != '*']['unidade_associada'].nunique()
    total_incidents = len(incidents_df)
    total_actions = len(action_plan_df)

    col1, col2, col3 = st.columns(3)
    col1.metric("Unidades Operacionais", operational_units)
    col2.metric("Total de Incidentes Globais", total_incidents)
    col3.metric("Total de Ações de Abrangência", total_actions)
    st.divider()

    # --- 2. Cálculo de Pendências (Ações com Prazo Vencido) ---
    if action_plan_df.empty:
        st.success("🎉 Nenhuma ação de abrangência registrada no sistema.")
        return
        
    pending_actions = action_plan_df[~action_plan_df['status'].str.lower().isin(['concluído', 'cancelado'])].copy()
    
    if pending_actions.empty:
        st.success("🎉 Parabéns! Todas as ações de abrangência foram concluídas.")
        return

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
        st.info("Nenhuma pendência vencida encontrada para gerar o gráfico.")
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
