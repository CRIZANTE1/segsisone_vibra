import streamlit as st
from datetime import datetime, date
from operations.employee import EmployeeManager
from gdrive.gdrive_upload import GoogleDriveUploader
import pandas as pd
from auth.auth_utils import check_admin_permission

gdrive_uploader = GoogleDriveUploader()

def mostrar_info_normas():
    with st.expander("Informações sobre Normas Regulamentadoras"):
        st.markdown("...") # Sua tabela de NRs

def highlight_expired(row):
    today = datetime.now().date()
    vencimento_val = row.get('vencimento')
    if isinstance(vencimento_val, date) and vencimento_val < today:
        return ['background-color: #FFCDD2'] * len(row)
    return [''] * len(row)

def process_aso_pdf():
    if st.session_state.aso_uploader_tab:
        employee_manager = st.session_state.employee_manager
        with st.spinner("Analisando PDF do ASO..."):
            st.session_state.aso_anexo_para_salvar = st.session_state.aso_uploader_tab
            st.session_state.aso_funcionario_para_salvar = st.session_state.aso_employee_add
            st.session_state.aso_info_para_salvar = employee_manager.analyze_aso_pdf(st.session_state.aso_uploader_tab)

def process_training_pdf():
    if st.session_state.training_uploader_tab:
        employee_manager = st.session_state.employee_manager
        with st.spinner("Analisando PDF do Treinamento..."):
            st.session_state.training_anexo_para_salvar = st.session_state.training_uploader_tab
            st.session_state.training_funcionario_para_salvar = st.session_state.training_employee_add
            st.session_state.training_info_para_salvar = employee_manager.analyze_training_pdf(st.session_state.training_uploader_tab)

