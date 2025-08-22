import streamlit as st
from datetime import date
import pandas as pd
from fuzzywuzzy import fuzz
import re

from auth.auth_utils import check_permission
from ui.ui_helpers import (
    mostrar_info_normas,
    highlight_expired,
    process_aso_pdf,
    process_training_pdf,
    process_company_doc_pdf,
    process_epi_pdf
)

def format_company_display(company_id, companies_df):
    try:
        company_row = companies_df[companies_df['id'] == str(company_id)].iloc[0]
        name = company_row['nome']
        status = company_row.get('status', 'Ativo')
        if str(status).lower() == 'arquivado':
            return f"🗄️ {name} (Arquivada)"
        else:
            cnpj = company_row.get('cnpj', 'CNPJ não informado')
            return f"{name} - {cnpj}"
    except (IndexError, KeyError):
        return f"Empresa ID {company_id} não encontrada"

def display_audit_results(audit_result):
    if not audit_result: return
    summary = audit_result.get("summary", "Indefinido")
    details = audit_result.get("details", [])
    st.markdown("---")
    st.markdown("##### 🔍 Resultado da Auditoria Rápida")
    if summary.lower() == 'conforme':
        st.success(f"**Parecer da IA:** {summary}")
    elif 'não conforme' in summary.lower():
        st.error(f"**Parecer da IA:** {summary}")
        with st.expander("Ver detalhes da não conformidade", expanded=True):
            for item in details:
                if item.get("status", "").lower() == "não conforme":
                    st.markdown(f"- **Item:** {item.get('item_verificacao')}\n- **Observação:** {item.get('observacao')}")
    else:
        st.info(f"**Parecer da IA:** {summary}")

