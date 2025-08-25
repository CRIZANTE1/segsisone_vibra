import streamlit as st
import pandas as pd
from datetime import datetime
from gdrive.matrix_manager import MatrixManager as GlobalMatrixManager
from operations.action_plan import ActionPlanManager
from operations.employee import EmployeeManager
from operations.company_docs import CompanyDocsManager
from auth.auth_utils import check_permission, is_user_logged_in, authenticate_user

# --- FUNÇÃO DE AGREGAÇÃO DE DADOS PARA A VISÃO GLOBAL ---
@st.cache_data(ttl=300)
def load_aggregated_action_plan_data():
    """
    Carrega e agrega dados do Plano de Ação de TODAS as unidades.
    """
    progress_bar = st.progress(0, text="Carregando Planos de Ação de todas as unidades...")
    
    matrix_manager_global = GlobalMatrixManager()
    all_units = matrix_manager_global.get_all_units()

    aggregated_actions = []
    company_id_to_name_map = {}

    total_units = len(all_units)
    for i, unit in enumerate(all_units):
        unit_name = unit.get('nome_unidade')
        spreadsheet_id = unit.get('spreadsheet_id')
        folder_id = unit.get('folder_id', '') # Folder ID pode não ser necessário
        
        progress_bar.progress((i + 1) / total_units, text=f"Lendo Plano de Ação da unidade: {unit_name}...")
        
        if not spreadsheet_id or not unit_name:
            continue

        try:
            temp_action_manager = ActionPlanManager(spreadsheet_id)
            temp_employee_manager = EmployeeManager(spreadsheet_id, folder_id)
            
            actions_df = temp_action_manager.action_plan_df
            if not actions_df.empty:
                actions_df['unidade'] = unit_name
                aggregated_actions.append(actions_df)
                
            if not temp_employee_manager.companies_df.empty:
                for _, row in temp_employee_manager.companies_df.iterrows():
                    company_id_to_name_map[row['id']] = row['nome']

        except Exception as e:
            st.warning(f"Não foi possível carregar o Plano de Ação da unidade '{unit_name}': {e}")

    progress_bar.empty()
    final_actions = pd.concat(aggregated_actions, ignore_index=True) if aggregated_actions else pd.DataFrame()
    
    return final_actions, company_id_to_name_map

