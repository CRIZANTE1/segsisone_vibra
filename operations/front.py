import streamlit as st
from datetime import datetime, date
from operations.employee import EmployeeManager
from operations.company_docs import CompanyDocsManager
from gdrive.gdrive_upload import GoogleDriveUploader
import pandas as pd
from auth.auth_utils import check_admin_permission

def mostrar_info_normas():
    with st.expander("Informações sobre Normas Regulamentadoras"):
        st.markdown("""
        ### Cargas Horárias e Periodicidade dos Treinamentos
        
        #### NR-20
        | Módulo | Formação Inicial | Reciclagem (Periodicidade) | Reciclagem (C.H. Mínima) |
        |--------|------------------|----------------------------|--------------------------|
        | Básico | 8 horas          | 3 anos                     | 4 horas                  |
        | Intermediário | 16 horas         | 2 anos                     | 4 horas                  |
        | Avançado I | 20 horas         | 2 anos                     | 4 horas                  |
        | Avançado II | 32 horas         | 1 ano                      | 4 horas                  |
        
        ---

        #### Outras NRs Comuns
        | Norma | Formação Inicial (C.H.) | Reciclagem (C.H.) | Periodicidade Reciclagem |
        |-------|---------------------------|-----------------------|--------------------------|
        | NR-35 | 8 horas                   | 8 horas               | 2 anos                   |
        | NR-10 | 40 horas                  | 40 horas              | 2 anos                   |
        | NR-18 | 8 horas                   | 8 horas               | 1 ano                    |
        | NR-34 | 8 horas                   | 8 horas               | 1 ano                    |
        | NR-12 | 8 horas                   | 8 horas               | 2 anos                   |
        | NR-06 | 3 horas                   | 3 horas               | 3 anos                   |
        """)

def highlight_expired(row):
    today = datetime.now().date()
    vencimento_val = row.get('vencimento')
    if pd.notna(vencimento_val) and isinstance(vencimento_val, date):
        if vencimento_val < today:
            return ['background-color: #FFCDD2'] * len(row)
    return [''] * len(row)

def style_audit_table(row):
    """Aplica cor à linha inteira se o status for 'Não Conforme'."""
    status_val = str(row.get('Status', '')).lower()
    if 'Não Conforme' in status_val:
        return ['background-color: #FFCDD2'] * len(row)
    return [''] * len(row)

def process_aso_pdf():
    if st.session_state.get('aso_uploader_tab'):
        employee_manager = st.session_state.employee_manager
        with st.spinner("Analisando PDF do ASO..."):
            st.session_state.aso_anexo_para_salvar = st.session_state.aso_uploader_tab
            st.session_state.aso_funcionario_para_salvar = st.session_state.aso_employee_add
            st.session_state.aso_info_para_salvar = employee_manager.analyze_aso_pdf(st.session_state.aso_uploader_tab)

def process_training_pdf():
    if st.session_state.get('training_uploader_tab'):
        employee_manager = st.session_state.employee_manager
        with st.spinner("Analisando PDF do Treinamento..."):
            st.session_state.training_anexo_para_salvar = st.session_state.training_uploader_tab
            st.session_state.training_funcionario_para_salvar = st.session_state.training_employee_add
            st.session_state.training_info_para_salvar = employee_manager.analyze_training_pdf(st.session_state.training_uploader_tab)

def process_company_doc_pdf():
    if st.session_state.get('doc_uploader_tab'):
        docs_manager = st.session_state.docs_manager
        with st.spinner("Analisando PDF do documento..."):
            st.session_state.doc_anexo_para_salvar = st.session_state.doc_uploader_tab
            st.session_state.doc_info_para_salvar = docs_manager.analyze_company_doc_pdf(st.session_state.doc_uploader_tab)

