import streamlit as st
from datetime import date
import pandas as pd
import logging

from auth.auth_utils import check_permission
from ui.ui_helpers import (
    mostrar_info_normas,
    highlight_expired,
    process_aso_pdf,
    process_training_pdf,
    process_company_doc_pdf,
    process_epi_pdf
)

logger = logging.getLogger('segsisone_app.dashboard')

def format_company_display(company_id, companies_df):
    """Formata o nome da empresa para exibição no selectbox."""
    if company_id is None:
        return "Selecione..."
    try:
        # Garante que estamos comparando tipos de dados consistentes (string com string)
        row = companies_df[companies_df['id'] == str(company_id)].iloc[0]
        name = row.get('nome', f"Empresa ID {company_id}")
        status = str(row.get('status', 'Ativo')).lower()
        if status == 'arquivado':
            return f"🗄️ {name} (Arquivada)"
        else:
            return f"{name} - {row.get('cnpj', 'N/A')}"
    except (IndexError, KeyError):
        return f"Empresa ID {company_id} (Não encontrada)"

def display_audit_results(audit_result):
    """Exibe os resultados da auditoria de forma visual."""
    if not audit_result: return
    summary = audit_result.get("summary", "Indefinido")
    details = audit_result.get("details", [])
    st.markdown("---"); st.markdown("##### 🔍 Resultado da Auditoria Rápida")
    if summary.lower() == 'conforme':
        st.success(f"**Parecer da IA:** {summary}")
    elif 'não conforme' in summary.lower():
        st.error(f"**Parecer da IA:** {summary}")
        with st.expander("Ver detalhes", expanded=True):
            for item in details:
                if item.get("status", "").lower() == "não conforme":
                    st.markdown(f"- **Item:** {item.get('item_verificacao')}\n- **Observação:** {item.get('observacao')}")
    else:
        st.info(f"**Parecer da IA:** {summary}")

