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
    # ... código existente ...
    
    if selected_company_id:
        company_name = employee_manager.get_company_name(selected_company_id)
        st.header(f"Itens Pendentes para: {company_name}")
        
        action_items_df = action_plan_manager.get_action_items_by_company(selected_company_id)
        
        pending_items = pd.DataFrame()
        if not action_items_df.empty and 'status' in action_items_df.columns:
            pending_items = action_items_df[~action_items_df['status'].str.lower().isin(['concluído', 'cancelado'])]

        if pending_items.empty:
            st.success("🎉 Nenhuma não conformidade pendente para esta empresa!")
        else:
            for _, row in pending_items.iterrows():
                with st.container(border=True):
                    st.markdown(f"**Item:** {row['item_nao_conforme']}")
                    
                    # ✅ MELHORADO: Usa id_funcionario diretamente da planilha
                    employee_id = row.get('id_funcionario')
                    
                    # Informações do contexto
                    original_doc_id = row.get('id_documento_original')
                    doc_type_context = "Documento da Empresa"
                    pdf_url = ""
                    
                    # Se tem employee_id, mostra o nome do funcionário
                    if employee_id and str(employee_id) != 'nan' and str(employee_id).strip():
                        employee_name = employee_manager.get_employee_name(employee_id)
                        employee_info = f"👤 **Funcionário:** {employee_name or f'ID: {employee_id}'} | "
                        
                        # Tenta identificar o tipo de documento
                        asos_df = employee_manager.aso_df
                        trainings_df = employee_manager.training_df
                        
                        aso_entry = asos_df[asos_df['id'] == original_doc_id]
                        if not aso_entry.empty:
                            entry = aso_entry.iloc[0]
                            doc_type_context = f"ASO ({entry.get('tipo_aso', '')})"
                            pdf_url = entry.get('arquivo_id', '')
                        else:
                            training_entry = trainings_df[trainings_df['id'] == original_doc_id]
                            if not training_entry.empty:
                                entry = training_entry.iloc[0]
                                doc_type_context = f"Treinamento ({entry.get('norma', '')})"
                                pdf_url = entry.get('anexo', '')
                    else:
                        employee_info = "🏢 **Empresa** | "
                        
                        # Busca em documentos da empresa
                        company_docs_df = docs_manager.docs_df
                        company_doc_entry = company_docs_df[company_docs_df['id'] == original_doc_id]
                        if not company_doc_entry.empty:
                            entry = company_doc_entry.iloc[0]
                            doc_type_context = f"Doc. Empresa ({entry.get('tipo_documento', '')})"
                            pdf_url = entry.get('arquivo_id', '')
                    
                    pdf_link = f"[[PDF]({pdf_url})]" if pdf_url else ""
                    st.caption(f"{employee_info}**Tipo:** {doc_type_context} | **Doc ID:** {original_doc_id} {pdf_link} | **Referência:** {row.get('referencia_normativa', 'N/A')}")
                    
                    col1, col2 = st.columns([4, 1])
                    col1.info(f"**Status Atual:** {row['status']}")
                    if col2.button("Tratar Item", key=f"treat_{row['id']}", use_container_width=True):
                        st.session_state.current_item_to_treat = row.to_dict()
                        st.rerun()
