# /mount/src/segsisone/operations/front.py

import streamlit as st
from datetime import datetime, date
from operations.employee import EmployeeManager
from gdrive.gdrive_upload import GoogleDriveUploader
import pandas as pd
from auth.auth_utils import check_admin_permission

# Inicializa o uploader do Google Drive globalmente
gdrive_uploader = GoogleDriveUploader()

def mostrar_info_normas():
    with st.expander("Informações sobre Normas Regulamentadoras"):
        st.markdown("""
        ### Cargas Horárias e Periodicidade dos Treinamentos
        (Tabela de NRs...)
        """)

def highlight_expired(row):
    today = datetime.now().date()
    vencimento_val = row.get('vencimento')
    
    if vencimento_val and isinstance(vencimento_val, date):
        if vencimento_val < today:
            return ['background-color: #FFCDD2'] * len(row) # Vermelho claro
    return [''] * len(row)

def front_page():
    if 'employee_manager' not in st.session_state:
        st.session_state.employee_manager = EmployeeManager()
    
    employee_manager = st.session_state.employee_manager
    employee_manager.load_data()
    
    st.title("Gestão de Documentação de Contratada")
    
    selected_company = None
    if not employee_manager.companies_df.empty:
        selected_company = st.selectbox(
            "Selecione uma empresa",
            employee_manager.companies_df['id'].tolist(),
            format_func=lambda x: f"{employee_manager.companies_df[employee_manager.companies_df['id'] == str(x)]['nome'].iloc[0]} - {employee_manager.companies_df[employee_manager.companies_df['id'] == str(x)]['cnpj'].iloc[0]}",
            key="company_select"
        )
    
    tab_dados, tab_aso, tab_treinamento = st.tabs(["**Situação dos Funcionários**", "**Adicionar ASO**", "**Adicionar Treinamento**"])

    with tab_dados:
        if selected_company:
            st.subheader(f"Funcionários")
            employees = employee_manager.get_employees_by_company(selected_company)

            if not employees.empty:
                for index, employee in employees.iterrows():
                    employee_id = employee['id']
                    employee_name = employee['nome']
                    employee_role = employee['cargo']
                    
                    today = datetime.now().date()
                    aso_status = 'Não encontrado'
                    aso_vencimento = None
                    trainings_total = 0
                    trainings_expired_count = 0
                    
                    latest_aso = employee_manager.get_latest_aso_by_employee(employee_id)
                    if not latest_aso.empty:
                        vencimento_aso_obj = latest_aso['vencimento'].iloc[0]
                        if vencimento_aso_obj and isinstance(vencimento_aso_obj, date):
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
                        col1, col2, col3 = st.columns(3)
                        
                        col1.metric("Status Geral", overall_status, f"{trainings_expired_count + (1 if aso_status == 'Vencido' else 0)} pendências" if overall_status != 'Em Dia' else "Nenhuma pendência", delta_color="inverse" if overall_status != 'Em Dia' else "off")
                        col2.metric("Status do ASO", aso_status, help=f"Vencimento: {aso_vencimento.strftime('%d/%m/%Y') if aso_vencimento else 'N/A'}")
                        col3.metric("Treinamentos Vencidos", f"{trainings_expired_count} de {trainings_total}")
                        
                        st.markdown("---")
                        st.markdown("##### ASO Mais Recente")
                        if not latest_aso.empty:
                            st.dataframe(latest_aso.style.apply(highlight_expired, axis=1), hide_index=True, use_container_width=True)
                        else:
                            st.info("Nenhum ASO encontrado.")

                        st.markdown("##### Todos os Treinamentos")
                        if not all_trainings.empty:
                            st.dataframe(all_trainings.style.apply(highlight_expired, axis=1), hide_index=True, use_container_width=True)
                        else:
                            st.info("Nenhum treinamento encontrado.")
            else:
                st.info("Nenhum funcionário cadastrado para esta empresa.")
        else:
            with st.form("cadastro_empresa"):
                st.subheader("Cadastrar Nova Empresa")
                nome_empresa = st.text_input("Nome da Empresa")
                cnpj = st.text_input("CNPJ")
                if st.form_submit_button("Cadastrar Empresa") and nome_empresa and cnpj:
                    _, message = employee_manager.add_company(nome_empresa, cnpj)
                    st.success(message)
                    st.rerun()

    with tab_aso:
        if selected_company:
            if check_admin_permission():
                st.subheader("Adicionar Novo ASO")
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    selected_employee_aso = st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="aso_employee_add")
                    anexo_aso = st.file_uploader("Anexar ASO (PDF)", type=['pdf'], key="aso_uploader_tab")
                    if anexo_aso:
                        with st.spinner("Analisando PDF..."):
                            aso_info = employee_manager.analyze_aso_pdf(anexo_aso)
                        if aso_info and aso_info.get('data_aso'):
                            with st.container(border=True):
                                st.markdown("### Informações Extraídas")
                                st.write(f"**Data:** {aso_info['data_aso'].strftime('%d/%m/%Y')}")
                                if st.button("Confirmar e Salvar ASO", type="primary"):
                                    arquivo_id = gdrive_uploader.upload_file(anexo_aso, f"ASO_{selected_employee_aso}_{aso_info['data_aso']}")
                                    if arquivo_id:
                                        employee_manager.add_aso(selected_employee_aso, **aso_info, arquivo_id=arquivo_id)
                                        st.success("ASO adicionado!")
                                        st.rerun()
                        else: st.error("Não foi possível extrair informações do PDF.")
                else: st.warning("Cadastre funcionários nesta empresa primeiro.")
            else: st.error("Você não tem permissão para esta ação.")
        else: st.info("Selecione uma empresa na primeira aba.")

    with tab_treinamento:
        if selected_company:
            if check_admin_permission():
                st.subheader("Adicionar Novo Treinamento")
                mostrar_info_normas()
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    selected_employee_training = st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="training_employee_add")
                    anexo_training = st.file_uploader("Anexar Certificado (PDF)", type=['pdf'], key="training_uploader_tab")
                    if anexo_training:
                        with st.spinner("Analisando PDF..."):
                            training_info = employee_manager.analyze_training_pdf(anexo_training)
                        if training_info and training_info.get('data'):
                            with st.container(border=True):
                                st.markdown("### Informações Extraídas")
                                vencimento = employee_manager.calcular_vencimento_treinamento(**training_info)
                                st.write(f"**Data:** {training_info['data'].strftime('%d/%m/%Y')}")
                                st.write(f"**Norma:** {training_info.get('norma')}")
                                if vencimento: st.success(f"**Vencimento Calculado:** {vencimento.strftime('%d/%m/%Y')}")
                                if st.button("Confirmar e Salvar Treinamento", type="primary"):
                                    arquivo_id = gdrive_uploader.upload_file(anexo_training, f"TRAINING_{selected_employee_training}_{training_info.get('norma')}")
                                    if arquivo_id:
                                        employee_manager.add_training(id=selected_employee_training, anexo=arquivo_id, vencimento=vencimento, status="Válido", **training_info)
                                        st.success("Treinamento adicionado!")
                                        st.rerun()
                        else: st.error("Não foi possível extrair informações do PDF.")
                else: st.warning("Cadastre funcionários nesta empresa primeiro.")
            else: st.error("Você não tem permissão para esta ação.")
        else: st.info("Selecione uma empresa na primeira aba.")

   


   



   

   



   
   

   


   

   

   


   
   

   

   


   
   



   
   

   

   

   
   

   


   
   

   


   

   

   

   


   

   

   

   

   


   


   

   

   

   
