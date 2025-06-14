# /mount/src/segsisone/operations/front.py

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
        | Avançado I | 32 horas         | 1 ano                      | 4 horas                  |
        | Avançado II | 40 horas         | 1 ano                      | 4 horas                  |
        
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
    # Adiciona uma verificação para garantir que o valor não é NaT (Not a Time)
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
    docs_manager.load_company_docs_data()
    
    gdrive_uploader = GoogleDriveUploader()
    
    st.title("Gestão de Documentação de Contratada")
    
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
            company_docs = docs_manager.get_docs_by_company(selected_company)
            
            if not company_docs.empty:
                # Converte as colunas de data para o tipo datetime
                company_docs['data_emissao'] = pd.to_datetime(company_docs['data_emissao'], format='%d/%m/%Y', errors='coerce').dt.date
                company_docs['vencimento'] = pd.to_datetime(company_docs['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date

                company_doc_cols = ["tipo_documento", "data_emissao", "vencimento", "arquivo_id"]
                for col in company_doc_cols:
                    if col not in company_docs.columns:
                        company_docs[col] = "N/A"
                
                company_docs_reordered = company_docs[company_doc_cols]
                
                st.dataframe(
                    company_docs_reordered.style.apply(highlight_expired, axis=1),
                    column_config={
                        "tipo_documento": "Documento",
                        "data_emissao": st.column_config.DateColumn("Data de Emissão", format="DD/MM/YYYY"),
                        "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                        "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF"),
                    },
                    hide_index=True, use_container_width=True
                )
            else: 
                st.info("Nenhum documento (ex: PGR, PCMSO) cadastrado para esta empresa.")
            
            st.markdown("---")
            st.subheader("Funcionários")
            
            employees = employee_manager.get_employees_by_company(selected_company)
            if not employees.empty:
                for index, employee in employees.iterrows():
                    employee_id = employee['id']; employee_name = employee['nome']; employee_role = employee['cargo']
                    today = datetime.now().date(); aso_status = 'Não encontrado'; aso_vencimento = None; trainings_total = 0; trainings_expired_count = 0
                    
                    latest_aso = employee_manager.get_latest_aso_by_employee(employee_id)
                    if not latest_aso.empty:
                        vencimento_aso_obj = latest_aso['vencimento'].iloc[0]
                        if isinstance(vencimento_aso_obj, date):
                             aso_vencimento = vencimento_aso_obj
                             aso_status = 'Válido' if aso_vencimento >= today else 'Vencido'

                    all_trainings = employee_manager.get_all_trainings_by_employee(employee_id)
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
                            aso_display_cols = ["tipo_aso", "data_aso", "vencimento", "cargo", "riscos", "arquivo_id"]
                            for col in aso_display_cols:
                                if col not in latest_aso.columns:
                                    latest_aso[col] = "N/A"
                            aso_reordered_df = latest_aso[aso_display_cols]
                            st.dataframe(aso_reordered_df.style.apply(highlight_expired, axis=1), column_config={"tipo_aso": "Tipo", "data_aso": st.column_config.DateColumn("Data", format="DD/MM/YYYY"), "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), "cargo": "Cargo (ASO)", "riscos": "Riscos", "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF"), "id": None, "funcionario_id": None,}, hide_index=True, use_container_width=True)
                        else: st.info("Nenhum ASO encontrado.")

                        st.markdown("##### Todos os Treinamentos")
                        if not all_trainings.empty:
                            training_display_cols = ["norma", "data", "vencimento", "tipo_treinamento", "carga_horaria", "arquivo_id"]
                            for col in training_display_cols:
                                if col not in all_trainings.columns:
                                    all_trainings[col] = "N/A"
                            training_reordered_df = all_trainings[training_display_cols]
                            st.dataframe(training_reordered_df.style.apply(highlight_expired, axis=1), column_config={"norma": "Norma", "data": st.column_config.DateColumn("Realização", format="DD/MM/YYYY"), "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), "tipo_treinamento": "Tipo", "carga_horaria": st.column_config.NumberColumn("C.H.", help="Carga Horária (horas)"), "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF"), "id": None, "funcionario_id": None, "status": None, "modulo": None,}, hide_index=True, use_container_width=True)
                        else: st.info("Nenhum treinamento encontrado.")
            else:
                st.info("Nenhum funcionário cadastrado para esta empresa.")
        else:
            if employee_manager.companies_df.empty:
                with st.form("cadastro_empresa"):
                    st.subheader("Cadastrar Nova Empresa"); nome_empresa = st.text_input("Nome"); cnpj = st.text_input("CNPJ")
                    if st.form_submit_button("Cadastrar") and nome_empresa and cnpj:
                        _, message = employee_manager.add_company(nome_empresa, cnpj)
                        st.success(message); st.rerun()

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
                                        doc_id = docs_manager.add_company_document(
                                            empresa_id=selected_company,
                                            tipo_documento=doc_info['tipo_documento'],
                                            data_emissao=doc_info['data_emissao'],
                                            vencimento=doc_info['vencimento'],
                                            arquivo_id=arquivo_id
                                        )
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
                                            else:
                                                st.error("Falha ao salvar os dados na planilha.")
                                        else:
                                            st.error("Falha ao fazer o upload do anexo para o Google Drive.")
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
                                            else:
                                                st.error("Falha ao salvar dados na planilha.")
                                        else:
                                            st.error("Falha ao fazer o upload do anexo.")
                        else:
                            st.error("Não foi possível extrair informações válidas do PDF.")
                            if 'training_info_para_salvar' in st.session_state: del st.session_state.training_info_para_salvar
                else: st.warning("Cadastre funcionários nesta empresa primeiro.")
            else: st.error("Você não tem permissão para esta ação.")
        else: st.info("Selecione uma empresa na primeira aba.")

   

   
