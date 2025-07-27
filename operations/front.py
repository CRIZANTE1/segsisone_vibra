import streamlit as st
from datetime import datetime, date
from operations.employee import EmployeeManager
from operations.company_docs import CompanyDocsManager
from gdrive.gdrive_upload import GoogleDriveUploader
import pandas as pd
from auth.auth_utils import check_admin_permission
from operations.epi import EPIManager

from ui.ui_helpers import (
    mostrar_info_normas,
    highlight_expired,
    process_aso_pdf,
    process_training_pdf,
    process_company_doc_pdf,
    process_epi_pdf
)



def front_page():
    if 'employee_manager' not in st.session_state:
        st.session_state.employee_manager = EmployeeManager()
    if 'docs_manager' not in st.session_state:
        st.session_state.docs_manager = CompanyDocsManager()
    if 'epi_manager' not in st.session_state:
        st.session_state.epi_manager = EPIManager()    
    
    employee_manager = st.session_state.employee_manager
    docs_manager = st.session_state.docs_manager
    epi_manager = st.session_state.epi_manager
    
    employee_manager.load_data()
    docs_manager.load_company_data()
    epi_manager.load_epi_data()
    
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
    
    tab_situacao, tab_add_doc_empresa, tab_add_aso, tab_add_treinamento, tab_add_epi = st.tabs([
        "**Situação Geral**", "**Adicionar Documento da Empresa**", "Adicionar ASO", "Adicionar Treinamento", "Adicionar Ficha de EPI"        
    ])

    with tab_situacao:
        if selected_company:
            st.subheader("Documentos da Empresa")
            company_docs = docs_manager.get_docs_by_company(selected_company).copy()
            if not company_docs.empty:
                company_docs['data_emissao'] = pd.to_datetime(company_docs['data_emissao'], format='%d/%m/%Y', errors='coerce').dt.date
                company_docs['vencimento'] = pd.to_datetime(company_docs['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
                company_doc_cols = ["tipo_documento", "data_emissao", "vencimento", "arquivo_id"]
                for col in company_doc_cols:
                    if col not in company_docs.columns: company_docs[col] = "N/A"
                company_docs_reordered = company_docs[company_doc_cols]
                st.dataframe(company_docs_reordered.style.apply(highlight_expired, axis=1), column_config={"tipo_documento": "Documento", "data_emissao": st.column_config.DateColumn("Emissão", format="DD/MM/YYYY"), "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF"),}, hide_index=True, use_container_width=True)
            else: st.info("Nenhum documento (ex: PGR, PCMSO) cadastrado para esta empresa.")
            
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
                            aso_display_cols = ["tipo_aso", "data_aso", "vencimento", "cargo", "riscos", "arquivo_id"]
                            for col in aso_display_cols:
                                if col not in latest_aso.columns: latest_aso[col] = "N/A"
                            aso_reordered_df = latest_aso[aso_display_cols]
                            st.dataframe(aso_reordered_df.style.apply(highlight_expired, axis=1), column_config={"tipo_aso": "Tipo", "data_aso": st.column_config.DateColumn("Data", format="DD/MM/YYYY"), "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), "cargo": "Cargo (ASO)", "riscos": "Riscos", "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF"), "id": None, "funcionario_id": None,}, hide_index=True, use_container_width=True)
                        else: st.info("Nenhum ASO encontrado.")
                        st.markdown("##### Todos os Treinamentos")
                        if not all_trainings.empty:
                            training_display_cols = ["norma", "data", "vencimento", "tipo_treinamento", "carga_horaria", "arquivo_id"]
                            for col in training_display_cols:
                                if col not in all_trainings.columns: all_trainings[col] = "N/A"
                            training_reordered_df = all_trainings[training_display_cols]
                            st.dataframe(training_reordered_df.style.apply(highlight_expired, axis=1), column_config={"norma": "Norma", "data": st.column_config.DateColumn("Realização", format="DD/MM/YYYY"), "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), "tipo_treinamento": "Tipo", "carga_horaria": st.column_config.NumberColumn("C.H.", help="Carga Horária (horas)"), "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF"), "id": None, "funcionario_id": None, "status": None, "modulo": None,}, hide_index=True, use_container_width=True)
                        else: st.info("Nenhum treinamento encontrado.")

                        st.markdown("##### Equipamentos de Proteção Individual (EPIs)")
                        all_epis = epi_manager.get_epi_by_employee(employee_id)
                        if not all_epis.empty:
                            epi_display_cols = ["descricao_epi", "ca_epi", "data_entrega", "arquivo_id"]
                            st.dataframe(
                                all_epis[epi_display_cols],
                                column_config={
                                    "descricao_epi": "Equipamento",
                                    "ca_epi": "C.A.",
                                    "data_entrega": "Data de Entrega",
                                    "arquivo_id": st.column_config.LinkColumn("Ficha (PDF)", display_text="Abrir PDF")
                                },
                                hide_index=True, use_container_width=True
                            )
                        else:
                            st.info("Nenhuma Ficha de EPI encontrada para este funcionário.")
                

            
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

    
    with tab_add_epi:
        if selected_company:
            if check_admin_permission():
                st.subheader("Adicionar Nova Ficha de EPI")
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="epi_employee_add")
                    st.file_uploader("Anexar Ficha de EPI (PDF)", type=['pdf'], key="epi_uploader_tab", on_change=process_epi_pdf)
                    
                    if st.session_state.get('epi_info_para_salvar'):
                        epi_info = st.session_state.epi_info_para_salvar
                        if epi_info and epi_info.get('itens_epi'):
                            with st.container(border=True):
                                st.markdown("### Confirme as Informações Extraídas")
                                
                                # Validação do nome do funcionário
                                nome_extraido = epi_info.get('nome_funcionario', 'N/A')
                                funcionario_selecionado_id = st.session_state.epi_funcionario_para_salvar
                                nome_selecionado = employee_manager.get_employee_name(funcionario_selecionado_id)
                                
                                st.write(f"**Funcionário no PDF:** {nome_extraido}")
                                st.write(f"**Funcionário Selecionado:** {nome_selecionado}")
                                
                                if nome_extraido.lower() not in nome_selecionado.lower():
                                    st.warning("Atenção: O nome do funcionário no PDF não parece corresponder ao funcionário selecionado. Prossiga com cuidado.")
                                
                                st.markdown("**Itens de EPI encontrados na ficha:**")
                                itens_df = pd.DataFrame(epi_info['itens_epi'])
                                st.dataframe(itens_df, hide_index=True, use_container_width=True)

                                if st.button("Confirmar e Salvar Itens da Ficha de EPI", type="primary"):
                                    with st.spinner("Salvando Ficha de EPI..."):
                                        anexo_epi = st.session_state.epi_anexo_para_salvar
                                        
                                        # Upload do arquivo PDF
                                        arquivo_id = gdrive_uploader.upload_file(anexo_epi, f"EPI_{nome_selecionado}_{date.today().strftime('%Y-%m-%d')}")
                                        
                                        if arquivo_id:
                                            # Adiciona os registros na planilha
                                            saved_ids = epi_manager.add_epi_records(funcionario_selecionado_id, arquivo_id, epi_info['itens_epi'])
                                            
                                            if saved_ids:
                                                st.success(f"{len(saved_ids)} item(ns) de EPI salvos com sucesso!")
                                                # Limpa o estado da sessão para resetar a interface
                                                for key in ['epi_info_para_salvar', 'epi_anexo_para_salvar', 'epi_funcionario_para_salvar']:
                                                    if key in st.session_state: del st.session_state[key]
                                                st.rerun()
                                            else:
                                                st.error("Falha ao salvar os dados na planilha.")
                                        else:
                                            st.error("Falha ao fazer o upload do anexo para o Google Drive.")
                        else:
                            st.error("Não foi possível extrair itens de EPI válidos do PDF.")
                            if 'epi_info_para_salvar' in st.session_state: del st.session_state['epi_info_para_salvar']
                else:
                    st.warning("Cadastre funcionários nesta empresa primeiro.")
            else:
                st.error("Você não tem permissão para esta ação.")
        else:
            st.info("Selecione uma empresa na primeira aba para adicionar Fichas de EPI.")
            
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

