import streamlit as st
from datetime import datetime, date
from operations.employee import EmployeeManager
from gdrive.gdrive_upload import GoogleDriveUploader
import pandas as pd
from auth.auth_utils import is_admin, check_admin_permission

# Inicializa o uploader do Google Drive globalmente
gdrive_uploader = GoogleDriveUploader()

def mostrar_info_normas():
    with st.expander("Informações sobre Normas Regulamentadoras"):
        st.markdown("""
        ### Cargas Horárias e Periodicidade dos Treinamentos
        
        #### NR-20
        ##### Reciclagem:
        | Módulo | Periodicidade | Carga Horária Mínima |
        |--------|---------------|---------------------|
        | Básico | 3 anos | 4 horas |
        | Intermediário | 2 anos | 4 horas |
        | Avançado I | 1 ano | 4 horas |
        | Avançado II | 1 ano | 4 horas |
        
        ##### Formação Inicial:
        | Módulo | Carga Horária Mínima |
        |--------|---------------------|
        | Básico | 8 horas |
        | Intermediário | 16 horas |
        | Avançado I | 32 horas |
        | Avançado II | 40 horas |

        #### Outras NRs
        | Norma | Carga Horária Inicial | Carga Horária Reciclagem | Periodicidade Reciclagem |
        |-------|----------------------|------------------------|----------------------|
        | NR-35 | 8 horas | 8 horas | 2 anos |
        | NR-10 | 40 horas | 40 horas | 2 anos |
        | NR-18 | 8 horas | 8 horas | 1 ano |
        | NR-34 | 8 horas | 8 horas | 1 ano |
        """)

