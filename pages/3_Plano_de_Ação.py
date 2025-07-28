import streamlit as st
import pandas as pd
from datetime import datetime

from operations.action_plan import ActionPlanManager
from operations.employee import EmployeeManager
from auth.auth_utils import check_admin_permission

st.set_page_config(page_title="Plano de Ação", page_icon="📋", layout="wide")

st.title("📋 Plano de Ação de Não Conformidades")

if not check_admin_permission():
    st.stop()

# Instanciar os gerenciadores
@st.cache_resource
def get_managers():
    return ActionPlanManager(), EmployeeManager()

action_plan_manager, employee_manager = get_managers()

# Selecionar a empresa
selected_company_id = st.selectbox(
    "Selecione uma empresa para visualizar o plano de ação",
    employee_manager.companies_df['id'].tolist(),
    format_func=lambda x: employee_manager.get_company_name(x),
    index=None,
    placeholder="Escolha uma empresa..."
)

if selected_company_id:
    st.header(f"Itens Pendentes para: {employee_manager.get_company_name(selected_company_id)}")

    action_items_df = action_plan_manager.get_action_items_by_company(selected_company_id)
    
    # Filtra por itens que não estão concluídos
    pending_items = action_items_df[action_items_df['status'].str.lower() != 'concluído']

    if pending_items.empty:
        st.success("🎉 Nenhuma não conformidade pendente para esta empresa!")
    else:
        for index, row in pending_items.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.markdown(f"**Item:** {row['item_nao_conforme']}")
                    st.caption(f"Referência: {row['referencia_normativa']} | Documento ID: {row['id_documento_original']}")
                with col2:
                    st.info(f"**Status:** {row['status']}")
                with col3:
                    # O botão "Tratar" abre o diálogo
                    if st.button("Tratar Item", key=f"treat_{row['id']}"):
                        st.session_state.current_item_to_treat = row.to_dict()

# --- LÓGICA DO DIÁLOGO DE TRATAMENTO ---
if 'current_item_to_treat' in st.session_state:
    item_data = st.session_state.current_item_to_treat

    @st.dialog("Tratar Não Conformidade")
    def treat_item_dialog():
        st.subheader(item_data['item_nao_conforme'])
        
        # Converte a string de data para objeto date, se existir
        prazo_atual = None
        if item_data.get('prazo'):
            try:
                prazo_atual = datetime.strptime(item_data['prazo'], "%d/%m/%Y").date()
            except (ValueError, TypeError):
                prazo_atual = None

        with st.form("action_plan_form"):
            plano_de_acao = st.text_area("Plano de Ação", value=item_data.get('plano_de_acao', ''))
            responsavel = st.text_input("Responsável", value=item_data.get('responsavel', ''))
            prazo = st.date_input("Prazo para Conclusão", value=prazo_atual)
            status_options = ["Aberto", "Em Andamento", "Concluído", "Cancelado"]
            # Encontra o índice do status atual para definir como padrão
            try:
                current_status_index = status_options.index(item_data.get('status', 'Aberto'))
            except ValueError:
                current_status_index = 0
            status = st.selectbox("Status", status_options, index=current_status_index)

            submitted = st.form_submit_button("Salvar Alterações")

            if submitted:
                updates = {
                    "plano_de_acao": plano_de_acao,
                    "responsavel": responsavel,
                    "prazo": prazo,
                    "status": status
                }
                if action_plan_manager.update_action_item(item_data['id'], updates):
                    st.success("Plano de ação atualizado com sucesso!")
                    del st.session_state.current_item_to_treat # Fecha o diálogo
                    st.rerun()
                else:
                    st.error("Falha ao atualizar o plano de ação.")

    treat_item_dialog()
