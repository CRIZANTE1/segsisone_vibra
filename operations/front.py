import streamlit as st
from datetime import datetime, date
import pandas as pd
from fuzzywuzzy import fuzz
import re

from operations.employee import EmployeeManager
from operations.company_docs import CompanyDocsManager
from operations.epi import EPIManager
from analysis.nr_analyzer import NRAnalyzer 

from gdrive.gdrive_upload import GoogleDriveUploader
from auth.auth_utils import check_permission, is_user_logged_in 
from operations.matrix_manager import MatrixManager
from ui.ui_helpers import (
    mostrar_info_normas,
    highlight_expired,
    process_aso_pdf,
    process_training_pdf,
    process_company_doc_pdf,
    process_epi_pdf
)


def format_company_display(company_id, companies_df):
    """
    Formata o nome da empresa para exibição no selectbox, incluindo
    o status se a empresa estiver arquivada.
    """
    try:
        # Encontra a linha da empresa pelo ID
        company_row = companies_df[companies_df['id'] == str(company_id)].iloc[0]
        name = company_row['nome']
        status = company_row.get('status', 'Ativo') # Assume 'Ativo' se a coluna não existir
        
        # Adiciona um marcador visual e texto se estiver arquivada
        if str(status).lower() == 'arquivado':
            return f"🗄️ {name} (Arquivada)"
        else:
            # Mantém o formato original para empresas ativas
            cnpj = company_row.get('cnpj', 'CNPJ não informado')
            return f"{name} - {cnpj}"
            
    except (IndexError, KeyError):
        # Fallback caso o ID não seja encontrado
        return f"Empresa ID {company_id} não encontrada"


def display_audit_results(audit_result):
    """Função helper para exibir os resultados da auditoria de forma consistente."""
    if not audit_result: return

    summary = audit_result.get("summary", "Indefinido")
    details = audit_result.get("details", [])

    st.markdown("---")
    st.markdown("##### 🔍 Resultado da Auditoria Rápida")

    if summary.lower() == 'conforme':
        st.success(f"**Parecer da IA:** {summary}")
    elif summary.lower() == 'não conforme':
        st.error(f"**Parecer da IA:** {summary}")
        with st.expander("Ver detalhes da não conformidade", expanded=True):
            for item in details:
                if item.get("status", "").lower() == "não conforme":
                    st.markdown(
                        f"- **Item:** {item.get('item_verificacao')}\n"
                        f"- **Observação:** {item.get('observacao')}"
                    )
    else:
        st.info(f"**Parecer da IA:** {summary}")

    
