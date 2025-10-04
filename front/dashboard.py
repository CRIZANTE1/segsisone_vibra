import streamlit as st
from datetime import date
import pandas as pd
from fuzzywuzzy import fuzz
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
    if company_id is None: return "Selecione..."
    try:
        row = companies_df[companies_df['id'] == str(company_id)].iloc[0]
        name, status = row.get('nome', f"ID {company_id}"), str(row.get('status', 'Ativo')).lower()
        return f"🗄️ {name} (Arquivada)" if status == 'arquivado' else f"{name} - {row.get('cnpj', 'N/A')}"
    except (IndexError, KeyError): return f"Empresa ID {company_id} (Não encontrada)"

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

def handle_delete_confirmation(docs_manager, employee_manager):
    """
    Gerencia o diálogo de confirmação de exclusão.
    Esta função é chamada no final da renderização da página.
    """
    if 'items_to_delete' in st.session_state:
        items = st.session_state.items_to_delete

        @st.dialog("Confirmar Exclusão")
        def confirm_multiple_delete():
            st.warning(f"Você tem certeza que deseja excluir permanentemente os {len(items)} registro(s) selecionado(s)?")
            
            with st.container(height=150):
                for item in items:
                    st.markdown(f"- **{item['name']}** (ID: {item['id']})")
            
            st.caption("Esta ação também removerá os arquivos associados do Google Drive e não pode ser desfeita.")
            
            col1, col2 = st.columns(2)
            if col1.button("Cancelar", use_container_width=True):
                del st.session_state.items_to_delete
                st.rerun()
            
            if col2.button(f"Sim, Excluir {len(items)} Iten(s)", type="primary", use_container_width=True):
                total_success = 0
                with st.spinner("Excluindo registros..."):
                    for item in items:
                        success = False
                        if item['type'] == 'doc_empresa':
                            success = docs_manager.delete_company_document(item['id'], item.get('file_url'))
                        elif item['type'] == 'aso':
                            success = employee_manager.delete_aso(item['id'], item.get('file_url'))
                        elif item['type'] == 'treinamento':
                            success = employee_manager.delete_training(item['id'], item.get('file_url'))
                        if success:
                            total_success += 1
                
                if total_success == len(items):
                    st.success(f"{total_success} registro(s) excluído(s) com sucesso!")
                else:
                    st.error(f"Falha ao excluir. {total_success} de {len(items)} registros foram removidos.")
                
                del st.session_state.items_to_delete
                st.rerun()

        confirm_multiple_delete()

