import streamlit as st
import pandas as pd
from datetime import date
from auth.auth_utils import is_user_logged_in, authenticate_user

def format_company_display(cid, companies_df):
    if cid is None:
        return "Selecione uma empresa..."
    if companies_df.empty:
        return f"ID: {cid}"
    
    company_name = companies_df[companies_df['id'] == cid]['nome'].iloc[0]
    return company_name

def show_plano_acao_page():
    st.title("📋 Plano de Ação")
    
    # Verifica autenticação
    if not is_user_logged_in():
        st.warning("Faça login para acessar esta página.")
        return
    
    if not authenticate_user():
        return
    
    # Verifica se está em modo global ou unidade
    is_global_view = st.session_state.get('unit_name') == 'Global'
    
    if is_global_view:
        st.info("📊 Visão Global do Plano de Ação")
        # Implementar agregação de todas as unidades
        # (similar ao código em front/administracao.py)
    else:
        # Visão por unidade
        if not st.session_state.get('managers_initialized'):
            st.warning("Aguardando inicialização dos dados da unidade...")
            return
        
        action_plan_manager = st.session_state.action_plan_manager
        employee_manager = st.session_state.employee_manager
        docs_manager = st.session_state.docs_manager
        
        # Seletor de empresa
        company_options = [None] + employee_manager.companies_df['id'].tolist()
        selected_company_id = st.selectbox(
            "Selecione uma empresa:",
            options=company_options,
            format_func=lambda cid: format_company_display(cid, employee_manager.companies_df),
            key="company_selector_plano"
        )
        
        if selected_company_id:
            company_name = employee_manager.get_company_name(selected_company_id)
            st.header(f"Itens Pendentes para: {company_name}")
            
            action_items_df = action_plan_manager.get_action_items_by_company(selected_company_id)
            
            pending_items = pd.DataFrame()
            if not action_items_df.empty and 'status' in action_items_df.columns:
                pending_items = action_items_df[
                    ~action_items_df['status'].str.lower().isin(['concluído', 'cancelado'])
                ]
            
            if pending_items.empty:
                st.success("🎉 Nenhuma não conformidade pendente para esta empresa!")
            else:
                for _, row in pending_items.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**Item:** {row['item_nao_conforme']}")
                        
                        # Informações do funcionário (se houver)
                        employee_id = row.get('id_funcionario')
                        if employee_id and str(employee_id).strip():
                            employee_name = employee_manager.get_employee_name(employee_id)
                            st.caption(f"👤 Funcionário: {employee_name}")
                        
                        # Referência normativa
                        st.caption(f"**Referência:** {row.get('referencia_normativa', 'N/A')}")
                        
                        col1, col2 = st.columns([4, 1])
                        col1.info(f"**Status Atual:** {row['status']}")
                        
                        if col2.button("Tratar Item", key=f"treat_{row['id']}", use_container_width=True):
                            st.session_state.current_item_to_treat = row.to_dict()
                            st.rerun()
        
        # Diálogo de tratamento de item
        if 'current_item_to_treat' in st.session_state:
            show_treatment_dialog(action_plan_manager)

def show_treatment_dialog(action_plan_manager):
    """Diálogo para tratar um item do plano de ação."""
    @st.dialog("Tratar Item de Não Conformidade")
    def treatment_form():
        item = st.session_state.current_item_to_treat
        
        st.markdown(f"**Item:** {item['item_nao_conforme']}")
        
        with st.form("treatment_form"):
            plano_acao = st.text_area("Plano de Ação", value=item.get('plano_de_acao', ''))
            responsavel = st.text_input("Responsável", value=item.get('responsavel', ''))
            prazo = st.date_input("Prazo")
            novo_status = st.selectbox("Status", ["Aberto", "Em Tratamento", "Concluído", "Cancelado"])
            
            if st.form_submit_button("Salvar Tratamento", type="primary"):
                updates = {
                    'plano_de_acao': plano_acao,
                    'responsavel': responsavel,
                    'prazo': prazo.strftime("%d/%m/%Y"),
                    'status': novo_status
                }
                
                if novo_status == "Concluído":
                    updates['data_conclusao'] = date.today().strftime("%d/%m/%Y")
                
                if action_plan_manager.update_action_item(item['id'], updates):
                    st.success("Item atualizado com sucesso!")
                    del st.session_state.current_item_to_treat
                    st.rerun()
    
    treatment_form()