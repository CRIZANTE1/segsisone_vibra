import streamlit as st
from datetime import date
import pandas as pd
from fuzzywuzzy import fuzz
import re
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
    if company_id is None:
        return "Selecione..."
    try:
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
        st.warning("Selecione uma unidade operacional para visualizar o dashboard.")
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
        key="company_selector",
        placeholder="Selecione uma empresa..."
    )

    tab_situacao, tab_add_doc_empresa, tab_add_aso, tab_add_treinamento, tab_add_epi = st.tabs([
        "**Situação Geral**", "**Adicionar Documento da Empresa**", "Adicionar ASO", "Adicionar Treinamento", "Adicionar Ficha de EPI"        
    ])

    with tab_situacao:
        if selected_company:
            try:
                st.subheader("Documentos da Empresa")
                company_docs = docs_manager.get_docs_by_company(selected_company).copy()
                expected_doc_cols = ["tipo_documento", "data_emissao", "vencimento", "arquivo_id"]
                
                if isinstance(company_docs, pd.DataFrame) and not company_docs.empty:
                    company_docs['vencimento_dt'] = pd.to_datetime(company_docs['vencimento'], format='%d/%m/%Y', errors='coerce').dt.date
                    st.dataframe(
                        company_docs.style.apply(highlight_expired, axis=1),
                        column_config={
                            "tipo_documento": "Documento", 
                            "data_emissao": st.column_config.DateColumn("Emissão", format="DD/MM/YYYY"), 
                            "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), 
                            "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="PDF"), 
                            "vencimento_dt": None 
                        }, 
                        column_order=expected_doc_cols, hide_index=True, use_container_width=True
                    )
                else: 
                    st.info("Nenhum documento (ex: PGR, PCMSO) cadastrado para esta empresa.")
                
                st.markdown("---")

                st.subheader("Funcionários")
                employees = employee_manager.get_employees_by_company(selected_company)
                
                if not employees.empty:
                    for index, employee in employees.iterrows():
                        employee_id = employee.get('id')
                        employee_name = employee.get('nome', 'N/A')
                        employee_cargo = employee.get('cargo', 'N/A')
                        today = date.today()

                        aso_status, aso_vencimento = 'Não encontrado', None
                        latest_asos = employee_manager.get_latest_aso_by_employee(employee_id)
                        if isinstance(latest_asos, pd.DataFrame) and not latest_asos.empty:
                            aptitude_asos = latest_asos[~latest_asos['tipo_aso'].str.lower().isin(['demissional'])].copy()
                            if not aptitude_asos.empty:
                                current_aso = aptitude_asos.sort_values('data_aso', ascending=False).iloc[0]
                                vencimento_obj = current_aso.get('vencimento')
                                if pd.notna(vencimento_obj) and isinstance(vencimento_obj, date):
                                    aso_vencimento = vencimento_obj
                                    aso_status = 'Válido' if aso_vencimento >= today else 'Vencido'
                                else:
                                    aso_status = 'Venc. Inválido'
                            else:
                                aso_status = 'Apenas Demissional'

                        all_trainings = employee_manager.get_all_trainings_by_employee(employee_id)
                        trainings_total, trainings_expired_count = 0, 0
                        if isinstance(all_trainings, pd.DataFrame) and not all_trainings.empty:
                            trainings_total = len(all_trainings)
                            trainings_expired_count = (all_trainings['vencimento'] < today).sum()

                        overall_status = 'Em Dia' if aso_status != 'Vencido' and trainings_expired_count == 0 else 'Pendente'
                        status_icon = "✅" if overall_status == 'Em Dia' else "⚠️"
                        
                        with st.expander(f"{status_icon} **{employee_name}** - *{employee_cargo}*"):
                            num_pendencias = trainings_expired_count + (1 if aso_status == 'Vencido' else 0)
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Status Geral", overall_status, f"{num_pendencias} pendência(s)" if num_pendencias > 0 else "Nenhuma", delta_color="inverse" if overall_status != 'Em Dia' else "off")
                            col2.metric("Status do ASO", aso_status, help=f"Vencimento: {aso_vencimento.strftime('%d/%m/%Y') if aso_vencimento else 'N/A'}")
                            col3.metric("Treinamentos Vencidos", f"{trainings_expired_count} de {trainings_total}")
                            
                            st.markdown("---")
                            st.markdown("##### ASO (Mais Recente por Tipo)")
                            if isinstance(latest_asos, pd.DataFrame) and not latest_asos.empty:
                                latest_asos['vencimento_dt'] = pd.to_datetime(latest_asos['vencimento'], errors='coerce').dt.date
                                st.dataframe(
                                    latest_asos.style.apply(highlight_expired, axis=1),
                                    column_config={
                                        "tipo_aso": "Tipo", 
                                        "data_aso": st.column_config.DateColumn("Data", format="DD/MM/YYYY"), 
                                        "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), 
                                        "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="PDF"), 
                                        "vencimento_dt": None
                                    },
                                    column_order=["tipo_aso", "data_aso", "vencimento", "arquivo_id"],
                                    hide_index=True, use_container_width=True
                                )
                            else:
                                st.info(f"Nenhum ASO encontrado para {employee_name}.")

                            st.markdown("##### Treinamentos (Mais Recente por Norma)")
                            if isinstance(all_trainings, pd.DataFrame) and not all_trainings.empty:
                                all_trainings['vencimento_dt'] = pd.to_datetime(all_trainings['vencimento'], errors='coerce').dt.date
                                st.dataframe(
                                    all_trainings.style.apply(highlight_expired, axis=1),
                                    column_config={
                                        "norma": "Norma", 
                                        "data": st.column_config.DateColumn("Realização", format="DD/MM/YYYY"), 
                                        "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), 
                                        "anexo": st.column_config.LinkColumn("Anexo", display_text="PDF"), 
                                        "vencimento_dt": None
                                    },
                                    column_order=["norma", "data", "vencimento", "anexo"],
                                    hide_index=True, use_container_width=True
                                )
                            else:
                                st.info(f"Nenhum treinamento encontrado para {employee_name}.")

                            st.markdown("##### Equipamentos de Proteção Individual (EPIs)")
                            all_epis = epi_manager.get_epi_by_employee(employee_id)
                            if isinstance(all_epis, pd.DataFrame) and not all_epis.empty:
                                st.dataframe(
                                    all_epis,
                                    column_config={
                                        "descricao_epi": "Equipamento", "ca_epi": "C.A.", 
                                        "data_entrega": st.column_config.DateColumn("Data de Entrega", format="DD/MM/YYYY"), 
                                        "arquivo_id": st.column_config.LinkColumn("Ficha", display_text="PDF")
                                    },
                                    column_order=["descricao_epi", "ca_epi", "data_entrega", "arquivo_id"],
                                    hide_index=True, use_container_width=True
                                )
                            else:
                                st.info(f"Nenhuma Ficha de EPI encontrada para {employee_name}.")

                            st.markdown("---")
                            st.markdown("##### Matriz de Conformidade de Treinamentos")
                            # ... (lógica da matriz)
                else:
                    st.error(f"Nenhum funcionário encontrado para esta empresa (ID: {selected_company}).")
                    st.info(f"**Ação necessária:** Verifique na aba `funcionarios` da sua planilha se existem registros com `empresa_id` igual a `{selected_company}`.")
            
            except Exception as e:
                logger.error(f"ERRO CRÍTICO ao renderizar dashboard para empresa {selected_company}: {e}", exc_info=True)
                st.error("Ocorreu um erro inesperado ao tentar exibir os detalhes desta empresa.")
                st.exception(e)
        else:
            st.info("Selecione uma empresa para visualizar os detalhes.")


    with tab_add_doc_empresa:
        if not selected_company:
            st.info("Selecione uma empresa na aba 'Situação Geral' primeiro.")
        else:
            st.subheader(f"Adicionar Documento para: {employee_manager.get_company_name(selected_company)}")
            with st.form("new_company_doc_form", clear_on_submit=True):
                uploaded_file = st.file_uploader("Selecione o arquivo PDF do documento", type="pdf")
                doc_type = st.text_input("Tipo de Documento (ex: PGR, PCMSO)")
                issue_date = st.date_input("Data de Emissão")
                expiry_date = st.date_input("Data de Vencimento")
                submit_doc = st.form_submit_button("Adicionar Documento")

                if submit_doc and uploaded_file is not None:
                    with st.spinner("Processando e salvando documento..."):
                        pdf_bytes = uploaded_file.getvalue()
                        # Aqui você pode opcionalmente usar a IA para extrair dados do PDF
                        # extracted_data = process_company_doc_pdf(pdf_bytes)
                        # doc_type = extracted_data.get("tipo_documento", doc_type)
                        # ... etc ...

                        file_id = docs_manager.upload_file(
                            file_name=f"{doc_type}_{selected_company}.pdf",
                            file_bytes=pdf_bytes
                        )
                        if file_id:
                            if docs_manager.add_document(selected_company, doc_type, issue_date, expiry_date, file_id):
                                st.success("Documento da empresa adicionado com sucesso!")
                                st.rerun()
                            else:
                                st.error("Erro ao salvar as informações do documento.")
                        else:
                            st.error("Erro ao fazer upload do arquivo para o Google Drive.")

    with tab_add_aso:
        if not selected_company:
            st.info("Selecione uma empresa na aba 'Situação Geral' primeiro.")
        else:
            st.subheader("Adicionar ASO para Funcionário")
            employees_list = employee_manager.get_employees_by_company(selected_company)
            if not employees_list.empty:
                employee_options = {row['id']: row['nome'] for index, row in employees_list.iterrows()}
                selected_employee_id = st.selectbox("Selecione o Funcionário", options=list(employee_options.keys()), format_func=lambda x: employee_options[x])

                with st.form("new_aso_form", clear_on_submit=True):
                    uploaded_aso = st.file_uploader("Selecione o arquivo PDF do ASO", type="pdf")
                    submit_aso = st.form_submit_button("Adicionar ASO")

                    if submit_aso and uploaded_aso is not None and selected_employee_id:
                        with st.spinner("Processando e salvando ASO..."):
                            pdf_bytes = uploaded_aso.getvalue()
                            extracted_data = process_aso_pdf(pdf_bytes) # Função de IA para extrair dados

                            file_id = employee_manager.upload_file(
                                file_name=f"ASO_{employee_options[selected_employee_id]}.pdf",
                                file_bytes=pdf_bytes
                            )
                            if file_id:
                                if employee_manager.add_aso(
                                    employee_id=selected_employee_id,
                                    aso_type=extracted_data.get("tipo_aso", "Admissional"),
                                    aso_date=extracted_data.get("data_aso", date.today()),
                                    aptitude=extracted_data.get("aptidao", "Apto"),
                                    file_id=file_id
                                ):
                                    st.success("ASO adicionado com sucesso!")
                                    st.rerun()
                                else:
                                    st.error("Erro ao salvar as informações do ASO.")
                            else:
                                st.error("Erro ao fazer upload do arquivo para o Google Drive.")
            else:
                st.warning("Não há funcionários cadastrados para esta empresa.")

    with tab_add_treinamento:
        if not selected_company:
            st.info("Selecione uma empresa na aba 'Situação Geral' primeiro.")
        else:
            st.subheader("Adicionar Treinamento para Funcionário")
            employees_list = employee_manager.get_employees_by_company(selected_company)
            if not employees_list.empty:
                employee_options = {row['id']: row['nome'] for index, row in employees_list.iterrows()}
                selected_employee_id_training = st.selectbox("Selecione o Funcionário", options=list(employee_options.keys()), format_func=lambda x: employee_options[x], key="training_employee_selector")

                with st.form("new_training_form", clear_on_submit=True):
                    uploaded_training = st.file_uploader("Selecione o PDF do Certificado", type="pdf")
                    norma = st.text_input("Norma/Treinamento (ex: NR-35)")
                    training_date = st.date_input("Data de Realização")
                    submit_training = st.form_submit_button("Adicionar Treinamento")

                    if submit_training and uploaded_training is not None and selected_employee_id_training:
                        with st.spinner("Processando e salvando treinamento..."):
                            pdf_bytes = uploaded_training.getvalue()
                            # extracted_data = process_training_pdf(pdf_bytes) # Opcional

                            file_id = employee_manager.upload_file(
                                file_name=f"Treinamento_{norma}_{employee_options[selected_employee_id_training]}.pdf",
                                file_bytes=pdf_bytes
                            )
                            if file_id:
                                if employee_manager.add_training(
                                    employee_id=selected_employee_id_training,
                                    norm=norma,
                                    date=training_date,
                                    attachment_id=file_id
                                ):
                                    st.success("Treinamento adicionado com sucesso!")
                                    st.rerun()
                                else:
                                    st.error("Erro ao salvar as informações do treinamento.")
                            else:
                                st.error("Erro ao fazer upload do arquivo para o Google Drive.")
            else:
                st.warning("Não há funcionários cadastrados para esta empresa.")

    with tab_add_epi:
        if not selected_company:
            st.info("Selecione uma empresa na aba 'Situação Geral' primeiro.")
        else:
            st.subheader("Adicionar Ficha de EPI para Funcionário")
            employees_list = employee_manager.get_employees_by_company(selected_company)
            if not employees_list.empty:
                employee_options_epi = {row['id']: row['nome'] for index, row in employees_list.iterrows()}
                selected_employee_id_epi = st.selectbox("Selecione o Funcionário", options=list(employee_options_epi.keys()), format_func=lambda x: employee_options_epi[x], key="epi_employee_selector")

                with st.form("new_epi_form", clear_on_submit=True):
                    uploaded_epi = st.file_uploader("Selecione o PDF da Ficha de EPI", type="pdf")
                    submit_epi = st.form_submit_button("Adicionar Ficha de EPI")

                    if submit_epi and uploaded_epi is not None and selected_employee_id_epi:
                        with st.spinner("Processando e salvando Ficha de EPI..."):
                            pdf_bytes = uploaded_epi.getvalue()
                            # A IA poderia extrair os EPIs da ficha aqui
                            # extracted_data = process_epi_pdf(pdf_bytes)

                            file_id = epi_manager.upload_file(
                                file_name=f"Ficha_EPI_{employee_options_epi[selected_employee_id_epi]}.pdf",
                                file_bytes=pdf_bytes
                            )
                            if file_id:
                                # Supondo que a IA extraia uma lista de EPIs
                                # Por simplicidade, vamos adicionar um registro genérico
                                if epi_manager.add_epi_record(
                                    employee_id=selected_employee_id_epi,
                                    epi_description="Ficha de EPI",
                                    ca="N/A",
                                    delivery_date=date.today(),
                                    file_id=file_id
                                ):
                                    st.success("Ficha de EPI adicionada com sucesso!")
                                    st.rerun()
                                else:
                                    st.error("Erro ao salvar as informações da Ficha de EPI.")
                            else:
                                st.error("Erro ao fazer upload do arquivo para o Google Drive.")
            else:
                st.warning("Não há funcionários cadastrados para esta empresa.")
