import streamlit as st
import pandas as pd
from datetime import datetime

from operations.action_plan import ActionPlanManager
from operations.employee import EmployeeManager
from operations.company_docs import CompanyDocsManager 
from auth.auth_utils import check_admin_permission

st.set_page_config(page_title="Plano de Ação", page_icon="📋", layout="wide")

st.title("📋 Plano de Ação de Não Conformidades")

if not check_admin_permission():
    st.stop()

# Instanciar os gerenciadores
@st.cache_resource
def get_managers():
    return ActionPlanManager(), EmployeeManager(), CompanyDocsManager()

action_plan_manager, employee_manager, docs_manager = get_managers()

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
                # --- CORREÇÃO E MELHORIA DE LAYOUT AQUI ---
                
                # 1. Busca o nome do funcionário, se aplicável.
                employee_id = row.get('id_funcionario')
                employee_info = "" # Inicializa como string vazia
                if employee_id and str(employee_id) != 'N/A':
                    employee_name = employee_manager.get_employee_name(employee_id)
                    if employee_name:
                        # Monta uma linha de informação completa sobre o funcionário
                        employee_info = f"👤 **Funcionário:** {employee_name} | "
                
                # 2. Exibe a descrição da não conformidade.
                st.markdown(f"**Item:** {row['item_nao_conforme']}")
                
                # 3. Monta e exibe as informações de contexto (funcionário, referência, etc.).
                context_caption = (
                    f"{employee_info}"
                    f"**Documento ID:** {row['id_documento_original']} | "
                    f"**Referência Normativa:** {row.get('referencia_normativa', 'N/A')}"
                )
                st.caption(context_caption)
    
                # 4. Exibe o status e o botão de ação em colunas.
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.info(f"**Status Atual:** {row['status']}")
                with col2:
                    if st.button("Tratar Item", key=f"treat_{row['id']}", use_container_width=True):
                        st.session_state.current_item_to_treat = row.to_dict()
                        
    st.markdown("---")
    with st.expander("📖 Ver Histórico Completo de Auditorias"):        
        with st.spinner("Carregando histórico de auditorias..."):
            audit_history = docs_manager.get_audits_by_company(selected_company_id)
            
        if audit_history.empty:
            st.info("Nenhum histórico de auditoria encontrado para esta empresa.")
        else:
            audit_history_display = audit_history.copy()
            audit_history_display['data_auditoria'] = pd.to_datetime(audit_history_display['data_auditoria'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
            audit_history_display.dropna(subset=['data_auditoria'], inplace=True)
            audit_history_display.sort_values(by='data_auditoria', ascending=False, inplace=True)
            
            for audit_id, group in audit_history_display.groupby('id_auditoria'):
                first_row = group.iloc[0]
                
                # Pega a linha de resumo da auditoria
                resumo_row = group[group['item_de_verificacao'].str.contains("Resumo", case=False, na=False)]
                if resumo_row.empty:
                    continue # Pula para a próxima auditoria se não houver um resumo
                
                resumo_row = resumo_row.iloc[0]
                status_auditoria = resumo_row['Status']
                
                status_badge = ""
                if 'não conforme' in str(status_auditoria).lower():
                    related_actions = action_items_df[action_items_df['audit_run_id'] == str(audit_id)]
                    if not related_actions.empty:
                        is_still_pending = any(s.lower() not in ['concluído', 'cancelado'] for s in related_actions['status'])
                        if is_still_pending:
                            status_badge = "🔴 **Pendente**"
                        else:
                            status_badge = "✅ **Tratado**"
                    else:
                        status_badge = "🔴 **Pendente**"
                else:
                    status_badge = "✅ **Conforme**"
                
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        target_name = ""
                        emp_id = first_row.get('id_funcionario')
                        if pd.notna(emp_id) and emp_id != 'N/A':
                            target_name = employee_manager.get_employee_name(emp_id) or f"Funcionário (ID: {emp_id})"
                        else:
                            target_name = company_name
                        
                        audit_title = f"**{first_row.get('tipo_documento')} ({first_row.get('norma_auditada')})** para **{target_name}**"
                        audit_date = first_row['data_auditoria'].strftime('%d/%m/%Y às %H:%M')
                        
                        st.markdown(audit_title)
                        st.caption(f"Realizada em: {audit_date}")
                    
                    with col2:
                        st.markdown(f"**Status:** {status_badge}")
                    
                    st.info(f"**Parecer da IA:** {resumo_row['observacao']}")
    
                    with st.expander("Ver detalhes da análise completa"):
                        details_df = group[['item_de_verificacao', 'Status', 'observacao']].rename(
                            columns={'item_de_verificacao': 'Item Verificado', 'observacao': 'Observação'}
                        )
                        st.dataframe(details_df, hide_index=True, use_container_width=True) 

    @st.dialog("Tratar Não Conformidade")
    def treat_item_dialog(item_data): 
        st.subheader(item_data['item_nao_conforme'])
        
        prazo_atual = None
        if item_data.get('prazo') and isinstance(item_data['prazo'], str) and item_data['prazo'].strip():
            try:
                prazo_atual = datetime.strptime(item_data['prazo'], "%d/%m/%Y").date()
            except (ValueError, TypeError):
                prazo_atual = None

        with st.form("action_plan_form"):
            plano_de_acao = st.text_area("Plano de Ação", value=item_data.get('plano_de_acao', ''))
            responsavel = st.text_input("Responsável", value=item_data.get('responsavel', ''))
            prazo = st.date_input("Prazo para Conclusão", value=prazo_atual)
            status_options = ["Aberto", "Em Andamento", "Concluído", "Cancelado"]
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
                    del st.session_state.current_item_to_treat
                    st.rerun()
                else:
                    st.error("Falha ao atualizar o plano de ação.")

    if 'current_item_to_treat' in st.session_state:
        treat_item_dialog(st.session_state.current_item_to_treat)
