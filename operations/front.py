import streamlit as st
from datetime import datetime, date
import pandas as pd
from operations.employee import EmployeeManager
from operations.company_docs import CompanyDocsManager
from gdrive.gdrive_upload import GoogleDriveUploader
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
        | NR-11 | 16-32 horas               | 16 horas              | 3 anos                   |
        | NR-33 | 16-40 horas               | 8 horas               | 1 ano                    |
        | Brigada | 24 horas (Avançado)     | 16 horas (Avançado)   | 1 ano                    |
        """)

def highlight_expired(row):
    today = datetime.now().date()
    try:
        vencimento_val = pd.to_datetime(row.get('vencimento')).date()
    except (ValueError, TypeError):
        vencimento_val = row.get('vencimento')

    if pd.notna(vencimento_val) and isinstance(vencimento_val, date):
        if vencimento_val < today:
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
    
    st.title("Gestão de Documentação de Contratada")
    
    selected_company_id = None
    if not employee_manager.companies_df.empty:
        df = employee_manager.companies_df.astype({'id': 'str'})
        selected_company_id = st.selectbox(
            "Selecione uma empresa",
            df['id'].tolist(),
            format_func=lambda x: f"{df[df['id'] == x]['nome'].iloc[0]} - {df[df['id'] == x]['cnpj'].iloc[0]}",
            key="company_select",
            index=None,
            placeholder="Selecione uma empresa..."
        )
    
    tab_situacao, tab_add_doc_empresa, tab_add_aso, tab_add_treinamento = st.tabs([
        "**Situação Geral**", "**Adicionar Documento da Empresa**", "Adicionar ASO", "Adicionar Treinamento"
    ])

    with tab_situacao:
        if selected_company_id:
            st.subheader("Documentos da Empresa")
            company_docs = docs_manager.get_docs_by_company(selected_company_id).copy()
            if not company_docs.empty:
                st.dataframe(
                    company_docs,
                    column_config={"arquivo_id": st.column_config.LinkColumn("Anexo")},
                    hide_index=True, use_container_width=True
                )
            else:
                st.info("Nenhum documento da empresa cadastrado.")
            
            st.markdown("---")
            st.subheader("Funcionários")
            employees = employee_manager.get_employees_by_company(selected_company_id)
            if not employees.empty:
                for index, employee in employees.iterrows():
                    employee_id = employee['id']
                    expander_title = f"**{employee['nome']}** - *{employee['cargo']}*"

                    with st.expander(expander_title):
                        # --- SEÇÃO DE AÇÕES EM MASSA ---
                        st.markdown("**Ações para este funcionário:**")
                        action_cols = st.columns(2)
                        
                        with action_cols[0]:
                            if st.button("🗄️ Arquivar todos os documentos", key=f"archive_all_{employee_id}", help="Marca todos os treinamentos como 'Arquivado'. Útil para desligamentos."):
                                st.session_state[f"confirm_archive_all_{employee_id}"] = True
                        
                        with action_cols[1]:
                            if st.button("🗑️ Excluir funcionário e todos os dados", key=f"delete_all_{employee_id}", type="primary"):
                                st.session_state[f"confirm_delete_all_{employee_id}"] = True

                        # Lógica de confirmação para ARQUIVAR
                        if st.session_state.get(f"confirm_archive_all_{employee_id}"):
                            st.info(f"Tem certeza que deseja arquivar todos os treinamentos de **{employee['nome']}**?")
                            c1, c2, _ = st.columns([1, 1, 4])
                            if c1.button("Sim, arquivar", key=f"confirm_arc_btn_{employee_id}"):
                                with st.spinner("Arquivando..."):
                                    if employee_manager.archive_all_employee_docs(employee_id):
                                        st.success("Todos os treinamentos foram arquivados.")
                                        del st.session_state[f"confirm_archive_all_{employee_id}"]
                                        st.rerun()
                            if c2.button("Cancelar", key=f"cancel_arc_btn_{employee_id}"):
                                del st.session_state[f"confirm_archive_all_{employee_id}"]
                                st.rerun()

                        # Lógica de confirmação para EXCLUIR
                        if st.session_state.get(f"confirm_delete_all_{employee_id}"):
                            st.error(f"**ALERTA IRREVERSÍVEL!** Tem certeza que deseja excluir **{employee['nome']}** e TODOS os seus documentos (ASOs, Treinamentos) permanentemente?")
                            c1, c2, _ = st.columns([1, 1, 4])
                            if c1.button("Sim, excluir tudo", key=f"confirm_del_all_btn_{employee_id}"):
                                with st.spinner("Excluindo todos os dados do funcionário..."):
                                    if employee_manager.delete_all_employee_data(employee_id):
                                        st.success("Funcionário e todos os seus dados foram excluídos.")
                                        del st.session_state[f"confirm_delete_all_{employee_id}"]
                                        st.rerun()
                            if c2.button("Cancelar", key=f"cancel_del_all_btn_{employee_id}"):
                                del st.session_state[f"confirm_delete_all_{employee_id}"]
                                st.rerun()

                        st.divider()

                        # --- SEÇÃO DE VISUALIZAÇÃO DE DOCUMENTOS ---
                        st.markdown("##### Atestados de Saúde Ocupacional (ASO)")
                        latest_aso = employee_manager.get_latest_aso_by_employee(employee_id)
                        if not latest_aso.empty:
                            st.dataframe(
                                latest_aso.style.apply(highlight_expired, axis=1),
                                column_config={"arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF")},
                                hide_index=True, use_container_width=True
                            )
                        else:
                            st.info("Nenhum ASO encontrado.")
                        
                        st.markdown("##### Treinamentos")
                        all_trainings = employee_manager.get_all_trainings_by_employee(employee_id)
                        active_trainings = all_trainings[all_trainings.get('status', 'Ativo') != 'Arquivado']
                        if not active_trainings.empty:
                            st.dataframe(
                                active_trainings.style.apply(highlight_expired, axis=1),
                                column_config={"arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF")},
                                hide_index=True, use_container_width=True
                            )
                        else:
                            st.info("Nenhum treinamento ativo encontrado.")
            else:
                st.info("Nenhum funcionário cadastrado para esta empresa.")
        else:
            st.info("Selecione uma empresa para visualizar os dados.")
            
    with tab_add_doc_empresa:
        if selected_company_id:
            if check_admin_permission():
                company_name = employee_manager.get_company_name(selected_company_id)
                st.subheader("Adicionar Documento (PGR, PCMSO, etc.)")
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
                                        doc_id = docs_manager.add_company_document(empresa_id=selected_company_id, tipo_documento=doc_info['tipo_documento'], data_emissao=doc_info['data_emissao'], vencimento=doc_info['vencimento'], arquivo_id=arquivo_id)
                                        if doc_id:
                                            st.success("Documento da empresa salvo com sucesso!")
                                            st.session_state.pop('doc_info_para_salvar', None)
                                            st.session_state.pop('doc_anexo_para_salvar', None)
                                            st.rerun()
            else:
                st.error("Você não tem permissão para esta ação.")
        else:
            st.info("Selecione uma empresa na primeira aba para adicionar documentos.")

    with tab_add_aso:
        if selected_company_id:
            if check_admin_permission():
                st.subheader("Adicionar Novo ASO")
                current_employees = employee_manager.get_employees_by_company(selected_company_id)
                if not current_employees.empty:
                    st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="aso_employee_add")
                    st.file_uploader("Anexar ASO (PDF)", type=['pdf'], key="aso_uploader_tab", on_change=process_aso_pdf)
                    if st.session_state.get('aso_info_para_salvar'):
                        aso_info = st.session_state.aso_info_para_salvar
                        if aso_info and aso_info.get('data_aso'):
                            with st.container(border=True):
                                st.markdown("### Confirme as Informações Extraídas")
                                st.write(f"**Data:** {aso_info['data_aso'].strftime('%d/%m/%Y')}")
                                vencimento_aso = aso_info.get('vencimento')
                                if vencimento_aso:
                                    st.success(f"**Vencimento:** {vencimento_aso.strftime('%d/%m/%Y')}")
                                if st.button("Confirmar e Salvar ASO", type="primary"):
                                    with st.spinner("Salvando ASO..."):
                                        anexo_aso = st.session_state.aso_anexo_para_salvar
                                        selected_employee_aso = st.session_state.aso_funcionario_para_salvar
                                        arquivo_id = gdrive_uploader.upload_file(anexo_aso, f"ASO_{selected_employee_aso}_{aso_info['data_aso']}")
                                        if arquivo_id:
                                            aso_info_to_add = aso_info.copy()
                                            aso_id = employee_manager.add_aso(id=selected_employee_aso, arquivo_id=arquivo_id, **aso_info_to_add)
                                            if aso_id:
                                                st.success(f"ASO adicionado com sucesso! ID: {aso_id}")
                                                st.session_state.pop('aso_info_para_salvar', None)
                                                st.session_state.pop('aso_anexo_para_salvar', None)
                                                st.session_state.pop('aso_funcionario_para_salvar', None)
                                                st.rerun()
                else:
                    st.warning("Cadastre funcionários nesta empresa primeiro.")
            else:
                st.error("Você não tem permissão para esta ação.")
        else:
            st.info("Selecione uma empresa na primeira aba.")
            
    with tab_add_treinamento:
        if selected_company_id:
            if check_admin_permission():
                st.subheader("Adicionar Novo Treinamento")
                mostrar_info_normas()
                current_employees = employee_manager.get_employees_by_company(selected_company_id)
                if not current_employees.empty:
                    st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="training_employee_add")
                    st.file_uploader("Anexar Certificado (PDF)", type=['pdf'], key="training_uploader_tab", on_change=process_training_pdf)
                    if st.session_state.get('training_info_para_salvar'):
                        training_info = st.session_state.training_info_para_salvar
                        if training_info and training_info.get('data'):
                            with st.container(border=True):
                                st.markdown("### Confirme as Informações Extraídas")
                                data = training_info.get('data')
                                norma_padronizada = employee_manager._padronizar_norma(training_info.get('norma'))
                                vencimento = employee_manager.calcular_vencimento_treinamento(data=data, norma=norma_padronizada, modulo=training_info.get('modulo'), tipo_treinamento=training_info.get('tipo_treinamento'))
                                st.write(f"**Norma:** {norma_padronizada}")
                                if vencimento:
                                    st.success(f"**Vencimento Calculado:** {vencimento.strftime('%d/%m/%Y')}")
                                else:
                                    st.error("Falha ao calcular vencimento.")
                                if st.button("Confirmar e Salvar Treinamento", type="primary", disabled=(vencimento is None)):
                                    with st.spinner("Salvando Treinamento..."):
                                        anexo_training = st.session_state.training_anexo_para_salvar
                                        selected_employee_training = st.session_state.training_funcionario_para_salvar
                                        arquivo_id = gdrive_uploader.upload_file(anexo_training, f"TRAINING_{selected_employee_training}_{norma_padronizada}")
                                        if arquivo_id:
                                            training_info_to_add = training_info.copy()
                                            training_info_to_add.update({'id': selected_employee_training, 'anexo': arquivo_id, 'vencimento': vencimento, 'status': "Ativo"})
                                            training_id = employee_manager.add_training(**training_info_to_add)
                                            if training_id:
                                                st.success(f"Treinamento adicionado! ID: {training_id}")
                                                st.session_state.pop('training_info_para_salvar', None)
                                                st.session_state.pop('training_anexo_para_salvar', None)
                                                st.session_state.pop('training_funcionario_para_salvar', None)
                                                st.rerun()
                else:
                    st.warning("Cadastre funcionários nesta empresa primeiro.")
            else:
                st.error("Você não tem permissão para esta ação.")
        else:
            st.info("Selecione uma empresa na primeira aba.")