def front_page():
    
    if 'employee_manager' not in st.session_state:
        st.session_state.employee_manager = EmployeeManager()
    if 'docs_manager' not in st.session_state:
        st.session_state.docs_manager = CompanyDocsManager()
    if 'epi_manager' not in st.session_state:
        st.session_state.epi_manager = EPIManager()
    if 'nr_analyzer' not in st.session_state:
        st.session_state.nr_analyzer = NRAnalyzer()
    if 'gdrive_uploader' not in st.session_state:
        st.session_state.gdrive_uploader = GoogleDriveUploader()
    if 'matrix_manager' not in st.session_state: 
        st.session_state.matrix_manager = MatrixManager()    

    employee_manager = st.session_state.employee_manager
    docs_manager = st.session_state.docs_manager
    epi_manager = st.session_state.epi_manager
    nr_analyzer = st.session_state.nr_analyzer
    gdrive_uploader = st.session_state.gdrive_uploader
    matrix_manager = st.session_state.matrix_manager
    
    
    st.title("Gestão de Documentação Inteligente")
    
    selected_company = None
    if not employee_manager.companies_df.empty:
        # Garante que os dados estejam ordenados para uma melhor experiência
        companies_to_display = employee_manager.companies_df.sort_values(by=['status', 'nome'], ascending=[True, True])
        
        selected_company = st.selectbox(
            "Selecione uma empresa para ver os detalhes:",
            options=companies_to_display['id'].tolist(),
            # A format_func agora chama nossa nova função helper
            format_func=lambda company_id: format_company_display(company_id, companies_to_display),
            index=None,
            placeholder="Selecione uma empresa...",
            key="company_select" # Mantém a chave, se você a usa em outro lugar
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
                    st.dataframe(company_docs_reordered.style.apply(highlight_expired, axis=1), column_config={"tipo_documento": "Documento", "data_emissao": st.column_config.DateColumn("Emissão", format="DD/MM/YYYY"), "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF"),}, hide_index=True, use_container_width=True)
                else: st.info("Nenhum documento (ex: PGR, PCMSO) cadastrado para esta empresa.")
                
                st.markdown("---")
                st.subheader("Funcionários")
                employees = employee_manager.get_employees_by_company(selected_company)
                if not employees.empty:
                    for index, employee in employees.iterrows():
                        employee_id = employee['id']
                        employee_name = employee['nome']
                        employee_role = employee['cargo']
                        today = date.today()
                    
                        aso_status = 'Não encontrado'
                        aso_vencimento = None
                        latest_asos_by_type = employee_manager.get_latest_aso_by_employee(employee_id)
                    
                        if not latest_asos_by_type.empty:
                            aptitude_asos = latest_asos_by_type[
                                ~latest_asos_by_type['tipo_aso'].str.lower().isin(['demissional'])
                            ].copy()
                            
                            # 3. Desses, pega o mais recente de todos para determinar o status
                            if not aptitude_asos.empty:
                                # Ordena pela data do ASO e pega a primeira linha (a mais recente)
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
                        
                        trainings_total = 0
                        trainings_expired_count = 0
                        
                        if not all_trainings.empty:
                            trainings_total = len(all_trainings)
                            expired_mask = all_trainings['vencimento'] < today
                            trainings_expired_count = expired_mask.sum()
                    
                        if aso_status == 'Vencido' or trainings_expired_count > 0:
                            overall_status = 'Pendente'
                            status_icon = "⚠️"
                        else:
                            overall_status = 'Em Dia'
                            status_icon = "✅"
                    
                        expander_title = f"{status_icon} **{employee_name}** - *{employee_role}*"
    
                        with st.expander(expander_title):
                            st.markdown("##### Resumo de Status")
                            col1, col2, col3 = st.columns(3); num_pendencias = trainings_expired_count + (1 if aso_status == 'Vencido' else 0)
                            col1.metric("Status Geral", overall_status, f"{num_pendencias} pendência(s)" if num_pendencias > 0 else "Nenhuma pendência", delta_color="inverse" if overall_status != 'Em Dia' else "off")
                            col2.metric("Status do ASO", aso_status, help=f"Vencimento: {aso_vencimento.strftime('%d/%m/%Y') if aso_vencimento else 'N/A'}")
                            col3.metric("Treinamentos Vencidos", f"{trainings_expired_count} de {trainings_total}")
                            st.markdown("---")
                            st.markdown("##### ASO Mais Recente")
                            if not latest_asos_by_type.empty:
                                aso_display_cols = ["tipo_aso", "data_aso", "vencimento", "cargo", "riscos", "arquivo_id"]
                                for col in aso_display_cols:
                                    if col not in latest_asos_by_type.columns:
                                        latest_asos_by_type[col] = "N/A"
                                aso_reordered_df = latest_asos_by_type[aso_display_cols]
                                st.dataframe(
                                    aso_reordered_df.style.apply(highlight_expired, axis=1),
                                    column_config={"tipo_aso": "Tipo", "data_aso": st.column_config.DateColumn("Data", format="DD/MM/YYYY"), "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), "cargo": "Cargo (ASO)", "riscos": "Riscos", "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF")},
                                    hide_index=True, use_container_width=True
                                )
                            else:
                                st.info("Nenhum ASO encontrado.")
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
                    #---------------------------------------------------------------------------------------------------------------------------------------
                            st.markdown("---")
                            st.markdown("##### Matriz de Conformidade de Treinamentos")
                            
                            employee_cargo = employee.get('cargo', '').strip()
                            if not employee_cargo:
                                st.info("O cargo deste funcionário não está cadastrado, impossibilitando a análise de matriz.")
                            else:
                                # 1. Encontra a função correspondente na matriz
                                matched_function_name = matrix_manager.find_closest_function(employee_cargo)
                                
                                if not matched_function_name:
                                    st.info(f"✅ O cargo '{employee_cargo}' não corresponde a nenhuma função com treinamentos obrigatórios na matriz.")
                                else:
                                    if employee_cargo.lower() != matched_function_name.lower():
                                        st.caption(f"Analisando com base na função da matriz mais próxima: **'{matched_function_name}'**")
                            
                                    # 2. Busca os treinamentos requeridos para a função encontrada
                                    required_trainings = matrix_manager.get_required_trainings_for_function(matched_function_name)
                                    
                                    if not required_trainings:
                                        st.success(f"✅ Nenhum treinamento obrigatório mapeado para a função '{matched_function_name}'.")
                                    else:
                                        current_trainings_norms = []
                                        if not all_trainings.empty and 'norma' in all_trainings.columns:
                                            current_trainings_norms = all_trainings['norma'].dropna().tolist()
                                        
                                        missing_trainings = []
                                        status_list = []
                                        SIMILARITY_THRESHOLD = 90 # Limiar alto para evitar falsos positivos
                            
                                        # --- LÓGICA DE COMPARAÇÃO HÍBRIDA ---
                                        for required in required_trainings:
                                            found_match = False
                                            # Remove espaços e converte para minúsculas para comparação
                                            required_clean = re.sub(r'\s+', ' ', required).lower()
                            
                                            for current in current_trainings_norms:
                                                current_clean = re.sub(r'\s+', ' ', str(current)).lower()
                                                
                                                # Regra 1: Uma string contém a outra (lida com "NR-10" vs "NR-10 Básico")
                                                if required_clean in current_clean or current_clean in required_clean:
                                                    found_match = True
                                                    break
                                                
                                                # Regra 2 (Fallback): Usa fuzzy matching para casos com pequenas variações
                                                # Ex: "NR20 Inflamáveis" vs "NR-20 Inflamáveis e Combustíveis"
                                                if fuzz.token_sort_ratio(required_clean, current_clean) >= SIMILARITY_THRESHOLD:
                                                    found_match = True
                                                    break
                                            
                                            # Monta a lista de status
                                            if found_match:
                                                status_list.append({"Treinamento Obrigatório": required, "Status": "✅ Realizado"})
                                            else:
                                                status_list.append({"Treinamento Obrigatório": required, "Status": "🔴 Faltante"})
                                                missing_trainings.append(required)
                                        
                                        # Exibe os resultados
                                        if not missing_trainings:
                                            st.success("✅ Todos os treinamentos obrigatórios para esta função foram realizados.")
                                        else:
                                            st.error(f"⚠️ **Treinamentos Obrigatórios Faltantes:** {', '.join(sorted(missing_trainings))}")
                                            
                                        if status_list:
                                            st.dataframe(pd.DataFrame(status_list), use_container_width=True, hide_index=True)
     #-------------------------------------------------------------------------------------------------------------------------------------------        
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
            if check_permission(level='editor'):
                st.subheader("Adicionar Documento (PGR, PCMSO, etc.)")
                company_name = employee_manager.get_company_name(selected_company)
                st.info(f"Adicionando documento para a empresa: **{company_name}**")
                st.file_uploader("Anexar Documento (PDF)", type=['pdf'], key="doc_uploader_tab", on_change=process_company_doc_pdf)
                
                if st.session_state.get('Doc. Empresa_info_para_salvar'):
                    doc_info = st.session_state['Doc. Empresa_info_para_salvar']
                    audit_result = doc_info.get('audit_result')

                    if doc_info and doc_info.get('data_emissao'):
                        with st.container(border=True):
                            st.markdown("### Confirme as Informações Extraídas")
                            st.write(f"**Tipo Identificado:** {doc_info['tipo_documento']}")
                            st.write(f"**Data de Emissão/Vigência:** {doc_info['data_emissao'].strftime('%d/%m/%Y')}")
                            st.success(f"**Vencimento Calculado:** {doc_info['vencimento'].strftime('%d/%m/%Y')}")
                            
                            display_audit_results(audit_result)

                            if st.button("Confirmar e Salvar Documento", type="primary"):
                                with st.spinner("Salvando documento e processando auditoria..."):
                                    anexo_doc = st.session_state['Doc. Empresa_anexo_para_salvar']
                                    arquivo_id = gdrive_uploader.upload_file(anexo_doc, f"{doc_info['tipo_documento']}_{company_name}_{doc_info['data_emissao'].strftime('%Y%m%d')}")
                                    if arquivo_id:
                                        doc_id = docs_manager.add_company_document(empresa_id=selected_company, tipo_documento=doc_info['tipo_documento'], data_emissao=doc_info['data_emissao'], vencimento=doc_info['vencimento'], arquivo_id=arquivo_id)
                                        if doc_id:
                                            if audit_result and audit_result.get("summary", "").lower() == 'não conforme':
                                                created_count = nr_analyzer.create_action_plan_from_audit(audit_result, selected_company, doc_id)
                                                st.success(f"Documento salvo! {created_count} item(ns) de ação foram criados.")
                                            else:
                                                st.success("Documento da empresa salvo com sucesso!")
                                            
                                            for key in ['Doc. Empresa_info_para_salvar', 'Doc. Empresa_anexo_para_salvar']:
                                                if key in st.session_state: del st.session_state[key]
                                            st.rerun()

    with tab_add_aso:
        if selected_company:
            if check_permission(level='editor'):
                st.subheader("Adicionar Novo ASO")
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="aso_employee_add")
                    st.file_uploader("Anexar ASO (PDF)", type=['pdf'], key="aso_uploader_tab", on_change=process_aso_pdf)
                    
                    if st.session_state.get('ASO_info_para_salvar'):
                        aso_info = st.session_state['ASO_info_para_salvar']
                        audit_result = aso_info.get('audit_result')
    
                        if aso_info and aso_info.get('data_aso'):
                            with st.container(border=True):
                                st.markdown("### Confirme as Informações Extraídas")
                                st.write(f"**Data:** {aso_info['data_aso'].strftime('%d/%m/%Y')}")
                                st.write(f"**Tipo de ASO Identificado:** {aso_info.get('tipo_aso', 'N/A')}")
                                vencimento_aso = aso_info.get('vencimento')
                                if vencimento_aso: st.success(f"**Vencimento:** {vencimento_aso.strftime('%d/%m/%Y')}")
                                else: st.info("**Vencimento:** N/A (Ex: Demissional)")
    
                                display_audit_results(audit_result)
    
                                if st.button("Confirmar e Salvar ASO", type="primary"):
                                    with st.spinner("Salvando ASO e processando auditoria..."):
                                        anexo_aso = st.session_state.ASO_anexo_para_salvar
                                        selected_employee_aso = st.session_state.ASO_funcionario_para_salvar
                                        employee_name = employee_manager.get_employee_name(selected_employee_aso)
                                        arquivo_id = gdrive_uploader.upload_file(anexo_aso, f"ASO_{employee_name}_{aso_info['data_aso'].strftime('%Y%m%d')}")
                                        
                                        if arquivo_id:
                                            aso_data_to_save = aso_info.copy()
                                            aso_data_to_save.pop('type', None)
                                            aso_data_to_save.pop('audit_result', None)
                                            
                                            aso_data_to_save['funcionario_id'] = selected_employee_aso
                                            aso_data_to_save['arquivo_id'] = arquivo_id
    
                                            aso_id = employee_manager.add_aso(aso_data_to_save)
    
                                            if aso_id:
                                                if audit_result and "não conforme" in audit_result.get("summary", "").lower():
                                                    created_count = nr_analyzer.create_action_plan_from_audit(audit_result, selected_company, aso_id)
                                                    st.success(f"ASO salvo! {created_count} item(ns) de ação foram criados.")
                                                else:
                                                    st.success(f"ASO adicionado com sucesso! ID: {aso_id}")
                                                
                                                # Limpa o estado da sessão para resetar a UI
                                                for key in ['ASO_info_para_salvar', 'ASO_anexo_para_salvar', 'ASO_funcionario_para_salvar']:
                                                    if key in st.session_state: del st.session_state[key]
                                                st.rerun()
                                            else:
                                                st.error("Falha ao salvar os dados do ASO na planilha.")
                                        else:
                                            st.error("Falha ao fazer o upload do anexo para o Google Drive.")
                else:
                    st.warning("Nenhum funcionário cadastrado. Por favor, adicione funcionários na página de Administração.")
            else:
                st.error("Você não tem permissão para realizar esta ação.")
        else:
            st.info("Selecione uma empresa na primeira aba para adicionar um ASO.")


    with tab_add_treinamento:
        if selected_company:
            if check_permission(level='editor'):
                st.subheader("Adicionar Novo Treinamento")
                mostrar_info_normas()
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    st.selectbox(
                        "Funcionário",
                        current_employees['id'].tolist(),
                        format_func=employee_manager.get_employee_name,
                        key="training_employee_add"
                    )
                    st.file_uploader(
                        "Anexar Certificado (PDF)",
                        type=['pdf'],
                        key="training_uploader_tab",
                        on_change=process_training_pdf
                    )
                    
                    if st.session_state.get('Treinamento_info_para_salvar'):
                        training_info = st.session_state['Treinamento_info_para_salvar']
                        audit_result = training_info.get('audit_result')
    
                        if training_info and training_info.get('data'):
                            with st.container(border=True):
                                st.markdown("### Confirme as Informações Extraídas")
                                
                                data = training_info.get('data')
                                norma_bruta = training_info.get('norma')
                                modulo = training_info.get('modulo') # Este é o módulo original OU o inferido
                                tipo_treinamento = training_info.get('tipo_treinamento')
                                carga_horaria = training_info.get('carga_horaria', 0)
                                
                                # 2. Padroniza a norma
                                norma_padronizada = employee_manager._padronizar_norma(norma_bruta)
                                
                                # 3. AGORA, com o módulo correto em mãos, calcula o vencimento
                                vencimento = employee_manager.calcular_vencimento_treinamento(
                                    data=data, 
                                    norma=norma_padronizada, 
                                    modulo=modulo, # Passa o módulo (original ou inferido)
                                    tipo_treinamento=tipo_treinamento
                                )
                                
                                # 4. Exibe as informações para o usuário
                                st.write(f"**Data:** {data.strftime('%d/%m/%Y')}")
                                st.write(f"**Norma Extraída:** {norma_bruta} (Padronizada para: {norma_padronizada})")
                                st.write(f"**Módulo:** {modulo or 'N/A'}") # Mostra o módulo final
                                st.write(f"**Tipo:** {tipo_treinamento}")
                                st.write(f"**Carga Horária:** {carga_horaria} horas")
                                
                                if vencimento:
                                    st.success(f"**Vencimento Calculado:** {vencimento.strftime('%d/%m/%Y')}")
                                else:
                                    st.error(f"**Falha ao Calcular Vencimento:** A norma '{norma_padronizada}' com módulo '{modulo}' não foi encontrada.")
                                
                                display_audit_results(audit_result)
        
                                if st.button("Confirmar e Salvar Treinamento", type="primary", disabled=(vencimento is None)):
                                    with st.spinner("Salvando Treinamento e processando auditoria..."):
                                        anexo_training = st.session_state.Treinamento_anexo_para_salvar
                                        selected_employee_training = st.session_state.Treinamento_funcionario_para_salvar
                                        employee_name = employee_manager.get_employee_name(selected_employee_training)
                                        arquivo_id = gdrive_uploader.upload_file(
                                            anexo_training,
                                            f"TRAINING_{employee_name}_{norma_padronizada}_{data.strftime('%Y%m%d')}"
                                        )
                                        
                                        if arquivo_id:
                                            training_data_to_save = {
                                                'funcionario_id': selected_employee_training,
                                                'data': training_info.get('data'),
                                                'vencimento': vencimento,
                                                'norma': norma_padronizada,
                                                'modulo': training_info.get('modulo'),
                                                'status': "Válido",
                                                'anexo': arquivo_id,
                                                'tipo_treinamento': training_info.get('tipo_treinamento'),
                                                'carga_horaria': training_info.get('carga_horaria', 0)
                                            }
                                                            
                                            training_id = employee_manager.add_training(training_data_to_save)
                                            
                                            if training_id:
                                                if audit_result and "não conforme" in audit_result.get("summary", "").lower():
                                                    created_count = nr_analyzer.create_action_plan_from_audit(
                                                        audit_result,
                                                        selected_company,
                                                        training_id,
                                                        employee_id=selected_employee_training
                                                    )
                                                    st.success(f"Treinamento salvo! {created_count} item(ns) de ação foram criados.")
                                                else:
                                                    st.success(f"Treinamento adicionado com sucesso! ID: {training_id}")
    
                                                for key in ['Treinamento_info_para_salvar', 'Treinamento_anexo_para_salvar', 'Treinamento_funcionario_para_salvar']:
                                                    if key in st.session_state:
                                                        del st.session_state[key]
                                                st.rerun()
                                            else:
                                                st.error("Falha ao salvar os dados do treinamento na planilha.")
                                        else:
                                            st.error("Falha ao fazer o upload do anexo para o Google Drive.")
                else:
                    st.warning("Nenhum funcionário cadastrado. Por favor, adicione funcionários na página de Administração.")
            else:
                st.error("Você não tem permissão para realizar esta ação.")
        else:
            st.info("Selecione uma empresa na primeira aba para adicionar um treinamento.")