def show_dashboard_page():
    logger.info("Iniciando a renderização da página do dashboard.")
    if not st.session_state.get('managers_initialized'):
        logger.warning("Managers não inicializados, parando a renderização do dashboard.")
        st.warning("Selecione uma unidade operacional para visualizar o dashboard.")
        st.info("Administradores podem usar o seletor na barra lateral.")
        return
        
    employee_manager = st.session_state.employee_manager
    docs_manager = st.session_state.docs_manager
    epi_manager = st.session_state.epi_manager
    nr_analyzer = st.session_state.nr_analyzer
    
    st.title("Dashboard de Conformidade")
    
    company_options = [None] + employee_manager.companies_df['id'].astype(str).tolist()
    
    selected_company = st.selectbox(
        "Selecione uma empresa para ver os detalhes:",
        options=company_options,
        format_func=lambda cid: format_company_display(cid, employee_manager.companies_df),
        key="company_selector"
    )

    tab_situacao, tab_add_doc_empresa, tab_add_aso, tab_add_treinamento, tab_add_epi = st.tabs([
        "**Situação Geral**", "**Adicionar Documento da Empresa**", "Adicionar ASO", "Adicionar Treinamento", "Adicionar Ficha de EPI"        
    ])

    with tab_situacao:
        if selected_company:
            logger.info(f"Empresa selecionada: {selected_company}. Renderizando detalhes.")
            try:
                st.subheader("Documentos da Empresa")
                company_docs = docs_manager.get_docs_by_company(selected_company).copy()
                
                expected_doc_cols = ["tipo_documento", "data_emissao", "vencimento", "arquivo_id"]
                if not company_docs.empty and all(col in company_docs.columns for col in expected_doc_cols):
                    # Cria a coluna de data para o estilo
                    company_docs['vencimento_dt'] = pd.to_datetime(company_docs['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
                    
                    # --- CORREÇÃO PRINCIPAL AQUI ---
                    st.dataframe(
                        # Passa o DataFrame inteiro com a coluna 'vencimento_dt'
                        company_docs.style.apply(highlight_expired, axis=1),
                        # Esconde a coluna 'vencimento_dt' da visualização do usuário
                        column_config={
                            "tipo_documento": "Documento", 
                            "data_emissao": "Emissão", 
                            "vencimento": "Vencimento", 
                            "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF"),
                            "vencimento_dt": None # Esconde a coluna
                        }, 
                        # Define a ordem das colunas para garantir que as colunas extras não apareçam no final
                        column_order=expected_doc_cols,
                        hide_index=True, 
                        use_container_width=True
                    )
                elif not company_docs.empty:
                    st.error("A aba 'documentos_empresa' parece estar com colunas faltando. Esperado: " + ", ".join(expected_doc_cols))
                    st.dataframe(company_docs)
                else: 
                    st.info("Nenhum documento (ex: PGR, PCMSO) cadastrado para esta empresa.")
                
                st.markdown("---")

                st.subheader("Funcionários")
                employees = employee_manager.get_employees_by_company(selected_company)
                
                if not employees.empty:
                    for index, employee in employees.iterrows():
                        employee_id = employee.get('id')
                        employee_name = employee.get('nome', 'Nome não encontrado')
                        employee_cargo = employee.get('cargo', 'Cargo não encontrado')
                        
                        expander_title = f"**{employee_name}** - *{employee_cargo}*"

                        with st.expander(expander_title):
                            st.markdown(f"##### Situação de: {employee_name}")
                            
                            # --- LÓGICA ROBUSTA PARA ASOS ---
                            st.markdown("**ASOs (Mais Recente por Tipo)**")
                            latest_asos = employee_manager.get_latest_aso_by_employee(employee_id).copy()
                            expected_aso_cols = ["tipo_aso", "data_aso", "vencimento", "arquivo_id"]
                            if not latest_asos.empty and all(c in latest_asos.columns for c in expected_aso_cols):
                                latest_asos['vencimento_dt'] = pd.to_datetime(latest_asos['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
                                st.dataframe(
                                    latest_asos.style.apply(highlight_expired, axis=1), 
                                    column_config={
                                        "arquivo_id": st.column_config.LinkColumn("Anexo"),
                                        "vencimento_dt": None
                                    },
                                    column_order=expected_aso_cols,
                                    hide_index=True, use_container_width=True
                                )
                            else:
                                st.info("Nenhum ASO encontrado ou colunas ausentes.")

                            # --- LÓGICA ROBUSTA PARA TREINAMENTOS ---
                            st.markdown("**Treinamentos (Mais Recente por Norma)**")
                            all_trainings = employee_manager.get_all_trainings_by_employee(employee_id).copy()
                            expected_training_cols = ["norma", "data", "vencimento", "anexo"]
                            if not all_trainings.empty and all(c in all_trainings.columns for c in expected_training_cols):
                                all_trainings['vencimento_dt'] = pd.to_datetime(all_trainings['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
                                st.dataframe(
                                    all_trainings.style.apply(highlight_expired, axis=1), 
                                    column_config={
                                        "anexo": st.column_config.LinkColumn("Anexo"),
                                        "vencimento_dt": None
                                    },
                                    column_order=expected_training_cols,
                                    hide_index=True, use_container_width=True
                                )
                            else:
                                st.info("Nenhum treinamento encontrado ou colunas ausentes.")

                else:
                    st.info("Nenhum funcionário cadastrado para esta empresa.")
            
            except Exception as e:
                logger.error(f"ERRO CRÍTICO ao renderizar dashboard para empresa {selected_company}: {e}", exc_info=True)
                st.error("Ocorreu um erro inesperado ao tentar exibir os detalhes desta empresa.")
                st.exception(e)

        else:
            st.info("Selecione uma empresa para visualizar os detalhes.")

    with tab_add_epi:
        if not selected_company: st.info("Selecione uma empresa na aba 'Situação Geral' primeiro.")
        elif check_permission(level='editor'):
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
                            if nome_extraido.lower() not in nome_selecionado.lower(): st.warning("Atenção: O nome do funcionário não corresponde ao selecionado.")
                            st.markdown("**Itens de EPI encontrados:**")
                            st.dataframe(pd.DataFrame(epi_info['itens_epi']), hide_index=True, use_container_width=True)
                            if st.button("Confirmar e Salvar Itens da Ficha de EPI", type="primary"):
                                with st.spinner("Salvando..."):
                                    arquivo_id = employee_manager.upload_documento_e_obter_link(st.session_state.epi_anexo_para_salvar, f"EPI_{nome_selecionado}_{date.today().strftime('%Y-%m-%d')}")
                                    if arquivo_id:
                                        saved_ids = epi_manager.add_epi_records(funcionario_selecionado_id, arquivo_id, epi_info['itens_epi'])
                                        if saved_ids:
                                            st.success(f"{len(saved_ids)} item(ns) de EPI salvos!")
                                            st.session_state.force_reload = True
                                            for key in ['epi_info_para_salvar', 'epi_anexo_para_salvar', 'epi_funcionario_para_salvar']:
                                                if key in st.session_state: del st.session_state[key]
                                            st.rerun()
            else: st.warning("Cadastre funcionários nesta empresa primeiro.")
            
    with tab_add_doc_empresa:
        if not selected_company: st.info("Selecione uma empresa na aba 'Situação Geral' primeiro.")
        elif check_permission(level='editor'):
            st.subheader("Adicionar Documento da Empresa")
            company_name = employee_manager.get_company_name(selected_company)
            st.info(f"Adicionando documento para: **{company_name}**")
            st.file_uploader("Anexar Documento (PDF)", type=['pdf'], key="doc_uploader_tab", on_change=process_company_doc_pdf)
            
            if st.session_state.get('Doc. Empresa_info_para_salvar'):
                doc_info = st.session_state['Doc. Empresa_info_para_salvar']
                if doc_info and doc_info.get('data_emissao'):
                    with st.container(border=True):
                        st.markdown("### Confirme as Informações Extraídas")
                        st.write(f"**Tipo:** {doc_info['tipo_documento']}")
                        st.write(f"**Data de Emissão:** {doc_info['data_emissao'].strftime('%d/%m/%Y')}")
                        st.success(f"**Vencimento:** {doc_info['vencimento'].strftime('%d/%m/%Y')}")
                        display_audit_results(doc_info.get('audit_result'))
                        if st.button("Confirmar e Salvar Documento", type="primary"):
                            with st.spinner("Salvando..."):
                                arquivo_id = employee_manager.upload_documento_e_obter_link(st.session_state['Doc. Empresa_anexo_para_salvar'], f"{doc_info['tipo_documento']}_{company_name}_{doc_info['data_emissao'].strftime('%Y%m%d')}")
                                if arquivo_id:
                                    doc_id = docs_manager.add_company_document(selected_company, doc_info['tipo_documento'], doc_info['data_emissao'], doc_info['vencimento'], arquivo_id)
                                    if doc_id:
                                        st.success("Documento salvo!")
                                        audit_result = doc_info.get('audit_result')
                                        if audit_result and 'não conforme' in audit_result.get("summary", "").lower():
                                            created = nr_analyzer.create_action_plan_from_audit(audit_result, selected_company, doc_id)
                                            st.info(f"{created} item(ns) de ação foram criados.")
                                        st.session_state.force_reload = True
                                        for key in ['Doc. Empresa_info_para_salvar', 'Doc. Empresa_anexo_para_salvar']:
                                            if key in st.session_state: del st.session_state[key]
                                        st.rerun()

    with tab_add_aso:
        if not selected_company: st.info("Selecione uma empresa na aba 'Situação Geral' primeiro.")
        elif check_permission(level='editor'):
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
                            st.write(f"**Tipo:** {aso_info.get('tipo_aso', 'N/A')}")
                            if aso_info.get('vencimento'): st.success(f"**Vencimento:** {aso_info['vencimento'].strftime('%d/%m/%Y')}")
                            else: st.info("**Vencimento:** N/A")
                            display_audit_results(aso_info.get('audit_result'))
                            if st.button("Confirmar e Salvar ASO", type="primary"):
                                with st.spinner("Salvando..."):
                                    emp_id = st.session_state.ASO_funcionario_para_salvar
                                    emp_name = employee_manager.get_employee_name(emp_id)
                                    arquivo_id = employee_manager.upload_documento_e_obter_link(st.session_state.ASO_anexo_para_salvar, f"ASO_{emp_name}_{aso_info['data_aso'].strftime('%Y%m%d')}")
                                    if arquivo_id:
                                        aso_data = {**aso_info, 'funcionario_id': emp_id, 'arquivo_id': arquivo_id}
                                        aso_id = employee_manager.add_aso(aso_data)
                                        if aso_id:
                                            st.success("ASO salvo!")
                                            audit_result = aso_info.get('audit_result')
                                            if audit_result and 'não conforme' in audit_result.get("summary", "").lower():
                                                created = nr_analyzer.create_action_plan_from_audit(audit_result, selected_company, aso_id, emp_id)
                                                st.info(f"{created} item(ns) de ação foram criados.")
                                            st.session_state.force_reload = True
                                            for key in ['ASO_info_para_salvar', 'ASO_anexo_para_salvar', 'ASO_funcionario_para_salvar']:
                                                if key in st.session_state: del st.session_state[key]
                                            st.rerun()
            else: st.warning("Cadastre funcionários nesta empresa primeiro.")

    with tab_add_treinamento:
        if not selected_company: st.info("Selecione uma empresa na aba 'Situação Geral' primeiro.")
        elif check_permission(level='editor'):
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
                            if vencimento: st.success(f"**Vencimento:** {vencimento.strftime('%d/%m/%Y')}")
                            else: st.error("Vencimento não calculado.")
                            display_audit_results(training_info.get('audit_result'))
                            if st.button("Confirmar e Salvar Treinamento", type="primary", disabled=(vencimento is None)):
                                with st.spinner("Salvando..."):
                                    emp_id = st.session_state.Treinamento_funcionario_para_salvar
                                    emp_name = employee_manager.get_employee_name(emp_id)
                                    arquivo_id = employee_manager.upload_documento_e_obter_link(st.session_state.Treinamento_anexo_para_salvar, f"TRAINING_{emp_name}_{norma}_{data.strftime('%Y%m%d')}")
                                    if arquivo_id:
                                        training_data = {**training_info, 'funcionario_id': emp_id, 'vencimento': vencimento, 'anexo': arquivo_id}
                                        training_id = employee_manager.add_training(training_data)
                                        if training_id:
                                            st.success("Treinamento salvo!")
                                            audit_result = training_info.get('audit_result')
                                            if audit_result and 'não conforme' in audit_result.get("summary", "").lower():
                                                created = nr_analyzer.create_action_plan_from_audit(audit_result, selected_company, training_id, emp_id)
                                                st.info(f"{created} item(ns) de ação foram criados.")
                                            st.session_state.force_reload = True
                                            for key in ['Treinamento_info_para_salvar', 'Treinamento_anexo_para_salvar', 'Treinamento_funcionario_para_salvar']:
                                                if key in st.session_state: del st.session_state[key]
                                            st.rerun()
            else: st.warning("Cadastre funcionários nesta empresa primeiro.")