def show_dashboard_page():
    logger.info("Iniciando a renderização da página do dashboard.")
    if not st.session_state.get('managers_initialized'):
        st.warning("Selecione uma unidade operacional para visualizar o dashboard.")
        return
        
    employee_manager = st.session_state.employee_manager
    docs_manager = st.session_state.docs_manager
    epi_manager = st.session_state.epi_manager
    matrix_manager_unidade = st.session_state.matrix_manager_unidade
    
    st.title("Dashboard de Conformidade")
    
    company_options = [None] + employee_manager.companies_df['id'].astype(str).tolist()
    selected_company = st.selectbox(
        "Selecione uma empresa para ver os detalhes:",
        options=company_options,
        format_func=lambda cid: format_company_display(cid, employee_manager.companies_df),
        key="company_selector",
        placeholder="Selecione uma empresa..."
    )

    tab_list = [
        "**Situação Geral**", "Adicionar Doc. Empresa", "Adicionar ASO", 
        "Adicionar Treinamento", "Adicionar Ficha de EPI", "⚙️ Gerenciar Registros"
    ]
    
    tab_situacao, tab_add_doc_empresa, tab_add_aso, tab_add_treinamento, tab_add_epi, tab_manage = st.tabs(tab_list)

    with tab_situacao:
        if selected_company:
            try:
                st.subheader("Documentos da Empresa")
                company_docs = docs_manager.get_docs_by_company(selected_company).copy()
                expected_doc_cols = ["tipo_documento", "data_emissao", "vencimento", "arquivo_id"]
                
                if isinstance(company_docs, pd.DataFrame) and not company_docs.empty:
                    company_docs['vencimento_dt'] = company_docs['vencimento'].dt.date
                    st.dataframe(
                        company_docs.style.apply(highlight_expired, axis=1),
                        column_config={
                            "tipo_documento": "Documento", "data_emissao": st.column_config.DateColumn("Emissão", format="DD/MM/YYYY"), 
                            "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), 
                            "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="PDF"), "vencimento_dt": None 
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
                                if pd.notna(vencimento_obj):
                                    aso_vencimento = vencimento_obj
                                    aso_status = 'Válido' if aso_vencimento.date() >= today else 'Vencido'
                                else:
                                    aso_status = 'Venc. Inválido'
                            else:
                                aso_status = 'Apenas Demissional'

                        all_trainings = employee_manager.get_all_trainings_by_employee(employee_id)
                        trainings_total, trainings_expired_count = 0, 0
                        if isinstance(all_trainings, pd.DataFrame) and not all_trainings.empty:
                            trainings_total = len(all_trainings)
                            trainings_expired_count = (all_trainings['vencimento'].dt.date < today).sum()

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
                                    column_config={"tipo_aso": "Tipo", "data_aso": st.column_config.DateColumn("Data", format="DD/MM/YYYY"), "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="PDF"), "vencimento_dt": None},
                                    column_order=["tipo_aso", "data_aso", "vencimento", "arquivo_id"],
                                    hide_index=True, use_container_width=True
                                )
                            else:
                                st.info(f"Nenhum ASO encontrado para {employee_name}.")

                            st.markdown("##### Treinamentos (Mais Recente por Norma/Módulo)")
                            if isinstance(all_trainings, pd.DataFrame) and not all_trainings.empty:
                                all_trainings['vencimento_dt'] = pd.to_datetime(all_trainings['vencimento'], errors='coerce').dt.date
                                
                                # ✅ Cria coluna combinada para exibição clara
                                def format_training_display(row):
                                    norma = str(row.get('norma', 'N/A')).strip()
                                    modulo = str(row.get('modulo', 'N/A')).strip()
                                    tipo = str(row.get('tipo_treinamento', 'N/A')).strip().title()
                                    
                                    # Se for NR-10 SEP, destaca
                                    if 'SEP' in norma.upper() or 'SEP' in modulo.upper():
                                        return f"⚡ NR-10 SEP ({tipo})"
                                    
                                    # Para normas com módulos relevantes
                                    if modulo and modulo not in ['N/A', 'nan', '', 'Nan']:
                                        # Normaliza o módulo para exibição
                                        modulo_exibicao = modulo.title()
                                        return f"{norma} - {modulo_exibicao} ({tipo})"
                                    
                                    # Para normas simples
                                    return f"{norma} ({tipo})"
                                
                                all_trainings['treinamento_completo'] = all_trainings.apply(format_training_display, axis=1)

                                st.dataframe(
                                    all_trainings.style.apply(highlight_expired, axis=1),
                                    column_config={
                                        "treinamento_completo": st.column_config.TextColumn(
                                            "Treinamento",
                                            help="Norma, módulo e tipo do treinamento",
                                            width="large"
                                        ),
                                        "data": st.column_config.DateColumn("Realização", format="DD/MM/YYYY"), 
                                        "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), 
                                        "anexo": st.column_config.LinkColumn("Anexo", display_text=" PDF"),
                                        # ✅ Oculta colunas redundantes
                                        "vencimento_dt": None,
                                        "norma": None,
                                        "modulo": None,
                                        "tipo_treinamento": None
                                    },
                                    column_order=["treinamento_completo", "data", "vencimento", "anexo"],
                                    hide_index=True, 
                                    use_container_width=True
                                )
                            else:
                                st.info(f"Nenhum treinamento encontrado para {employee_name}.")

                            st.markdown("##### Equipamentos de Proteção Individual (EPIs)")
                            all_epis = epi_manager.get_epi_by_employee(employee_id)
                            if isinstance(all_epis, pd.DataFrame) and not all_epis.empty:
                                st.dataframe(
                                    all_epis,
                                    column_config={"descricao_epi": "Equipamento", "ca_epi": "C.A.", "data_entrega": st.column_config.DateColumn("Data de Entrega", format="DD/MM/YYYY"), "arquivo_id": st.column_config.LinkColumn("Ficha", display_text="PDF")},
                                    column_order=["descricao_epi", "ca_epi", "data_entrega", "arquivo_id"],
                                    hide_index=True, use_container_width=True
                                )
                            else:
                                st.info(f"Nenhuma Ficha de EPI encontrada para {employee_name}.")

                            st.markdown("---")
                            st.markdown("##### Matriz de Conformidade de Treinamentos")
                            if not employee_cargo or employee_cargo == 'N/A':
                                st.info("Cargo não definido, impossibilitando análise de matriz.")
                            else:
                                matched_function = matrix_manager_unidade.find_closest_function(employee_cargo)
                                if not matched_function:
                                    st.success(f"O cargo '{employee_cargo}' não possui treinamentos obrigatórios na matriz da unidade.")
                                else:
                                    if matched_function.lower() != employee_cargo.lower():
                                        st.caption(f"Analisando com base na função da matriz mais próxima: **'{matched_function}'**")
                                    
                                    required_trainings = matrix_manager_unidade.get_required_trainings_for_function(matched_function)
                                    
                                    if not required_trainings:
                                        st.success(f"Nenhum treinamento obrigatório mapeado para a função '{matched_function}'.")
                                    else:
                                        # ✅ Cria lista de treinamentos realizados (norma + módulo normalizados)
                                        completed_trainings = []

                                        if isinstance(all_trainings, pd.DataFrame) and not all_trainings.empty:
                                            for _, row in all_trainings.iterrows():
                                                norma = str(row.get('norma', '')).strip().upper()
                                                modulo = str(row.get('modulo', 'N/A')).strip().title()
                                                
                                                # Normalização especial
                                                if 'NR-10' in norma:
                                                    if 'SEP' in norma or 'SEP' in modulo.upper():
                                                        completed_trainings.append('nr-10 sep')
                                                        completed_trainings.append('nr-10-sep')
                                                    else:
                                                        completed_trainings.append('nr-10')
                                                        completed_trainings.append('nr-10 básico')
                                                
                                                elif 'NR-33' in norma:
                                                    if 'SUPERVISOR' in modulo.upper():
                                                        completed_trainings.append('nr-33 supervisor')
                                                    elif 'TRABALHADOR' in modulo.upper() or 'AUTORIZADO' in modulo.upper():
                                                        completed_trainings.append('nr-33 trabalhador autorizado')
                                                    completed_trainings.append('nr-33')
                                                
                                                else:
                                                    # Adiciona variações normalizadas
                                                    completed_trainings.append(norma.lower())
                                                    
                                                    if modulo and modulo not in ['N/A', 'nan', '']:
                                                        completed_trainings.append(f"{norma} - {modulo}".lower())
                                                        completed_trainings.append(f"{norma} {modulo}".lower())
                                                        completed_trainings.append(f"{norma}-{modulo}".lower())

                                        # ✅ Verifica treinamentos faltantes
                                        missing = []
                                        for req in required_trainings:
                                            req_lower = req.lower().strip()
                                            
                                            # ✅ CORREÇÃO CRÍTICA: NR-10 Básico NÃO cobre NR-10 SEP
                                            if 'nr-10 sep' in req_lower or 'nr-10-sep' in req_lower:
                                                # Verifica especificamente por SEP
                                                has_sep = any('sep' in comp for comp in completed_trainings if 'nr-10' in comp)
                                                if not has_sep:
                                                    missing.append(req)
                                                continue
                                            
                                            # Verifica match exato ou fuzzy (score > 85)
                                            has_match = any(
                                                req_lower == comp or 
                                                req_lower in comp or 
                                                comp in req_lower or
                                                fuzz.ratio(req_lower, comp) > 85
                                                for comp in completed_trainings
                                            )
                                            
                                            if not has_match:
                                                missing.append(req)

                                        if not missing:
                                            st.success("✅ Todos os treinamentos obrigatórios foram realizados.")
                                        else:
                                            st.error(f"⚠️ **{len(missing)} Treinamento(s) Faltante(s):**")
                                            
                                            for treinamento in sorted(missing):
                                                # Destaca treinamentos especiais
                                                if 'SEP' in treinamento.upper():
                                                    st.markdown(f"- ⚡ **{treinamento}** *(Sistema Elétrico de Potência)*")
                                                elif any(x in treinamento.upper() for x in ['BÁSICO', 'INTERMEDIÁRIO', 'AVANÇADO']):
                                                    st.markdown(f"-  **{treinamento}**")
                                                else:
                                                    st.markdown(f"- {treinamento}")
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
        elif check_permission(level='editor'):
            st.subheader("Adicionar Documento da Empresa (PGR, PCMSO, etc.)")
            company_name = employee_manager.get_company_name(selected_company)
            st.info(f"Adicionando documento para: **{company_name}**")
            
            # Etapa 1: Upload e Análise com IA
            st.file_uploader(
                "Anexar Documento (PDF)",
                type=['pdf'],
                key="doc_uploader_tab",
                on_change=process_company_doc_pdf
            )
            
            # Etapa 2: Confirmação e Salvamento
            if st.session_state.get('Doc. Empresa_info_para_salvar'):
                doc_info = st.session_state['Doc. Empresa_info_para_salvar']
                if doc_info and doc_info.get('data_emissao'):
                    with st.container(border=True):
                        st.markdown("### Confirme as Informações Extraídas")
                        st.write(f"**Tipo:** {doc_info['tipo_documento']}")
                        st.write(f"**Data de Emissão:** {doc_info['data_emissao'].strftime('%d/%m/%Y')}")
                        st.success(f"**Vencimento:** {doc_info['vencimento'].strftime('%d/%m/%Y')}")
                        
                        display_audit_results(doc_info.get('audit_result'))
                        
                        if st.button("Confirmar e Salvar Documento", type="primary", key="save_company_doc"):
                            with st.spinner("Salvando..."):
                                anexo = st.session_state['Doc. Empresa_anexo_para_salvar']
                                arquivo_hash = st.session_state.get('Doc. Empresa_hash_para_salvar')
                                nome_arquivo = f"{doc_info['tipo_documento']}_{company_name}_{doc_info['data_emissao'].strftime('%Y%m%d')}.pdf"
                                
                                arquivo_id = employee_manager.upload_documento_e_obter_link(anexo, nome_arquivo)
                                
                                if arquivo_id:
                                    doc_id = docs_manager.add_company_document(
                                        selected_company, doc_info['tipo_documento'], 
                                        doc_info['data_emissao'], doc_info['vencimento'], arquivo_id, arquivo_hash
                                    )
                                    if doc_id:
                                        st.success("Documento da empresa salvo com sucesso!")
                                        
                                        # ✅ CORREÇÃO: Criar plano de ação APÓS salvamento bem-sucedido
                                        audit_result = doc_info.get('audit_result', {})
                                        if audit_result and 'não conforme' in audit_result.get('summary', '').lower():
                                            action_plan_manager = st.session_state.action_plan_manager
                                            non_conformities = [
                                                item for item in audit_result.get('details', []) 
                                                if item.get('status', '').lower() == 'não conforme'
                                                and 'resumo executivo' not in item.get('item_verificacao', '').lower()
                                            ]
                                            
                                            if non_conformities:
                                                st.info(f"Registrando {len(non_conformities)} não conformidade(s) no Plano de Ação...")
                                                audit_run_id = f"audit_doc_{doc_id}"
                                                
                                                for item_details in non_conformities:
                                                    action_plan_manager.add_action_item(
                                                        audit_run_id=audit_run_id,
                                                        company_id=selected_company,
                                                        doc_id=doc_id,
                                                        item_details=item_details,
                                                        employee_id=None
                                                    )
                                                st.success("Itens adicionados ao Plano de Ação!")

                                        # Limpa o estado
                                        for key in ['Doc. Empresa_info_para_salvar', 'Doc. Empresa_anexo_para_salvar', 'Doc. Empresa_hash_para_salvar']:
                                            if key in st.session_state: 
                                                del st.session_state[key]
                                        
                                        st.rerun()
                                    else:
                                        st.error("Falha ao salvar os dados na planilha.")
                                else:
                                    st.error("Falha ao fazer o upload do arquivo para o Google Drive.")

    with tab_add_aso:
        if not selected_company:
            st.info("Selecione uma empresa na aba 'Situação Geral' primeiro.")
        elif check_permission(level='editor'):
            st.subheader("Adicionar Novo ASO")
            current_employees = employee_manager.get_employees_by_company(selected_company)
            if not current_employees.empty:
                st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="aso_employee_add")
                
                # Etapa 1: Upload e Análise
                st.file_uploader("Anexar ASO (PDF)", type=['pdf'], key="aso_uploader_tab", on_change=process_aso_pdf)
                
                # Etapa 2: Confirmação e Salvamento
                if st.session_state.get('ASO_info_para_salvar'):
                    aso_info = st.session_state.ASO_info_para_salvar
                    if aso_info and aso_info.get('data_aso'):
                        with st.container(border=True):
                            st.markdown("### Confirme as Informações Extraídas")
                            st.write(f"**Data:** {aso_info['data_aso'].strftime('%d/%m/%Y')}")
                            st.write(f"**Tipo:** {aso_info.get('tipo_aso', 'N/A')}")
                            if aso_info.get('vencimento'):
                                st.success(f"**Vencimento:** {aso_info['vencimento'].strftime('%d/%m/%Y')}")
                            else:
                                st.info("**Vencimento:** N/A (Ex: Demissional)")
                            
                            display_audit_results(aso_info.get('audit_result'))
                            
                            if st.button("Confirmar e Salvar ASO", type="primary", key="save_aso"):
                                with st.spinner("Salvando..."):
                                    anexo = st.session_state.ASO_anexo_para_salvar
                                    arquivo_hash = st.session_state.get('ASO_hash_para_salvar')
                                    emp_id = st.session_state.ASO_funcionario_para_salvar
                                    emp_name = employee_manager.get_employee_name(emp_id)
                                    nome_arquivo = f"ASO_{emp_name}_{aso_info['data_aso'].strftime('%Y%m%d')}.pdf"
                                    
                                    arquivo_id = employee_manager.upload_documento_e_obter_link(anexo, nome_arquivo)
                                    
                                    if arquivo_id:
                                        aso_data = {**aso_info, 'funcionario_id': emp_id, 'arquivo_id': arquivo_id, 'arquivo_hash': arquivo_hash}
                                        aso_id = employee_manager.add_aso(aso_data)
                                        if aso_id:
                                            st.success("ASO salvo com sucesso!")

                                            # ✅ CORREÇÃO: Criar plano de ação APÓS salvamento bem-sucedido
                                            audit_result = aso_info.get('audit_result', {})
                                            if audit_result and 'não conforme' in audit_result.get('summary', '').lower():
                                                action_plan_manager = st.session_state.action_plan_manager
                                                non_conformities = [
                                                    item for item in audit_result.get('details', [])
                                                    if item.get('status', '').lower() == 'não conforme'
                                                    and 'resumo executivo' not in item.get('item_verificacao', '').lower()
                                                ]

                                                if non_conformities:
                                                    st.info(f"Registrando {len(non_conformities)} não conformidade(s) no Plano de Ação...")
                                                    audit_run_id = f"audit_aso_{aso_id}"
                                                    
                                                    for item_details in non_conformities:
                                                        action_plan_manager.add_action_item(
                                                            audit_run_id=audit_run_id,
                                                            company_id=selected_company,
                                                            doc_id=aso_id,
                                                            item_details=item_details,
                                                            employee_id=emp_id
                                                        )
                                                    st.success("Itens adicionados ao Plano de Ação!")

                                            # Limpa o estado
                                            for key in ['ASO_info_para_salvar', 'ASO_anexo_para_salvar', 'ASO_funcionario_para_salvar', 'ASO_hash_para_salvar']:
                                                if key in st.session_state: 
                                                    del st.session_state[key]
                                            st.rerun()
            else:
                st.warning("Cadastre funcionários nesta empresa primeiro.")

    with tab_add_treinamento:
        if not selected_company:
            st.info("Selecione uma empresa na aba 'Situação Geral' primeiro.")
        elif check_permission(level='editor'):
            st.subheader("Adicionar Novo Treinamento")
            mostrar_info_normas()
            current_employees = employee_manager.get_employees_by_company(selected_company)
            if not current_employees.empty:
                st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="training_employee_add")
                
                # Etapa 1: Upload e Análise
                st.file_uploader("Anexar Certificado (PDF)", type=['pdf'], key="training_uploader_tab", on_change=process_training_pdf)
                
                # Etapa 2: Confirmação e Salvamento
                if st.session_state.get('Treinamento_info_para_salvar'):
                    training_info = st.session_state['Treinamento_info_para_salvar']
                    if training_info and training_info.get('data'):
                        with st.container(border=True):
                            st.markdown("### Confirme as Informações Extraídas")
                            data, norma, modulo, tipo, ch = training_info.get('data'), training_info.get('norma'), training_info.get('modulo'), training_info.get('tipo_treinamento'), training_info.get('carga_horaria', 0)
                            vencimento = employee_manager.calcular_vencimento_treinamento(data, norma, modulo, tipo)
                            
                            st.write(f"**Data:** {data.strftime('%d/%m/%Y')}")
                            st.write(f"**Norma:** {norma}")
                            if vencimento:
                                st.success(f"**Vencimento:** {vencimento.strftime('%d/%m/%Y')}")
                            else:
                                st.error("Vencimento não pôde ser calculado. Verifique as regras para esta norma.")
                            
                            display_audit_results(training_info.get('audit_result'))
                            
                            if st.button("Confirmar e Salvar Treinamento", type="primary", key="save_training", disabled=(vencimento is None)):
                                with st.spinner("Salvando..."):
                                    anexo = st.session_state.Treinamento_anexo_para_salvar
                                    arquivo_hash = st.session_state.get('Treinamento_hash_para_salvar')
                                    emp_id = st.session_state.Treinamento_funcionario_para_salvar
                                    emp_name = employee_manager.get_employee_name(emp_id)
                                    nome_arquivo = f"TRAINING_{emp_name}_{norma}_{data.strftime('%Y%m%d')}.pdf"
                                    
                                    arquivo_id = employee_manager.upload_documento_e_obter_link(anexo, nome_arquivo)
                                    
                                    if arquivo_id:
                                        training_data = {**training_info, 'funcionario_id': emp_id, 'vencimento': vencimento, 'anexo': arquivo_id, 'arquivo_hash': arquivo_hash}
                                        training_id = employee_manager.add_training(training_data)
                                        if training_id:
                                            st.success("Treinamento salvo com sucesso!")

                                            # ✅ CORREÇÃO: Criar plano de ação APÓS salvamento bem-sucedido
                                            audit_result = training_info.get('audit_result', {})
                                            if audit_result and 'não conforme' in audit_result.get('summary', '').lower():
                                                action_plan_manager = st.session_state.action_plan_manager
                                                non_conformities = [
                                                    item for item in audit_result.get('details', [])
                                                    if item.get('status', '').lower() == 'não conforme'
                                                    and 'resumo executivo' not in item.get('item_verificacao', '').lower()
                                                ]

                                                if non_conformities:
                                                    st.info(f"Registrando {len(non_conformities)} não conformidade(s) no Plano de Ação...")
                                                    audit_run_id = f"audit_trn_{training_id}"

                                                    for item_details in non_conformities:
                                                        action_plan_manager.add_action_item(
                                                            audit_run_id=audit_run_id,
                                                            company_id=selected_company,
                                                            doc_id=training_id,
                                                            item_details=item_details,
                                                            employee_id=emp_id
                                                        )
                                                    st.success("Itens adicionados ao Plano de Ação!")

                                            # Limpa o estado
                                            for key in ['Treinamento_info_para_salvar', 'Treinamento_anexo_para_salvar', 'Treinamento_funcionario_para_salvar', 'Treinamento_hash_para_salvar']:
                                                if key in st.session_state: 
                                                    del st.session_state[key]
                                            st.rerun()
            else:
                st.warning("Cadastre funcionários nesta empresa primeiro.")

    with tab_add_epi:
        if not selected_company:
            st.info("Selecione uma empresa na aba 'Situação Geral' primeiro.")
        elif check_permission(level='editor'):
            st.subheader("Adicionar Nova Ficha de EPI")
            current_employees = employee_manager.get_employees_by_company(selected_company)
            if not current_employees.empty:
                st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="epi_employee_add")
                
                # Etapa 1: Upload e Análise
                st.file_uploader("Anexar Ficha de EPI (PDF)", type=['pdf'], key="epi_uploader_tab", on_change=process_epi_pdf)
                
                # Etapa 2: Confirmação e Salvamento
                if st.session_state.get('epi_info_para_salvar'):
                    epi_info = st.session_state.epi_info_para_salvar
                    if epi_info and epi_info.get('itens_epi'):
                        with st.container(border=True):
                            st.markdown("### Confirme as Informações Extraídas")
                            nome_extraido = epi_info.get('nome_funcionario', 'N/A')
                            emp_id = st.session_state.epi_funcionario_para_salvar
                            nome_selecionado = employee_manager.get_employee_name(emp_id)
                            
                            st.write(f"**Funcionário no PDF:** {nome_extraido}")
                            st.write(f"**Funcionário Selecionado:** {nome_selecionado}")
                            if nome_extraido.lower() not in nome_selecionado.lower():
                                st.warning("Atenção: O nome do funcionário não corresponde ao selecionado.")
                            
                            st.markdown("**Itens de EPI encontrados:**")
                            st.dataframe(pd.DataFrame(epi_info['itens_epi']), hide_index=True, use_container_width=True)
                            
                            if st.button("Confirmar e Salvar Itens da Ficha de EPI", type="primary", key="save_epi"):
                                with st.spinner("Salvando..."):
                                    anexo = st.session_state.epi_anexo_para_salvar
                                    arquivo_hash = st.session_state.get('epi_hash_para_salvar')
                                    nome_arquivo = f"EPI_{nome_selecionado}_{date.today().strftime('%Y-%m-%d')}.pdf"
                                    
                                    arquivo_id = employee_manager.upload_documento_e_obter_link(anexo, nome_arquivo)
                                    
                                    if arquivo_id:
                                        saved_ids = epi_manager.add_epi_records(emp_id, arquivo_id, epi_info['itens_epi'], arquivo_hash)
                                        if saved_ids:
                                            st.success(f"{len(saved_ids)} item(ns) de EPI salvos com sucesso!")
                                            
                                            # Limpa o estado
                                            for key in ['epi_info_para_salvar', 'epi_anexo_para_salvar', 'epi_funcionario_para_salvar', 'epi_hash_para_salvar']:
                                                if key in st.session_state: 
                                                    del st.session_state[key]
                                            st.rerun()
            else:
                st.warning("Cadastre funcionários nesta empresa primeiro.")

    with tab_manage:
        st.header("Gerenciar Registros da Empresa Selecionada")
        if not selected_company:
            st.info("Selecione uma empresa na aba 'Situação Geral' para gerenciar seus registros.")
        else:
            company_name = employee_manager.get_company_name(selected_company)
            st.subheader(f"Exclusão de registros para: **{company_name}**")
            st.warning("Atenção: A exclusão é permanente e removerá o arquivo do Google Drive.")

            # --- GERENCIAMENTO DE DOCUMENTOS DA EMPRESA ---
            with st.container(border=True):
                st.markdown("#### Excluir Documentos da Empresa")
                company_docs = docs_manager.get_docs_by_company(selected_company)
                if not company_docs.empty:
                    docs_to_delete = st.multiselect(
                        "Selecione os documentos para excluir:",
                        options=company_docs['id'],
                        format_func=lambda doc_id: f"{company_docs[company_docs['id'] == doc_id].iloc[0]['tipo_documento']} (ID: {doc_id})",
                        key="delete_doc_select"
                    )
                    if st.button("Adicionar à Lista de Exclusão", key="delete_doc_btn"):
                        if docs_to_delete:
                            # ✅ Inicializa a lista se não existir
                            if 'items_to_delete' not in st.session_state:
                                st.session_state.items_to_delete = []
                            
                            for doc_id in docs_to_delete:
                                row = company_docs[company_docs['id'] == doc_id].iloc[0]
                                item_data = {
                                    "type": "doc_empresa", 
                                    "id": doc_id, 
                                    "file_url": row.get('arquivo_id'),
                                    "name": f"Documento {row.get('tipo_documento')}"
                                }
                                # ✅ Evita duplicatas
                                if item_data not in st.session_state.items_to_delete:
                                    st.session_state.items_to_delete.append(item_data)
                            st.success(f"{len(docs_to_delete)} documento(s) adicionado(s) à lista de exclusão.")
                else:
                    st.caption("Nenhum documento da empresa para gerenciar.")

            # --- GERENCIAMENTO DE DOCUMENTOS DE FUNCIONÁRIOS ---
            employees = employee_manager.get_employees_by_company(selected_company)
            if not employees.empty:
                selected_employee_id = st.selectbox(
                    "Selecione um funcionário para gerenciar seus documentos:",
                    options=employees['id'],
                    format_func=employee_manager.get_employee_name,
                    index=None,
                    placeholder="Escolha um funcionário..."
                )

                if selected_employee_id:
                    employee_name = employee_manager.get_employee_name(selected_employee_id)
                    
                    with st.container(border=True):
                        st.markdown(f"#### Excluir ASOs de **{employee_name}**")
                        latest_asos = employee_manager.get_latest_aso_by_employee(selected_employee_id)
                        if not latest_asos.empty:
                            asos_to_delete = st.multiselect(
                                "Selecione os ASOs para excluir:",
                                options=latest_asos['id'],
                                format_func=lambda aso_id: f"{latest_asos.loc[latest_asos['id'] == aso_id, 'tipo_aso'].iloc[0]} de {latest_asos.loc[latest_asos['id'] == aso_id, 'data_aso'].iloc[0].strftime('%d/%m/%Y') if pd.notna(latest_asos.loc[latest_asos['id'] == aso_id, 'data_aso'].iloc[0]) else 'Data Inválida'} (ID: {aso_id})",
                                key=f"delete_aso_select_{selected_employee_id}"
                            )
                            if st.button("Adicionar à Lista de Exclusão", key=f"delete_aso_btn_{selected_employee_id}"):
                                if asos_to_delete:
                                    # ✅ Inicializa a lista se não existir
                                    if 'items_to_delete' not in st.session_state:
                                        st.session_state.items_to_delete = []
                                    
                                    for aso_id in asos_to_delete:
                                        row = latest_asos[latest_asos['id'] == aso_id].iloc[0]
                                        item_data = {
                                            "type": "aso", 
                                            "id": aso_id, 
                                            "file_url": row.get('arquivo_id'),
                                            "name": f"ASO {row.get('tipo_aso')} de {employee_name}"
                                        }
                                        # ✅ Evita duplicatas
                                        if item_data not in st.session_state.items_to_delete:
                                            st.session_state.items_to_delete.append(item_data)
                                    st.success(f"{len(asos_to_delete)} ASO(s) adicionado(s) à lista de exclusão.")
                        else:
                            st.caption("Nenhum ASO para gerenciar.")

                    with st.container(border=True):
                        st.markdown(f"#### Excluir Treinamentos de **{employee_name}**")
                        all_trainings = employee_manager.get_all_trainings_by_employee(selected_employee_id)
                        if not all_trainings.empty:
                            trainings_to_delete = st.multiselect(
                                "Selecione os treinamentos para excluir:",
                                options=all_trainings['id'],
                                format_func=lambda tr_id: f"{all_trainings.loc[all_trainings['id'] == tr_id, 'norma'].iloc[0]} de {all_trainings.loc[all_trainings['id'] == tr_id, 'data'].iloc[0].strftime('%d/%m/%Y') if pd.notna(all_trainings.loc[all_trainings['id'] == tr_id, 'data'].iloc[0]) else 'Data Inválida'} (ID: {tr_id})",
                                key=f"delete_tr_select_{selected_employee_id}"
                            )
                            if st.button("Adicionar à Lista de Exclusão", key=f"delete_tr_btn_{selected_employee_id}"):
                                if trainings_to_delete:
                                    # ✅ Inicializa a lista se não existir
                                    if 'items_to_delete' not in st.session_state:
                                        st.session_state.items_to_delete = []

                                    for tr_id in trainings_to_delete:
                                        row = all_trainings[all_trainings['id'] == tr_id].iloc[0]
                                        item_data = {
                                            "type": "treinamento", 
                                            "id": tr_id, 
                                            "file_url": row.get('anexo'),
                                            "name": f"Treinamento de {row.get('norma')} de {employee_name}"
                                        }
                                        # ✅ Evita duplicatas
                                        if item_data not in st.session_state.items_to_delete:
                                            st.session_state.items_to_delete.append(item_data)
                                    st.success(f"{len(trainings_to_delete)} treinamento(s) adicionado(s) à lista de exclusão.")
                        else:
                            st.caption("Nenhum treinamento para gerenciar.")
            else:
                st.caption("Nenhum funcionário cadastrado para esta empresa.")

            # --- Exibe a lista de exclusão e o botão final para confirmar ---
            if st.session_state.get('items_to_delete'):
                st.markdown("---")
                st.subheader("Itens na Lista de Exclusão")
                items_to_display = st.session_state.items_to_delete
                for item in items_to_display:
                    st.markdown(f"- **{item['name']}** (ID: {item['id']})")
                
                if st.button("Confirmar Exclusão de Todos os Itens da Lista", type="primary", use_container_width=True):
                    # O diálogo de confirmação será acionado pelo 'items_to_delete' na sessão
                    st.rerun()
    
    # ✅ Chama o handler de diálogo no final da renderização
    handle_delete_confirmation(docs_manager, employee_manager)