def front_page():
    if 'employee_manager' not in st.session_state:
        st.session_state.employee_manager = EmployeeManager()
    if 'docs_manager' not in st.session_state:
        st.session_state.docs_manager = CompanyDocsManager()
    
    employee_manager = st.session_state.employee_manager
    docs_manager = st.session_state.docs_manager
    
    employee_manager.load_data()
    docs_manager.load_company_data()
    
    gdrive_uploader = GoogleDriveUploader()
    
    st.title("Gestão de Documentação Inteligente")
    
    selected_company = None
    if not employee_manager.companies_df.empty:
        df = employee_manager.companies_df.astype({'id': 'str'})
        selected_company = st.selectbox(
            "Selecione uma empresa",
            df['id'].tolist(),
            format_func=lambda x: f"{df[df['id'] == x]['nome'].iloc[0]} - {df[df['id'] == x]['cnpj'].iloc[0]}",
            key="company_select"
        )
    
    tab_situacao, tab_add_doc_empresa, tab_add_aso, tab_add_treinamento = st.tabs([
        "**Situação Geral**", "**Adicionar Documento da Empresa**", "Adicionar ASO", "Adicionar Treinamento"
    ])

    with tab_situacao:
        if selected_company:
            st.subheader("Documentos da Empresa")
            company_docs = docs_manager.get_docs_by_company(selected_company).copy()
            
            if not company_docs.empty:
                # Cabeçalho da nossa tabela customizada
                header_cols = st.columns([3, 2, 2, 1, 1, 1])
                headers = ["Tipo do Documento", "Emissão", "Vencimento", "Anexo", "Arquivar", "Excluir"]
                for col, header in zip(header_cols, headers):
                    col.markdown(f"**{header}**")
                
                st.divider()
            
                # Loop para criar uma linha para cada documento
                for index, row in company_docs.iterrows():
                    # Converte as datas para exibição, tratando possíveis erros
                    try:
                        emissao_str = pd.to_datetime(row['data_emissao']).strftime('%d/%m/%Y')
                    except (ValueError, TypeError):
                        emissao_str = row['data_emissao']
                        
                    try:
                        vencimento_str = pd.to_datetime(row['vencimento']).strftime('%d/%m/%Y')
                    except (ValueError, TypeError):
                        vencimento_str = row['vencimento']
            
                    # Define a cor do texto se estiver arquivado
                    doc_info_html = f"<span style='color: #888;'>{row['tipo_documento']}</span>" if row.get('status') == 'Arquivado' else row['tipo_documento']
            
                    # Usa colunas para alinhar os dados e botões
                    doc_cols = st.columns([3, 2, 2, 1, 1, 1])
                    
                    doc_cols[0].markdown(doc_info_html, unsafe_allow_html=True)
                    doc_cols[1].write(emissao_str)
                    doc_cols[2].write(vencimento_str)
                    
                    # Link para o anexo
                    with doc_cols[3]:
                        if pd.notna(row['arquivo_id']):
                            st.link_button("🔗", row['arquivo_id'], help="Abrir anexo")
            
                    # Botão de Arquivar/Desarquivar
                    with doc_cols[4]:
                        is_archived = row.get('status') == 'Arquivado'
                        archive_text = "↩️" if is_archived else "🗄️"
                        archive_help = "Desarquivar documento" if is_archived else "Arquivar documento"
                        if st.button(archive_text, key=f"archive_doc_{row['id']}", help=archive_help):
                            if docs_manager.archive_company_doc(row['id'], archive=not is_archived):
                                st.success(f"Documento '{row['tipo_documento']}' atualizado!")
                                st.rerun()
                            else:
                                st.error("Falha ao arquivar o documento.")
                    
                    # Botão de Excluir com confirmação
                    with doc_cols[5]:
                        if st.button("🗑️", key=f"delete_doc_{row['id']}", help="Excluir documento permanentemente"):
                            st.session_state[f"confirm_delete_doc_{row['id']}"] = True
                            st.rerun()
            
                    # Lógica de confirmação da exclusão
                    if st.session_state.get(f"confirm_delete_doc_{row['id']}", False):
                        st.warning(f"**Tem certeza que deseja excluir permanentemente o documento '{row['tipo_documento']}'?** Esta ação não pode ser desfeita.")
                        
                        confirm_cols = st.columns([2, 1, 1, 8]) # Alinha os botões
                        if confirm_cols[0].button("Sim, excluir agora", key=f"confirm_del_doc_btn_{row['id']}", type="primary"):
                            with st.spinner("Excluindo documento e arquivo..."):
                                if docs_manager.delete_company_doc(row['id'], row['arquivo_id']):
                                    st.success("Documento excluído com sucesso.")
                                    del st.session_state[f"confirm_delete_doc_{row['id']}"]
                                    st.rerun()
                                else:
                                    st.error("Falha ao excluir o documento.")
                        if confirm_cols[1].button("Cancelar", key=f"cancel_del_doc_btn_{row['id']}"):
                            del st.session_state[f"confirm_delete_doc_{row['id']}"]
                            st.rerun()
                    
            else:
                st.info("Nenhum documento (ex: PGR, PCMSO) cadastrado para esta empresa.")
            
            st.markdown("---")
            st.subheader("Funcionários")
            employees = employee_manager.get_employees_by_company(selected_company)
            if not employees.empty:
                for index, employee in employees.iterrows():
                    employee_id = employee['id']; employee_name = employee['nome']; employee_role = employee['cargo']
                    today = datetime.now().date(); aso_status = 'Não encontrado'; aso_vencimento = None; trainings_total = 0; trainings_expired_count = 0
                    
                    latest_aso = employee_manager.get_latest_aso_by_employee(employee_id).copy()
                    if not latest_aso.empty:
                        vencimento_aso_obj = latest_aso['vencimento'].iloc[0]
                        if isinstance(vencimento_aso_obj, date):
                             aso_vencimento = vencimento_aso_obj
                             aso_status = 'Válido' if aso_vencimento >= today else 'Vencido'
                    all_trainings = employee_manager.get_all_trainings_by_employee(employee_id).copy()
                    if not all_trainings.empty:
                        trainings_total = len(all_trainings)
                        expired_mask = pd.to_datetime(all_trainings['vencimento'], errors='coerce').dt.date < today
                        trainings_expired_count = expired_mask.sum()
                    overall_status = 'Em Dia' if aso_status == 'Válido' and trainings_expired_count == 0 else 'Pendente'
                    status_icon = "✅" if overall_status == 'Em Dia' else "⚠️"
                    expander_title = f"{status_icon} **{employee_name}** - *{employee_role}*"

                    with st.expander(expander_title):
                        st.markdown("##### Resumo de Status")
                        col1, col2, col3 = st.columns(3); num_pendencias = trainings_expired_count + (1 if aso_status == 'Vencido' else 0)
                        col1.metric("Status Geral", overall_status, f"{num_pendencias} pendência(s)" if num_pendencias > 0 else "Nenhuma pendência", delta_color="inverse" if overall_status != 'Em Dia' else "off")
                        col2.metric("Status do ASO", aso_status, help=f"Vencimento: {aso_vencimento.strftime('%d/%m/%Y') if aso_vencimento else 'N/A'}")
                        col3.metric("Treinamentos Vencidos", f"{trainings_expired_count} de {trainings_total}")
                        st.markdown("---")
                        st.markdown("##### ASO Mais Recente")
                        if not latest_aso.empty:
                            # Cabeçalho da nossa tabela customizada
                            header_cols = st.columns([2, 2, 2, 3, 1, 1])
                            headers = ["Tipo", "Data", "Vencimento", "Riscos", "Anexo", "Ação"]
                            for col, header in zip(header_cols, headers):
                                col.markdown(f"**{header}**")
                        
                            # Loop para criar uma linha para cada ASO
                            for index, row in latest_aso.iterrows():
                                # Usa colunas para alinhar os dados e os botões
                                row_cols = st.columns([2, 2, 2, 3, 1, 1])
                                
                                # Exibe as informações do ASO
                                row_cols[0].write(row.get('tipo_aso', 'N/A'))
                                row_cols[1].write(row['data_aso'].strftime('%d/%m/%Y') if isinstance(row['data_aso'], date) else 'N/A')
                                row_cols[2].write(row['vencimento'].strftime('%d/%m/%Y') if isinstance(row['vencimento'], date) else 'N/A')
                                row_cols[3].write(row.get('riscos', 'N/A'))
                        
                                # Link para o arquivo
                                if pd.notna(row['arquivo_id']):
                                    row_cols[4].link_button("🔗", row['arquivo_id'], help="Abrir anexo")
                                else:
                                    row_cols[4].write("---")
                        
                                # Botão de Excluir com confirmação
                                with row_cols[5]:
                                    # Verificando se todos os parênteses estão fechados aqui
                                    if st.button("🗑️", key=f"delete_aso_{row['id']}", help="Excluir ASO permanentemente", type="secondary"):
                                        st.session_state[f"confirm_delete_aso_{row['id']}"] = True
                                        st.rerun()
                        
                                # Lógica de confirmação que aparece abaixo da linha
                                if st.session_state.get(f"confirm_delete_aso_{row['id']}", False):
                                    st.warning(f"**Tem certeza que deseja excluir permanentemente o ASO de '{row.get('tipo_aso', 'N/A')}'?** Esta ação não pode ser desfeita.")
                                    
                                    # Colunas para os botões de Sim/Não
                                    confirm_cols = st.columns([1, 1, 4]) 
                                    with confirm_cols[0]:
                                        # Verificando se todos os parênteses estão fechados aqui
                                        if st.button("Sim, excluir", key=f"confirm_del_aso_btn_{row['id']}", type="primary"):
                                            with st.spinner("Excluindo ASO e arquivo..."):
                                                if employee_manager.delete_aso(row['id'], row['arquivo_id']):
                                                    st.success("ASO excluído com sucesso.")
                                                    del st.session_state[f"confirm_delete_aso_{row['id']}"]
                                                    st.rerun()
                                                else:
                                                    st.error("Falha ao excluir o ASO.")
                                    
                                    with confirm_cols[1]:
                                        # Verificando se todos os parênteses estão fechados aqui
                                        if st.button("Cancelar", key=f"cancel_del_aso_btn_{row['id']}"):
                                            del st.session_state[f"confirm_delete_aso_{row['id']}"]
                                            st.rerun()
                                
                                st.divider()
                        
                        else:
                            st.info("Nenhum ASO encontrado.")
                            
                        st.markdown("##### Todos os Treinamentos")
                        if not all_trainings.empty:
                            training_display_cols = ["norma", "data", "vencimento", "tipo_treinamento", "carga_horaria", "arquivo_id"]
                            
                            for index, row in all_trainings.iterrows():
                                # Usa colunas para alinhar os botões
                                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                                
                                doc_info = f"**{row['norma']}** ({row['modulo']}) - Vence em: {row['vencimento'].strftime('%d/%m/%Y')}"
                                col1.markdown(doc_info)
                                
                                # Link para o arquivo
                                col2.link_button("Abrir Anexo", row['arquivo_id'])
                        
                                # Botão de Arquivar
                                is_archived = row.get('status') == 'Arquivado'
                                archive_text = "Desarquivar" if is_archived else "Arquivar"
                                if col3.button(archive_text, key=f"archive_train_{row['id']}"):
                                    if employee_manager.archive_training(row['id'], archive=not is_archived):
                                        st.success(f"Treinamento '{row['norma']}' atualizado!")
                                        st.rerun()
                                    else:
                                        st.error("Falha ao arquivar.")
                        
                                # Botão de Excluir com confirmação
                                if col4.button("🗑️ Excluir", key=f"delete_train_{row['id']}", type="primary"):
                                    # Lógica de confirmação
                                    if f"confirm_delete_{row['id']}" not in st.session_state:
                                        st.session_state[f"confirm_delete_{row['id']}"] = True
                                        st.rerun()
                        
                                if st.session_state.get(f"confirm_delete_{row['id']}", False):
                                    st.warning(f"**Tem certeza que deseja excluir permanentemente o treinamento '{row['norma']}'?** Esta ação não pode ser desfeita.")
                                    c1, c2 = st.columns(2)
                                    if c1.button("Sim, excluir agora", key=f"confirm_del_btn_{row['id']}"):
                                        if employee_manager.delete_training(row['id'], row['arquivo_id']):
                                            st.success("Treinamento excluído com sucesso.")
                                            del st.session_state[f"confirm_delete_{row['id']}"]
                                            st.rerun()
                                        else:
                                            st.error("Falha ao excluir.")
                                    if c2.button("Cancelar", key=f"cancel_del_btn_{row['id']}"):
                                        del st.session_state[f"confirm_delete_{row['id']}"]
                                        st.rerun()
                        else:
                                st.info("Nenhum treinamento encontrado."

            st.markdown("---")
            with st.expander("📖 Histórico de Auditorias de Conformidade"):
                audit_history = docs_manager.get_audits_by_company(selected_company)
                
                if not audit_history.empty:
                    audit_history_display = audit_history.copy()
                    if 'data_auditoria' in audit_history_display.columns:
                        audit_history_display['data_auditoria'] = pd.to_datetime(audit_history_display['data_auditoria'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
                        audit_history_display.dropna(subset=['data_auditoria'], inplace=True)
                    
                    # Agrupa os resultados por 'id_auditoria'
                    for audit_id, group in audit_history_display.groupby('id_auditoria'):
                        # Pega a primeira linha do grupo para informações gerais
                        first_row = group.iloc[0]
                        
                        resumo_row = group[group['item_de_verificacao'].str.contains("Resumo da Auditoria", case=False, na=False)]
                        
                        if not resumo_row.empty:
                            resumo_text = resumo_row.iloc[0]['observacao']
                            status = resumo_row.iloc[0]['Status']
                            
                            # Determina o alvo da auditoria (funcionário ou empresa)
                            target_name = ""
                            emp_id = first_row.get('id_funcionario')
                            if pd.notna(emp_id) and emp_id != 'N/A':
                                target_name = employee_manager.get_employee_name(emp_id) or f"Funcionário (ID: {emp_id})"
                            else:
                                # Garante que estamos buscando na lista correta de empresas
                                company_info = employee_manager.companies_df[employee_manager.companies_df['id'] == first_row['id_empresa']]
                                if not company_info.empty:
                                    target_name = company_info['nome'].iloc[0]
                                else:
                                    target_name = f"Empresa (ID: {first_row['id_empresa']})"

                            # Define o título e a data da auditoria
                            audit_title = f"**{first_row.get('tipo_documento')} ({first_row.get('norma_auditada')})** para **{target_name}**"
                            audit_date = first_row['data_auditoria'].strftime('%d/%m/%Y às %H:%M')
                            
                            # Exibe as informações de forma limpa, com cor baseada no status do resumo
                            st.markdown(f"**Análise de {audit_title}**")
                            st.caption(f"Realizada em: {audit_date}")
                            
                            if 'não conforme' in str(status).lower():
                                st.error(f"**Parecer da IA:** {resumo_text}")
                            else:
                                st.info(f"**Parecer da IA:** {resumo_text}")
                            st.markdown("---")
                else:
                    st.info("Nenhum histórico de auditoria encontrado para esta empresa.")

    with tab_add_doc_empresa:
        if selected_company:
            if check_admin_permission():
                st.subheader("Adicionar Documento (PGR, PCMSO, etc.)")
                company_name = employee_manager.companies_df[employee_manager.companies_df['id'] == selected_company]['nome'].iloc[0]
                st.info(f"Adicionando documento para a empresa: **{company_name}**")
                st.file_uploader("Anexar Documento (PDF)", type=['pdf'], key="doc_uploader_tab", on_change=process_company_doc_pdf)
                if st.session_state.get('doc_info_para_salvar'):
                    doc_info = st.session_state.doc_info_para_salvar
                    if doc_info and doc_info.get('data_emissao'):
                        with st.container(border=True):
                            st.markdown("### Confirme as Informações Extraídas")
                            st.write(f"**Tipo Identificado:** {doc_info['tipo_documento']}")
                            st.write(f"**Data de Emissão/Vigência:** {doc_info['data_emissao'].strftime('%d/%m/%Y')}")
                            st.success(f"**Vencimento Calculado:** {doc_info['vencimento'].strftime('%d/%m/%Y')}")
                            if st.button("Confirmar e Salvar Documento", type="primary"):
                                with st.spinner("Salvando documento..."):
                                    anexo_doc = st.session_state.doc_anexo_para_salvar
                                    arquivo_id = gdrive_uploader.upload_file(anexo_doc, f"{doc_info['tipo_documento']}_{company_name}_{doc_info['data_emissao']}")
                                    if arquivo_id:
                                        doc_id = docs_manager.add_company_document(empresa_id=selected_company, tipo_documento=doc_info['tipo_documento'], data_emissao=doc_info['data_emissao'], vencimento=doc_info['vencimento'], arquivo_id=arquivo_id)
                                        if doc_id:
                                            st.success("Documento da empresa salvo com sucesso!")
                                            for key in ['doc_info_para_salvar', 'doc_anexo_para_salvar']:
                                                if key in st.session_state: del st.session_state[key]
                                            st.rerun()
                                        else: st.error("Falha ao salvar os dados na planilha.")
                                    else: st.error("Falha ao fazer upload do anexo.")
                    else:
                        st.error("Não foi possível extrair data de emissão do PDF.")
                        if 'doc_info_para_salvar' in st.session_state: del st.session_state.doc_info_para_salvar
            else: st.error("Você não tem permissão para esta ação.")
        else: st.info("Selecione uma empresa na primeira aba para adicionar documentos.")

    with tab_add_aso:
        if selected_company:
            if check_admin_permission():
                st.subheader("Adicionar Novo ASO")
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="aso_employee_add")
                    st.file_uploader("Anexar ASO (PDF)", type=['pdf'], key="aso_uploader_tab", on_change=process_aso_pdf)
                    if st.session_state.get('aso_info_para_salvar'):
                        aso_info = st.session_state.aso_info_para_salvar
                        if aso_info and aso_info.get('data_aso'):
                            with st.container(border=True):
                                st.markdown("### Confirme as Informações Extraídas")
                                st.write(f"**Data:** {aso_info['data_aso'].strftime('%d/%m/%Y')}")
                                st.write(f"**Tipo de ASO Identificado:** {aso_info.get('tipo_aso', 'N/A')}")
                                vencimento_aso = aso_info.get('vencimento')
                                if vencimento_aso: st.success(f"**Vencimento:** {vencimento_aso.strftime('%d/%m/%Y')}")
                                else: st.info("**Vencimento:** N/A (Ex: Demissional)")
                                if st.button("Confirmar e Salvar ASO", type="primary"):
                                    with st.spinner("Salvando ASO..."):
                                        anexo_aso = st.session_state.aso_anexo_para_salvar
                                        selected_employee_aso = st.session_state.aso_funcionario_para_salvar
                                        arquivo_id = gdrive_uploader.upload_file(anexo_aso, f"ASO_{selected_employee_aso}_{aso_info['data_aso']}")
                                        if arquivo_id:
                                            aso_id = employee_manager.add_aso(id=selected_employee_aso, arquivo_id=arquivo_id, **aso_info)
                                            if aso_id:
                                                st.success(f"ASO adicionado com sucesso! ID: {aso_id}")
                                                for key in ['aso_info_para_salvar', 'aso_anexo_para_salvar', 'aso_funcionario_para_salvar']:
                                                    if key in st.session_state: del st.session_state[key]
                                                st.rerun()
                                            else: st.error("Falha ao salvar os dados na planilha.")
                                        else: st.error("Falha ao fazer o upload do anexo para o Google Drive.")
                        else:
                            st.error("Não foi possível extrair informações válidas do PDF.")
                            if 'aso_info_para_salvar' in st.session_state: del st.session_state.aso_info_para_salvar
                else: st.warning("Cadastre funcionários nesta empresa primeiro.")
            else: st.error("Você não tem permissão para esta ação.")
        else: st.info("Selecione uma empresa na primeira aba.")

    with tab_add_treinamento:
        if selected_company:
            if check_admin_permission():
                st.subheader("Adicionar Novo Treinamento")
                mostrar_info_normas()
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="training_employee_add")
                    st.file_uploader("Anexar Certificado (PDF)", type=['pdf'], key="training_uploader_tab", on_change=process_training_pdf)
                    if st.session_state.get('training_info_para_salvar'):
                        training_info = st.session_state.training_info_para_salvar
                        if training_info and training_info.get('data'):
                            with st.container(border=True):
                                st.markdown("### Confirme as Informações Extraídas")
                                data = training_info.get('data')
                                norma_bruta = training_info.get('norma')
                                norma_padronizada = employee_manager._padronizar_norma(norma_bruta)
                                modulo = training_info.get('modulo')
                                tipo_treinamento = training_info.get('tipo_treinamento')
                                carga_horaria = training_info.get('carga_horaria', 0)
                                vencimento = employee_manager.calcular_vencimento_treinamento(data=data, norma=norma_padronizada, modulo=modulo, tipo_treinamento=tipo_treinamento)
                                st.write(f"**Data:** {data.strftime('%d/%m/%Y')}")
                                st.write(f"**Norma Extraída:** {norma_bruta} (Padronizada para: {norma_padronizada})")
                                st.write(f"**Módulo:** {modulo or 'N/A'}")
                                st.write(f"**Tipo:** {tipo_treinamento}")
                                st.write(f"**Carga Horária:** {carga_horaria} horas")
                                if vencimento: st.success(f"**Vencimento Calculado:** {vencimento.strftime('%d/%m/%Y')}")
                                else: st.error(f"**Falha ao Calcular Vencimento:** A norma '{norma_padronizada}' com módulo '{modulo}' não foi encontrada nas configurações.")
                                if st.button("Confirmar e Salvar Treinamento", type="primary", disabled=(vencimento is None)):
                                    with st.spinner("Salvando Treinamento..."):
                                        anexo_training = st.session_state.training_anexo_para_salvar
                                        selected_employee_training = st.session_state.training_funcionario_para_salvar
                                        arquivo_id = gdrive_uploader.upload_file(anexo_training, f"TRAINING_{selected_employee_training}_{norma_padronizada}")
                                        if arquivo_id:
                                            training_info.update({'id': selected_employee_training, 'anexo': arquivo_id, 'vencimento': vencimento, 'status': "Válido", 'norma': norma_padronizada})
                                            training_id = employee_manager.add_training(**training_info)
                                            if training_id:
                                                st.success(f"Treinamento adicionado! ID: {training_id}")
                                                for key in ['training_info_para_salvar', 'training_anexo_para_salvar', 'training_funcionario_para_salvar']:
                                                    if key in st.session_state: del st.session_state[key]
                                                st.rerun()
                                            else: st.error("Falha ao salvar dados na planilha.")
                                        else: st.error("Falha ao fazer o upload do anexo.")
                        else:
                            st.error("Não foi possível extrair informações válidas do PDF.")
                            if 'training_info_para_salvar' in st.session_state: del st.session_state.training_info_para_salvar
                else: st.warning("Cadastre funcionários nesta empresa primeiro.")
            else: st.error("Você não tem permissão para esta ação.")
        else: st.info("Selecione uma empresa na primeira aba.")