# --- FUNÇÃO PRINCIPAL DA PÁGINA ---
def show_plano_acao_page():
    st.title("📋 Gestão de Não Conformidades e Auditorias")

    if not is_user_logged_in() or not authenticate_user():
        st.warning("Por favor, faça login para acessar esta página.")
        st.stop()
    if not check_permission(level='editor'):
        st.stop()

    is_global_view = st.session_state.get('unit_name') == 'Global'

    # --- VISÃO GLOBAL CONSOLIDADA ---
    if is_global_view:
        st.header("Visão Geral de Todas as Pendências (Todas as Unidades)")
        st.info("Selecione uma unidade na barra lateral para tratar itens e ver o histórico detalhado.")

        all_action_items, company_map = load_aggregated_action_plan_data()
        
        all_pending_items = pd.DataFrame()
        if not all_action_items.empty and 'status' in all_action_items.columns:
            all_pending_items = all_action_items[~all_action_items['status'].str.lower().isin(['concluído', 'cancelado'])]
            
        if all_pending_items.empty:
            st.success("🎉 Parabéns! Não há nenhuma não conformidade pendente em todas as unidades.")
        else:
            total_pending = len(all_pending_items)
            companies_with_pendencies = all_pending_items['id_empresa'].nunique()
            
            col1, col2 = st.columns(2)
            col1.metric("Total de Itens Pendentes", total_pending)
            col2.metric("Empresas com Pendências", f"{companies_with_pendencies}")
            
            st.markdown("#### Lista de Todas as Pendências Abertas:")
            
            display_df = all_pending_items.copy()
            display_df['nome_empresa'] = display_df['id_empresa'].apply(lambda id: company_map.get(id, f"ID: {id}"))
            
            st.dataframe(
                display_df[['unidade', 'nome_empresa', 'item_nao_conforme', 'status', 'prazo']],
                column_config={
                    "unidade": "Unidade", "nome_empresa": "Empresa",
                    "item_nao_conforme": "Não Conformidade", "status": "Status", "prazo": "Prazo"
                },
                use_container_width=True, hide_index=True
            )
        st.stop()

    # --- VISÃO DE UNIDADE ESPECÍFICA ---
    if not st.session_state.get('managers_initialized'):
        st.warning("Selecione uma unidade operacional para visualizar o Plano de Ação.")
        return

    action_plan_manager = st.session_state.action_plan_manager
    employee_manager = st.session_state.employee_manager
    docs_manager = st.session_state.docs_manager

    if not action_plan_manager.data_loaded_successfully:
        st.warning("Atenção: Não foi possível carregar os dados do Plano de Ação para esta unidade.")
        return

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
            if st.form_submit_button("Salvar Alterações"):
                updates = {
                    "plano_de_acao": plano_de_acao, "responsavel": responsavel,
                    "prazo": prazo, "status": status
                }
                if action_plan_manager.update_action_item(item_data['id'], updates):
                    st.success("Plano de ação atualizado!")
                    del st.session_state.current_item_to_treat
                    st.rerun()
                else:
                    st.error("Falha ao atualizar o plano de ação.")

    selected_company_id = st.selectbox(
        "Selecione uma empresa",
        employee_manager.companies_df['id'].tolist(),
        format_func=lambda x: employee_manager.get_company_name(x),
        index=None,
        placeholder="Escolha uma empresa..."
    )

    if 'current_item_to_treat' in st.session_state:
        treat_item_dialog(st.session_state.current_item_to_treat)
        
    st.markdown("---")

    if selected_company_id:
        company_name = employee_manager.get_company_name(selected_company_id)
        st.header(f"Itens Pendentes para: {company_name}")
        
        action_items_df = action_plan_manager.get_action_items_by_company(selected_company_id)
        asos_df = employee_manager.aso_df
        trainings_df = employee_manager.training_df
        company_docs_df = docs_manager.docs_df
        
        pending_items = pd.DataFrame()
        if not action_items_df.empty and 'status' in action_items_df.columns:
            pending_items = action_items_df[~action_items_df['status'].str.lower().isin(['concluído', 'cancelado'])]

        if pending_items.empty:
            st.success("🎉 Nenhuma não conformidade pendente para esta empresa!")
        else:
            for _, row in pending_items.iterrows():
                with st.container(border=True):
                    st.markdown(f"**Item:** {row['item_nao_conforme']}")
                    original_doc_id = row.get('id_documento_original')
                    employee_id = None
                    doc_type_context, pdf_url = "Documento da Empresa", ""
                    
                    aso_entry = asos_df[asos_df['id'] == original_doc_id]
                    if not aso_entry.empty:
                        entry = aso_entry.iloc[0]
                        employee_id, doc_type_context, pdf_url = entry.get('funcionario_id'), f"ASO ({entry.get('tipo_aso', '')})", entry.get('arquivo_id', '')
                    else:
                        training_entry = trainings_df[trainings_df['id'] == original_doc_id]
                        if not training_entry.empty:
                            entry = training_entry.iloc[0]
                            employee_id, doc_type_context, pdf_url = entry.get('funcionario_id'), f"Treinamento ({entry.get('norma', '')})", entry.get('anexo', '')
                        else:
                            company_doc_entry = company_docs_df[company_docs_df['id'] == original_doc_id]
                            if not company_doc_entry.empty:
                                entry = company_doc_entry.iloc[0]
                                doc_type_context, pdf_url = f"Doc. Empresa ({entry.get('tipo_documento', '')})", entry.get('arquivo_id', '')
                    
                    employee_info = f"🏢 **Empresa** | "
                    if employee_id and str(employee_id) != 'nan':
                        employee_name = employee_manager.get_employee_name(employee_id)
                        employee_info = f"👤 **Funcionário:** {employee_name or f'ID: {employee_id}'} | "
                    
                    pdf_link = f"[[PDF]({pdf_url})]" if pdf_url else ""
                    st.caption(f"{employee_info}**Tipo:** {doc_type_context} | **Doc ID:** {original_doc_id} {pdf_link} | **Referência:** {row.get('referencia_normativa', 'N/A')}")
                    
                    col1, col2 = st.columns([4, 1])
                    col1.info(f"**Status Atual:** {row['status']}")
                    if col2.button("Tratar Item", key=f"treat_{row['id']}", use_container_width=True):
                        st.session_state.current_item_to_treat = row.to_dict()
                        st.rerun()
                            
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

    else:
        st.header("Visão Geral de Todas as Pendências")
        st.info("Selecione uma empresa no menu acima para tratar os itens e ver o histórico detalhado.")

        all_action_items = action_plan_manager.action_plan_df
        
        all_pending_items = pd.DataFrame()
        if not all_action_items.empty and 'status' in all_action_items.columns:
            all_pending_items = all_action_items[all_action_items['status'].str.lower() != 'concluído']
            
        if all_pending_items.empty:
            st.success("🎉 Parabéns! Não há nenhuma não conformidade pendente em todas as empresas.")
        else:
            total_pending = len(all_pending_items)
            companies_with_pendencies = all_pending_items['id_empresa'].nunique()
            
            col1, col2 = st.columns(2)
            col1.metric("Total de Itens Pendentes", total_pending)
            col2.metric("Empresas com Pendências", f"{companies_with_pendencies}")
            
            st.markdown("#### Lista de Todas as Pendências Abertas:")
            
            display_df = all_pending_items.copy()
            display_df['nome_empresa'] = display_df['id_empresa'].apply(lambda id: employee_manager.get_company_name(id) or f"ID: {id}")
            
            def get_employee_context(row):
                emp_id = row.get('id_funcionario')
                if emp_id and str(emp_id).lower() != 'n/a':
                    return employee_manager.get_employee_name(emp_id) or f"ID: {emp_id}"
                return "Empresa"
            
            display_df['contexto'] = display_df.apply(get_employee_context, axis=1)

            st.dataframe(
                display_df[['nome_empresa', 'contexto', 'item_nao_conforme', 'status', 'prazo']],
                column_config={
                    "nome_empresa": "Empresa", "contexto": "Alvo",
                    "item_nao_conforme": "Não Conformidade", "status": "Status", "prazo": "Prazo"
                },
                use_container_width=True, hide_index=True
            )