# Função auxiliar para colorir linhas da tabela com base na data de vencimento
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
            format_func=lambda x: f"{employee_manager.companies_df[employee_manager.companies_df['id'] == x]['nome'].iloc[0]} - {employee_manager.companies_df[employee_manager.companies_df['id'] == x]['cnpj'].iloc[0]}",
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
                    
                    # --- Calcula o status do funcionário ---
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
                        
                        col1.metric(
                            label="Status Geral", 
                            value=overall_status,
                            delta="Todos os documentos OK" if overall_status == 'Em Dia' else f"{trainings_expired_count + (1 if aso_status == 'Vencido' else 0)} pendências",
                            delta_color="off" if overall_status == 'Em Dia' else "inverse"
                        )
                        
                        col2.metric(
                            label="Status do ASO", 
                            value=aso_status, 
                            help=f"Vencimento: {aso_vencimento.strftime('%d/%m/%Y') if aso_vencimento else 'N/A'}"
                        )

                        col3.metric(
                            label="Treinamentos Vencidos",
                            value=f"{trainings_expired_count} de {trainings_total}"
                        )
                        st.markdown("---")

                        st.markdown("##### ASO Mais Recente")
                        if not latest_aso.empty:
                            st.dataframe(
                                latest_aso.style.apply(highlight_expired, axis=1),
                                column_config={
                                    "id": "ID ASO", "data_aso": st.column_config.DateColumn("Data do ASO", format="DD/MM/YYYY"),
                                    "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"), "riscos": "Riscos",
                                    "cargo": "Cargo (ASO)", "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF"),
                                    "funcionario_id": None, 
                                },
                                hide_index=True, use_container_width=True
                            )
                        else:
                            st.info("Nenhum ASO encontrado para este funcionário.")

                        st.markdown("##### Todos os Treinamentos")
                        if not all_trainings.empty:
                            st.dataframe(
                                all_trainings.style.apply(highlight_expired, axis=1),
                                column_config={
                                    "id": "ID Trein.", "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                                    "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                                    "carga_horaria": st.column_config.NumberColumn("C.H.", format="%d h", help="Carga Horária"),
                                    "norma": "Norma", "modulo": "Módulo", "tipo_treinamento": "Tipo",
                                    "arquivo_id": st.column_config.LinkColumn("Anexo", display_text="Abrir PDF"),
                                    "funcionario_id": None, "status": None
                                },
                                hide_index=True, use_container_width=True
                            )
                        else:
                            st.info("Nenhum treinamento encontrado para este funcionário.")
            else:
                st.info("Nenhum funcionário cadastrado para esta empresa.")
        else:
            with st.form("cadastro_empresa"):
                st.subheader("Cadastrar Nova Empresa")
                nome_empresa = st.text_input("Nome da Empresa")
                cnpj = st.text_input("CNPJ")
                if st.form_submit_button("Cadastrar Empresa") and nome_empresa and cnpj:
                    company_id, message = employee_manager.add_company(nome_empresa, cnpj)
                    if company_id:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

    with tab_aso:
        if selected_company:
            if check_admin_permission():
                st.subheader("Adicionar Novo ASO")
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    selected_employee_aso = st.selectbox("Selecione o funcionário", current_employees['id'].tolist(), format_func=lambda x: employee_manager.get_employee_name(x), key="aso_employee_add_tab")
                    anexo_aso = st.file_uploader("Anexar ASO (PDF)", type=['pdf'], key="aso_uploader_tab")
                    if anexo_aso:
                        with st.spinner("Analisando o PDF do ASO..."):
                            aso_info = employee_manager.analyze_aso_pdf(anexo_aso)
                        if aso_info:
                            with st.container(border=True):
                                st.markdown("### Informações Extraídas do ASO")
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**Data do ASO:** {aso_info['data_aso'].strftime('%d/%m/%Y') if aso_info.get('data_aso') else 'Não encontrada'}")
                                    st.write(f"**Cargo:** {aso_info.get('cargo', 'N/A')}")
                                with col2:
                                    st.write(f"**Vencimento:** {aso_info['vencimento'].strftime('%d/%m/%Y') if aso_info.get('vencimento') else 'Não encontrada'}")
                                    st.write(f"**Riscos:** {aso_info.get('riscos', 'N/A')}")
                                if st.button("Confirmar e Salvar ASO", type="primary", key="save_aso_btn"):
                                    arquivo_id = gdrive_uploader.upload_file(anexo_aso, f"ASO_EMP_{selected_employee_aso}_COMP_{selected_company}")
                                    if arquivo_id:
                                        employee_manager.add_aso(selected_employee_aso, aso_info['data_aso'], aso_info['vencimento'], arquivo_id, aso_info['riscos'], aso_info['cargo'])
                                        st.success("ASO adicionado com sucesso!")
                                        st.cache_data.clear()
                                        st.rerun()
                        else: st.error("Não foi possível extrair informações do PDF.")
                else: st.warning("Cadastre funcionários para esta empresa antes de adicionar ASOs.")
            else: st.error("Você não tem permissão para realizar esta ação.")
        else: st.info("Selecione uma empresa na aba 'Situação dos Funcionários' para adicionar um ASO.")

    with tab_treinamento:
        if selected_company:
            if check_admin_permission():
                st.subheader("Adicionar Novo Treinamento")
                mostrar_info_normas()
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    selected_employee_training = st.selectbox("Selecione o funcionário", current_employees['id'].tolist(), format_func=lambda x: employee_manager.get_employee_name(x), key="treinamento_employee_add_tab")
                    anexo_training = st.file_uploader("Anexar Certificado (PDF)", type=['pdf'], key="treinamento_uploader_tab")
                    if anexo_training:
                        with st.spinner("Analisando o PDF do treinamento..."):
                            treinamento_info = employee_manager.analyze_training_pdf(anexo_training)
                        if treinamento_info:
                            with st.container(border=True):
                                st.markdown("### Informações Extraídas do Treinamento")
                                data = treinamento_info.get('data')
                                vencimento = employee_manager.calcular_vencimento_treinamento(data, treinamento_info.get('norma'), treinamento_info.get('modulo'), treinamento_info.get('tipo_treinamento')) if isinstance(data, date) else None
                                st.write(f"**Data:** {data.strftime('%d/%m/%Y') if data else 'Não encontrada'}")
                                st.write(f"**Norma:** {treinamento_info.get('norma', 'N/A')}")
                                if vencimento: st.success(f"**Vencimento Calculado:** {vencimento.strftime('%d/%m/%Y')}")
                                else: st.warning("Não foi possível calcular o vencimento.")
                                if st.button("Confirmar e Salvar Treinamento", type="primary", key="save_training_btn"):
                                    arquivo_id = gdrive_uploader.upload_file(anexo_training, f"TREINAMENTO_EMP_{selected_employee_training}_COMP_{selected_company}_{treinamento_info.get('norma')}")
                                    if arquivo_id:
                                        employee_manager.add_training(id=selected_employee_training, data=data, vencimento=vencimento, norma=treinamento_info.get('norma'), modulo=treinamento_info.get('modulo'), status="Válido", anexo=arquivo_id, tipo_treinamento=treinamento_info.get('tipo_treinamento'), carga_horaria=treinamento_info.get('carga_horaria'))
                                        st.success("Treinamento registrado com sucesso!")
                                        st.cache_data.clear()
                                        st.rerun()
                        else: st.error("Não foi possível extrair informações do PDF.")
                else: st.warning("Cadastre funcionários para esta empresa antes de adicionar treinamentos.")
            else: st.error("Você não tem permissão para realizar esta ação.")
        else: st.info("Selecione uma empresa na aba 'Situação dos Funcionários' para adicionar um treinamento.")




