def show_dashboard_page():
    if not st.session_state.get('managers_initialized'):
        st.warning("Selecione uma unidade operacional para visualizar o dashboard.")
        st.info("Administradores globais podem usar o seletor 'Operar como Unidade' na barra lateral.")
        return
        
    employee_manager = st.session_state.employee_manager
    docs_manager = st.session_state.docs_manager
    epi_manager = st.session_state.epi_manager
    matrix_manager = st.session_state.matrix_manager
    nr_analyzer = st.session_state.nr_analyzer
    
    st.title("Dashboard de Conformidade")
    
    selected_company = None
    if not employee_manager.companies_df.empty:
        companies_to_display = employee_manager.companies_df.sort_values(by=['status', 'nome'], ascending=[True, True])
        selected_company = st.selectbox(
            "Selecione uma empresa para ver os detalhes:",
            options=companies_to_display['id'].tolist(),
            format_func=lambda company_id: format_company_display(company_id, companies_to_display),
            index=None,
            placeholder="Selecione uma empresa...",
            key="company_select"
        )
    
    tab_situacao, tab_add_doc_empresa, tab_add_aso, tab_add_treinamento, tab_add_epi = st.tabs([
        "**Situação Geral**", "**Adicionar Documento da Empresa**", "Adicionar ASO", "Adicionar Treinamento", "Adicionar Ficha de EPI"        
    ])

    with tab_situacao:
        if selected_company:
            if check_permission(level='editor'):
                st.subheader("Documentos da Empresa")
                company_docs = docs_manager.get_docs_by_company(selected_company).copy()
                if not company_docs.empty:
                    company_docs['data_emissao'] = pd.to_datetime(company_docs['data_emissao'], format='%d/%m/%Y', errors='coerce').dt.date
                    company_docs['vencimento'] = pd.to_datetime(company_docs['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
                    company_doc_cols = ["tipo_documento", "data_emissao", "vencimento", "arquivo_id"]
                    for col in company_doc_cols:
                        if col not in company_docs.columns: company_docs[col] = "N/A"
                    company_docs_reordered = company_docs[company_doc_cols]
                    st.dataframe(
                        company_docs_reordered.style.apply(highlight_expired, axis=1), 
                        column_config={
                            "tipo_documento": "Documento", "data_emissao": st.column_config.DateColumn("Emissão", format="DD/MM/YYYY"), 
                            "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), 
                            "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF")
                        }, 
                        hide_index=True, use_container_width=True
                    )
                else: st.info("Nenhum documento (ex: PGR, PCMSO) cadastrado para esta empresa.")
                
                st.markdown("---")
                st.subheader("Funcionários")
                employees = employee_manager.get_employees_by_company(selected_company)
                if not employees.empty:
                    for index, employee in employees.iterrows():
                        employee_id, employee_name, employee_role = employee['id'], employee['nome'], employee['cargo']
                        today = date.today()
                        aso_status, aso_vencimento = 'Não encontrado', None
                        
                        latest_asos_by_type = employee_manager.get_latest_aso_by_employee(employee_id)
                        if not latest_asos_by_type.empty:
                            aptitude_asos = latest_asos_by_type[~latest_asos_by_type['tipo_aso'].str.lower().isin(['demissional'])].copy()
                            if not aptitude_asos.empty:
                                current_aptitude_aso = aptitude_asos.sort_values('data_aso', ascending=False).iloc[0]
                                vencimento_obj = current_aptitude_aso.get('vencimento')
                                if pd.notna(vencimento_obj) and isinstance(vencimento_obj, date):
                                    aso_vencimento = vencimento_obj
                                    aso_status = 'Válido' if aso_vencimento >= today else 'Vencido'
                                else:
                                    aso_status = 'Venc. Indefinido'
                            else:
                                aso_status = 'Apenas Demissional'
                        
                        all_trainings = employee_manager.get_all_trainings_by_employee(employee_id)
                        trainings_total, trainings_expired_count = 0, 0
                        if not all_trainings.empty:
                            trainings_total = len(all_trainings)
                            valid_trainings = all_trainings.copy()
                            valid_trainings['vencimento_dt'] = pd.to_datetime(valid_trainings['vencimento'], errors='coerce').dt.date
                            valid_trainings.dropna(subset=['vencimento_dt'], inplace=True)
                            if not valid_trainings.empty:
                                expired_mask = valid_trainings['vencimento_dt'] < today
                                trainings_expired_count = expired_mask.sum()

                        overall_status = 'Em Dia' if aso_status not in ['Vencido'] and trainings_expired_count == 0 else 'Pendente'
                        status_icon = "✅" if overall_status == 'Em Dia' else "⚠️"
                        expander_title = f"{status_icon} **{employee_name}** - *{employee_role}*"

                        with st.expander(expander_title):
                            num_pendencias = trainings_expired_count + (1 if aso_status == 'Vencido' else 0)
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Status Geral", overall_status, f"{num_pendencias} pendência(s)" if num_pendencias > 0 else "Nenhuma pendência", delta_color="inverse" if overall_status != 'Em Dia' else "off")
                            col2.metric("Status do ASO", aso_status, help=f"Vencimento: {aso_vencimento.strftime('%d/%m/%Y') if aso_vencimento else 'N/A'}")
                            col3.metric("Treinamentos Vencidos", f"{trainings_expired_count} de {trainings_total}")
                            
                            st.markdown("---")
                            st.markdown("##### ASO Mais Recente por Tipo")
                            if not latest_asos_by_type.empty:
                                aso_display_cols = ["tipo_aso", "data_aso", "vencimento", "cargo", "riscos", "arquivo_id"]
                                st.dataframe(
                                    latest_asos_by_type[aso_display_cols].style.apply(highlight_expired, axis=1),
                                    column_config={"tipo_aso": "Tipo", "data_aso": "Data", "vencimento": "Vencimento", "cargo": "Cargo (ASO)", "riscos": "Riscos", "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF")},
                                    hide_index=True, use_container_width=True
                                )
                            else: st.info("Nenhum ASO encontrado.")
                            
                            st.markdown("##### Treinamentos Válidos (Mais Recente por Norma)")
                            if not all_trainings.empty:
                                training_display_cols = ["norma", "data", "vencimento", "tipo_treinamento", "carga_horaria", "arquivo_id"]
                                st.dataframe(
                                    all_trainings[training_display_cols].style.apply(highlight_expired, axis=1),
                                    column_config={"norma": "Norma", "data": "Realização", "vencimento": "Vencimento", "tipo_treinamento": "Tipo", "carga_horaria": "C.H.", "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF")},
                                    hide_index=True, use_container_width=True
                                )
                            else: st.info("Nenhum treinamento encontrado.")
    
                            st.markdown("##### Equipamentos de Proteção Individual (EPIs)")
                            all_epis = epi_manager.get_epi_by_employee(employee_id)
                            if not all_epis.empty:
                                epi_display_cols = ["descricao_epi", "ca_epi", "data_entrega", "arquivo_id"]
                                st.dataframe(all_epis[epi_display_cols],
                                    column_config={"descricao_epi": "Equipamento", "ca_epi": "C.A.", "data_entrega": "Data de Entrega", "arquivo_id": st.column_config.LinkColumn("Ficha (PDF)", display_text="Abrir PDF")},
                                    hide_index=True, use_container_width=True
                                )
                            else: st.info("Nenhuma Ficha de EPI encontrada.")

                            st.markdown("---")
                            st.markdown("##### Matriz de Conformidade de Treinamentos")
                            employee_cargo = employee.get('cargo', '').strip()
                            if not employee_cargo:
                                st.info("O cargo deste funcionário não está cadastrado, impossibilitando a análise de matriz.")
                            else:
                                matched_function_name = employee_manager.find_closest_function(employee_cargo)
                                if not matched_function_name:
                                    st.success(f"✅ O cargo '{employee_cargo}' não possui treinamentos obrigatórios na matriz da unidade.")
                                else:
                                    if employee_cargo.lower() != matched_function_name.lower():
                                        st.caption(f"Analisando com base na função da matriz mais próxima: **'{matched_function_name}'**")
                                    required_trainings = employee_manager.get_required_trainings_for_function(matched_function_name)
                                    if not required_trainings:
                                        st.success(f"✅ Nenhum treinamento obrigatório mapeado para a função '{matched_function_name}'.")
                                    else:
                                        current_trainings_norms = all_trainings['norma'].dropna().tolist() if not all_trainings.empty else []
                                        missing_trainings, status_list = [], []
                                        for required in required_trainings:
                                            found = any(fuzz.partial_ratio(required.lower(), current.lower()) > 85 for current in current_trainings_norms)
                                            status = "✅ Realizado" if found else "🔴 Faltante"
                                            status_list.append({"Treinamento Obrigatório": required, "Status": status})
                                            if not found: missing_trainings.append(required)
                                        
                                        if not missing_trainings:
                                            st.success("✅ Todos os treinamentos obrigatórios para esta função foram realizados.")
                                        else:
                                            st.error(f"⚠️ **Treinamentos Faltantes:** {', '.join(sorted(missing_trainings))}")
                                        st.dataframe(pd.DataFrame(status_list), use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhum funcionário cadastrado para esta empresa.")

    with tab_add_epi:
        if selected_company:
            if check_permission(level='editor'):
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
                                nome_extraido = epi_info.get('nome_funcionario', 'N/A')
                                funcionario_selecionado_id = st.session_state.epi_funcionario_para_salvar
                                nome_selecionado = employee_manager.get_employee_name(funcionario_selecionado_id)
                                
                                st.write(f"**Funcionário no PDF:** {nome_extraido}")
                                st.write(f"**Funcionário Selecionado:** {nome_selecionado}")
                                if nome_extraido.lower() not in nome_selecionado.lower():
                                    st.warning("Atenção: O nome do funcionário no PDF não corresponde ao funcionário selecionado.")
                                
                                st.markdown("**Itens de EPI encontrados na ficha:**")
                                st.dataframe(pd.DataFrame(epi_info['itens_epi']), hide_index=True, use_container_width=True)

                                if st.button("Confirmar e Salvar Itens da Ficha de EPI", type="primary"):
                                    with st.spinner("Salvando Ficha de EPI..."):
                                        anexo_epi = st.session_state.epi_anexo_para_salvar
                                        arquivo_id = employee_manager.upload_documento_e_obter_link(anexo_epi, f"EPI_{nome_selecionado}_{date.today().strftime('%Y-%m-%d')}")
                                        if arquivo_id:
                                            saved_ids = epi_manager.add_epi_records(funcionario_selecionado_id, arquivo_id, epi_info['itens_epi'])
                                            if saved_ids:
                                                st.success(f"{len(saved_ids)} item(ns) de EPI salvos com sucesso!")
                                                for key in ['epi_info_para_salvar', 'epi_anexo_para_salvar', 'epi_funcionario_para_salvar']:
                                                    if key in st.session_state: del st.session_state[key]
                                                st.rerun()
                                            else: st.error("Falha ao salvar os dados na planilha.")
                                        else: st.error("Falha no upload do anexo para o Google Drive.")
                        else:
                            st.error("Não foi possível extrair itens de EPI válidos do PDF.")
                            if 'epi_info_para_salvar' in st.session_state: del st.session_state['epi_info_para_salvar']
                else: st.warning("Cadastre funcionários nesta empresa primeiro.")
        else: st.info("Selecione uma empresa na primeira aba para adicionar Fichas de EPI.")
            
    with tab_add_doc_empresa:
        if selected_company:
            if check_permission(level='editor'):
                st.subheader("Adicionar Documento (PGR, PCMSO, etc.)")
                company_name = employee_manager.get_company_name(selected_company)
                st.info(f"Adicionando documento para a empresa: **{company_name}**")
                st.file_uploader("Anexar Documento (PDF)", type=['pdf'], key="doc_uploader_tab", on_change=process_company_doc_pdf)
                
                if st.session_state.get('Doc. Empresa_info_para_salvar'):
                    doc_info = st.session_state['Doc. Empresa_info_para_salvar']
                    if doc_info and doc_info.get('data_emissao'):
                        with st.container(border=True):
                            st.markdown("### Confirme as Informações Extraídas")
                            st.write(f"**Tipo Identificado:** {doc_info['tipo_documento']}")
                            st.write(f"**Data de Emissão:** {doc_info['data_emissao'].strftime('%d/%m/%Y')}")
                            st.success(f"**Vencimento Calculado:** {doc_info['vencimento'].strftime('%d/%m/%Y')}")
                            display_audit_results(doc_info.get('audit_result'))
                            if st.button("Confirmar e Salvar Documento", type="primary"):
                                with st.spinner("Salvando documento..."):
                                    anexo_doc = st.session_state['Doc. Empresa_anexo_para_salvar']
                                    arquivo_id = employee_manager.upload_documento_e_obter_link(anexo_doc, f"{doc_info['tipo_documento']}_{company_name}_{doc_info['data_emissao'].strftime('%Y%m%d')}")
                                    if arquivo_id:
                                        doc_id = docs_manager.add_company_document(selected_company, doc_info['tipo_documento'], doc_info['data_emissao'], doc_info['vencimento'], arquivo_id)
                                        if doc_id:
                                            audit_result = doc_info.get('audit_result')
                                            if audit_result and 'não conforme' in audit_result.get("summary", "").lower():
                                                created_count = nr_analyzer.create_action_plan_from_audit(audit_result, selected_company, doc_id)
                                                st.success(f"Documento salvo! {created_count} item(ns) de ação foram criados.")
                                            else:
                                                st.success("Documento salvo com sucesso!")
                                            for key in ['Doc. Empresa_info_para_salvar', 'Doc. Empresa_anexo_para_salvar']:
                                                if key in st.session_state: del st.session_state[key]
                                            st.rerun()
        else: st.info("Selecione uma empresa para adicionar um documento.")

    with tab_add_aso:
        if selected_company:
            if check_permission(level='editor'):
                st.subheader("Adicionar Novo ASO")
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="aso_employee_add")
                    st.file_uploader("Anexar ASO (PDF)", type=['pdf'], key="aso_uploader_tab", on_change=process_aso_pdf)
                    
                    if st.session_state.get('ASO_info_para_salvar'):
                        aso_info = st.session_state.ASO_info_para_salvar
                        if aso_info and aso_info.get('data_aso'):
                            with st.container(border=True):
                                st.markdown("### Confirme as Informações Extraídas")
                                st.write(f"**Data:** {aso_info['data_aso'].strftime('%d/%m/%Y')}")
                                st.write(f"**Tipo de ASO:** {aso_info.get('tipo_aso', 'N/A')}")
                                if aso_info.get('vencimento'): st.success(f"**Vencimento:** {aso_info['vencimento'].strftime('%d/%m/%Y')}")
                                else: st.info("**Vencimento:** N/A (Ex: Demissional)")
                                display_audit_results(aso_info.get('audit_result'))
                                if st.button("Confirmar e Salvar ASO", type="primary"):
                                    with st.spinner("Salvando ASO..."):
                                        anexo = st.session_state.ASO_anexo_para_salvar
                                        emp_id = st.session_state.ASO_funcionario_para_salvar
                                        emp_name = employee_manager.get_employee_name(emp_id)
                                        arquivo_id = employee_manager.upload_documento_e_obter_link(anexo, f"ASO_{emp_name}_{aso_info['data_aso'].strftime('%Y%m%d')}")
                                        if arquivo_id:
                                            aso_data = {**aso_info, 'funcionario_id': emp_id, 'arquivo_id': arquivo_id}
                                            aso_id = employee_manager.add_aso(aso_data)
                                            if aso_id:
                                                audit_result = aso_info.get('audit_result')
                                                if audit_result and 'não conforme' in audit_result.get("summary", "").lower():
                                                    created_count = nr_analyzer.create_action_plan_from_audit(audit_result, selected_company, aso_id, employee_id=emp_id)
                                                    st.success(f"ASO salvo! {created_count} item(ns) de ação foram criados.")
                                                else:
                                                    st.success("ASO adicionado com sucesso!")
                                                for key in ['ASO_info_para_salvar', 'ASO_anexo_para_salvar', 'ASO_funcionario_para_salvar']:
                                                    if key in st.session_state: del st.session_state[key]
                                                st.rerun()
                else: st.warning("Cadastre funcionários nesta empresa primeiro.")
        else: st.info("Selecione uma empresa para adicionar um ASO.")

    with tab_add_treinamento:
        if selected_company:
            if check_permission(level='editor'):
                st.subheader("Adicionar Novo Treinamento")
                mostrar_info_normas()
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="training_employee_add")
                    st.file_uploader("Anexar Certificado (PDF)", type=['pdf'], key="training_uploader_tab", on_change=process_training_pdf)
                    
                    if st.session_state.get('Treinamento_info_para_salvar'):
                        training_info = st.session_state['Treinamento_info_para_salvar']
                        if training_info and training_info.get('data'):
                            with st.container(border=True):
                                st.markdown("### Confirme as Informações Extraídas")
                                data, norma, modulo, tipo, ch = training_info.get('data'), training_info.get('norma'), training_info.get('modulo'), training_info.get('tipo_treinamento'), training_info.get('carga_horaria', 0)
                                vencimento = employee_manager.calcular_vencimento_treinamento(data, norma, modulo, tipo)
                                st.write(f"**Data:** {data.strftime('%d/%m/%Y')}")
                                st.write(f"**Norma:** {norma}")
                                st.write(f"**Módulo:** {modulo or 'N/A'}")
                                st.write(f"**Tipo:** {tipo}")
                                st.write(f"**Carga Horária:** {ch} horas")
                                if vencimento: st.success(f"**Vencimento Calculado:** {vencimento.strftime('%d/%m/%Y')}")
                                else: st.error("Não foi possível calcular o vencimento.")
                                display_audit_results(training_info.get('audit_result'))
                                if st.button("Confirmar e Salvar Treinamento", type="primary", disabled=(vencimento is None)):
                                    with st.spinner("Salvando Treinamento..."):
                                        anexo = st.session_state.Treinamento_anexo_para_salvar
                                        emp_id = st.session_state.Treinamento_funcionario_para_salvar
                                        emp_name = employee_manager.get_employee_name(emp_id)
                                        arquivo_id = employee_manager.upload_documento_e_obter_link(anexo, f"TRAINING_{emp_name}_{norma}_{data.strftime('%Y%m%d')}")
                                        if arquivo_id:
                                            training_data = {**training_info, 'funcionario_id': emp_id, 'vencimento': vencimento, 'anexo': arquivo_id}
                                            training_id = employee_manager.add_training(training_data)
                                            if training_id:
                                                audit_result = training_info.get('audit_result')
                                                if audit_result and 'não conforme' in audit_result.get("summary", "").lower():
                                                    created_count = nr_analyzer.create_action_plan_from_audit(audit_result, selected_company, training_id, employee_id=emp_id)
                                                    st.success(f"Treinamento salvo! {created_count} item(ns) de ação foram criados.")
                                                else:
                                                    st.success("Treinamento adicionado com sucesso!")
                                                for key in ['Treinamento_info_para_salvar', 'Treinamento_anexo_para_salvar', 'Treinamento_funcionario_para_salvar']:
                                                    if key in st.session_state: del st.session_state[key]
                                                st.rerun()
                else: st.warning("Cadastre funcionários nesta empresa primeiro.")
        else: st.info("Selecione uma empresa para adicionar um treinamento.")