def front_page():
    if 'employee_manager' not in st.session_state:
        st.session_state.employee_manager = EmployeeManager()
    
    employee_manager = st.session_state.employee_manager
    employee_manager.load_data()
    
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
    
    tab_dados, tab_aso, tab_treinamento = st.tabs(["**Situação dos Funcionários**", "**Adicionar ASO**", "**Adicionar Treinamento**"])

    with tab_dados:
        if selected_company:
            st.subheader("Funcionários")
            employees = employee_manager.get_employees_by_company(selected_company)
            if not employees.empty:
                for index, employee in employees.iterrows():
                    employee_id = employee['id']; employee_name = employee['nome']; employee_role = employee['cargo']
                    
                    # Lógica de status (sem alterações)
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
                        # Dashboard de status (sem alterações)
                        st.markdown("##### Resumo de Status")
                        col1, col2, col3 = st.columns(3); num_pendencias = trainings_expired_count + (1 if aso_status == 'Vencido' else 0)
                        col1.metric("Status Geral", overall_status, f"{num_pendencias} pendência(s)" if num_pendencias > 0 else "Nenhuma pendência", delta_color="inverse" if overall_status != 'Em Dia' else "off")
                        col2.metric("Status do ASO", aso_status, help=f"Vencimento: {aso_vencimento.strftime('%d/%m/%Y') if aso_vencimento else 'N/A'}")
                        col3.metric("Treinamentos Vencidos", f"{trainings_expired_count} de {trainings_total}")
                        st.markdown("---")

                        st.markdown("##### ASO Mais Recente")
                        if not latest_aso.empty:
                            # --- CORREÇÃO APLICADA AQUI ---
                            # Garante que todas as colunas esperadas existam no DataFrame
                            aso_display_cols = ["tipo_aso", "data_aso", "vencimento", "cargo", "riscos", "arquivo_id"]
                            for col in aso_display_cols:
                                if col not in latest_aso.columns:
                                    latest_aso[col] = "N/A" # Adiciona a coluna com um valor padrão

                            st.dataframe(
                                latest_aso.style.apply(highlight_expired, axis=1),
                                column_config={
                                    "tipo_aso": "Tipo", "data_aso": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                                    "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                                    "cargo": "Cargo (ASO)", "riscos": "Riscos",
                                    "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF"),
                                    "id": None, "funcionario_id": None,
                                },
                                order=aso_display_cols, # Usa a lista para reordenar
                                hide_index=True, use_container_width=True
                            )
                        else: st.info("Nenhum ASO encontrado.")

                        st.markdown("##### Todos os Treinamentos")
                        if not all_trainings.empty:
                            # --- CORREÇÃO APLICADA AQUI ---
                            # Garante que todas as colunas esperadas existam
                            training_display_cols = ["norma", "data", "vencimento", "tipo_treinamento", "carga_horaria", "arquivo_id"]
                            for col in training_display_cols:
                                if col not in all_trainings.columns:
                                    all_trainings[col] = "N/A"

                            st.dataframe(
                                all_trainings.style.apply(highlight_expired, axis=1),
                                column_config={
                                    "norma": "Norma", "data": st.column_config.DateColumn("Realização", format="DD/MM/YYYY"),
                                    "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                                    "tipo_treinamento": "Tipo",
                                    "carga_horaria": st.column_config.NumberColumn("C.H.", help="Carga Horária (horas)"),
                                    "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF"),
                                    "id": None, "funcionario_id": None, "status": None, "modulo": None,
                                },
                                order=training_display_cols, # Usa a lista para reordenar
                                hide_index=True, use_container_width=True
                            )
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

    with tab_aso:
        # Lógica da aba Adicionar ASO (sem alterações)
        if selected_company:
            if check_admin_permission():
                st.subheader("Adicionar Novo ASO")
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="aso_employee_add")
                    st.file_uploader("Anexar ASO (PDF)", type=['pdf'], key="aso_uploader_tab", on_change=process_aso_pdf)
                    if 'aso_info_para_salvar' in st.session_state:
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
                                    anexo_aso = st.session_state.aso_anexo_para_salvar
                                    selected_employee_aso = st.session_state.aso_funcionario_para_salvar
                                    arquivo_id = gdrive_uploader.upload_file(anexo_aso, f"ASO_{selected_employee_aso}_{aso_info['data_aso']}")
                                    if arquivo_id:
                                        employee_manager.add_aso(id=selected_employee_aso, arquivo_id=arquivo_id, **aso_info)
                                        st.success("ASO adicionado!");
                                        del st.session_state.aso_info_para_salvar, st.session_state.aso_anexo_para_salvar, st.session_state.aso_funcionario_para_salvar
                                        st.rerun()
                        else:
                            st.error("Não foi possível extrair informações do PDF.")
                            if 'aso_info_para_salvar' in st.session_state: del st.session_state.aso_info_para_salvar
                else: st.warning("Cadastre funcionários nesta empresa primeiro.")
            else: st.error("Você não tem permissão para esta ação.")
        else: st.info("Selecione uma empresa na primeira aba.")

    with tab_treinamento:
        # Lógica da aba Adicionar Treinamento (sem alterações)
        if selected_company:
            if check_admin_permission():
                st.subheader("Adicionar Novo Treinamento")
                mostrar_info_normas()
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="training_employee_add")
                    st.file_uploader("Anexar Certificado (PDF)", type=['pdf'], key="training_uploader_tab", on_change=process_training_pdf)
                    if 'training_info_para_salvar' in st.session_state:
                        training_info = st.session_state.training_info_para_salvar
                        if training_info and training_info.get('data'):
                            with st.container(border=True):
                                st.markdown("### Confirme as Informações Extraídas")
                                data = training_info.get('data')
                                vencimento = employee_manager.calcular_vencimento_treinamento(data=data, norma=training_info.get('norma'), modulo=training_info.get('modulo'), tipo_treinamento=training_info.get('tipo_treinamento'))
                                st.write(f"**Data:** {data.strftime('%d/%m/%Y')}")
                                st.write(f"**Norma:** {training_info.get('norma')}")
                                if vencimento: st.success(f"**Vencimento Calculado:** {vencimento.strftime('%d/%m/%Y')}")
                                if st.button("Confirmar e Salvar Treinamento", type="primary"):
                                    anexo_training = st.session_state.training_anexo_para_salvar
                                    selected_employee_training = st.session_state.training_funcionario_para_salvar
                                    arquivo_id = gdrive_uploader.upload_file(anexo_training, f"TRAINING_{selected_employee_training}_{training_info.get('norma')}")
                                    if arquivo_id:
                                        training_info.update({'id': selected_employee_training, 'anexo': arquivo_id, 'vencimento': vencimento, 'status': "Válido"})
                                        employee_manager.add_training(**training_info)
                                        st.success("Treinamento adicionado!");
                                        del st.session_state.training_info_para_salvar, st.session_state.training_anexo_para_salvar, st.session_state.training_funcionario_para_salvar
                                        st.rerun()
                        else:
                            st.error("Não foi possível extrair informações do PDF.")
                            if 'training_info_para_salvar' in st.session_state: del st.session_state.training_info_para_salvar
                else: st.warning("Cadastre funcionários nesta empresa primeiro.")
            else: st.error("Você não tem permissão para esta ação.")
        else: st.info("Selecione uma empresa na primeira aba.")
   

   

   


   


   

   

   

   
