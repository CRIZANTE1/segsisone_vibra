import streamlit as st
from datetime import datetime
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

def front_page():
    # Inicializa o gerenciador de funcionários
    if 'employee_manager' not in st.session_state:
        st.session_state.employee_manager = EmployeeManager()
    
    employee_manager = st.session_state.employee_manager
    
    # Carrega os dados
    employee_manager.load_data()
    
    # Título da página
    st.title("Gestão de Documentação de Contratada")
    
    # Seleção de empresa
    if not employee_manager.companies_df.empty:
        selected_company = st.selectbox(
            "Selecione uma empresa",
            employee_manager.companies_df['id'].tolist(),
            format_func=lambda x: f"{employee_manager.companies_df[employee_manager.companies_df['id'] == x]['nome'].iloc[0]} - {employee_manager.companies_df[employee_manager.companies_df['id'] == x]['cnpj'].iloc[0]}"
        )
        
        # Obtém os funcionários da empresa selecionada
        employees = employee_manager.get_employees_by_company(selected_company)
        
        # Criar abas para diferentes operações
        tab_dados, tab_aso, tab_treinamento = st.tabs(["Dados da Empresa", "Adicionar ASO", "Adicionar Treinamento"])
        
        with tab_dados:
            if not employees.empty:
                st.subheader("Funcionários")
                st.dataframe(employees[['nome', 'cargo', 'data_admissao']])
                
                # Mostrar ASOs
                st.subheader("ASOs")
                asos = pd.DataFrame()
                for _, employee in employees.iterrows():
                    aso_docs, _ = employee_manager.get_employee_docs(employee['id'])
                    if not aso_docs.empty:
                        aso_docs = aso_docs.copy()
                        aso_docs.loc[:, 'funcionario'] = employee['nome']
                        asos = pd.concat([asos, aso_docs])
                
                if not asos.empty:
                    # Converter colunas de data para datetime
                    asos['data_aso'] = pd.to_datetime(asos['data_aso'])
                    asos['vencimento'] = pd.to_datetime(asos['vencimento'])
                    
                    # Configurar colunas da tabela
                    st.dataframe(
                        asos,
                        column_config={
                            "id": st.column_config.NumberColumn("ID", width=50),
                            "data_aso": st.column_config.DateColumn("Data do ASO", format="DD/MM/YYYY"),
                            "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                            "riscos": "Riscos",
                            "cargo": "Cargo",
                            "arquivo_id": st.column_config.LinkColumn(
                                label="Anexo",
                                display_text="Abrir PDF",
                                help="Clique para abrir o PDF no Google Drive"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("Nenhum ASO registrado")

                # Mostrar Treinamentos
                st.subheader("Treinamentos")
                treinamentos = pd.DataFrame()
                for _, employee in employees.iterrows():
                    _, training_docs = employee_manager.get_employee_docs(employee['id'])
                    if not training_docs.empty:
                        training_docs = training_docs.copy()
                        training_docs.loc[:, 'funcionario'] = employee['nome']
                        treinamentos = pd.concat([treinamentos, training_docs])
                
                if not treinamentos.empty:
                    # Converter colunas de data para datetime
                    treinamentos['data'] = pd.to_datetime(treinamentos['data'])
                    treinamentos['vencimento'] = pd.to_datetime(treinamentos['vencimento'])
                    
                    # Configurar colunas da tabela
                    st.dataframe(
                        treinamentos,
                        column_config={
                            "id": st.column_config.NumberColumn("ID", width=50),
                            "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                            "vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                            "norma": "Norma",
                            "modulo": "Módulo",
                            "status": "Status",
                            "tipo_treinamento": "Tipo",
                            "carga_horaria": st.column_config.NumberColumn("Carga Horária", format="%d horas"),
                            "arquivo_id": st.column_config.LinkColumn(
                                label="Anexo",
                                display_text="Abrir PDF",
                                help="Clique para abrir o PDF no Google Drive"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("Nenhum treinamento registrado")
            else:
                st.info("Nenhum funcionário cadastrado para esta empresa")
        
        with tab_aso:
            if check_admin_permission():  # Verifica permissão antes de permitir adicionar ASO
                st.subheader("Adicionar ASO")
                if not employees.empty:
                    # Seleção do funcionário
                    selected_employee = st.selectbox(
                        "Selecione o funcionário",
                        employees['id'].tolist(),
                        format_func=lambda x: employees[employees['id'] == x]['nome'].iloc[0]
                    )
                    
                    # Upload do arquivo
                    anexo = st.file_uploader("Anexar ASO (PDF)", type=['pdf'], key="aso_uploader")
                    
                    if anexo:
                        # Analisar o PDF
                        with st.spinner("Analisando o PDF do ASO..."):
                            aso_info = employee_manager.analyze_aso_pdf(anexo)
                        
                        if aso_info:
                            # Mostrar informações extraídas em um container
                            with st.container():
                                st.markdown("### Informações Extraídas do ASO")
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write("**Data do ASO:**")
                                    st.write(aso_info['data_aso'].strftime('%d/%m/%Y') if aso_info['data_aso'] else 'Não encontrada')
                                    st.write("**Cargo:**")
                                    st.write(aso_info['cargo'])
                                with col2:
                                    st.write("**Data de Vencimento:**")
                                    st.write(aso_info['vencimento'].strftime('%d/%m/%Y') if aso_info['vencimento'] else 'Não encontrada')
                                    st.write("**Riscos:**")
                                    st.write(aso_info['riscos'])
                                
                                # Botão para confirmar e salvar
                                if st.button("Confirmar e Salvar ASO", type="primary"):
                                    # Upload do arquivo com ID do empregado e empresa
                                    gdrive_uploader = GoogleDriveUploader()
                                    arquivo_id = gdrive_uploader.upload_file(
                                        anexo, 
                                        f"ASO_EMP_{selected_employee}_COMP_{selected_company}"
                                    )
                                    
                                    if arquivo_id:
                                        # Adicionar ASO
                                        aso_id = employee_manager.add_aso(
                                            selected_employee,
                                            aso_info['data_aso'],
                                            aso_info['vencimento'],
                                            arquivo_id,
                                            aso_info['riscos'],
                                            aso_info['cargo']
                                        )
                                        if aso_id:
                                            st.success("ASO adicionado com sucesso!")
                                            # Limpar o estado do uploader
                                            if 'aso_uploader' in st.session_state:
                                                del st.session_state.aso_uploader
                                            st.rerun()
                                        else:
                                            st.error("Erro ao adicionar ASO")
                                    else:
                                        st.error("Erro ao fazer upload do arquivo")
                        else:
                            st.error("Não foi possível extrair informações do PDF. Por favor, verifique se o arquivo está correto.")
        
        with tab_treinamento:
            if check_admin_permission():  # Verifica permissão antes de permitir adicionar treinamento
                st.subheader("Adicionar Treinamento")
                if not employees.empty:
                    # Seleção do funcionário
                    selected_employee = st.selectbox(
                        "Selecione o funcionário",
                        employees['id'].tolist(),
                        format_func=lambda x: employees[employees['id'] == x]['nome'].iloc[0],
                        key="treinamento_employee"
                    )
                    
                    # Upload do arquivo
                    anexo = st.file_uploader("Anexar Certificado (PDF)", type=['pdf'], key="treinamento_uploader")
                    
                    if anexo:
                        # Analisar o PDF
                        with st.spinner("Analisando o PDF do treinamento..."):
                            treinamento_info = employee_manager.analyze_training_pdf(anexo)
                        
                        if treinamento_info:
                            # Mostrar informações extraídas em um container
                            with st.container():
                                st.markdown("### Informações Extraídas do Treinamento")
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write("**Norma:**")
                                    st.write(treinamento_info['norma'])
                                    st.write("**Data:**")
                                    st.write(treinamento_info['data'].strftime('%d/%m/%Y') if treinamento_info['data'] else 'Não encontrada')
                                    st.write("**Carga Horária:**")
                                    st.write(f"{treinamento_info['carga_horaria']} horas")
                                with col2:
                                    st.write("**Módulo:**")
                                    st.write(treinamento_info['modulo'])
                                    st.write("**Tipo:**")
                                    st.write(treinamento_info['tipo_treinamento'])
                                    st.write("**Vencimento:**")
                                    st.write(treinamento_info['vencimento'].strftime('%d/%m/%Y') if treinamento_info['vencimento'] else 'Não encontrado')
                                
                                # Validar carga horária
                                is_valid, message = employee_manager.validar_treinamento(
                                    treinamento_info['norma'],
                                    treinamento_info['modulo'],
                                    treinamento_info['tipo_treinamento'],
                                    treinamento_info['carga_horaria']
                                )
                                
                                if not is_valid:
                                    st.warning(message)
                                
                                # Botão para confirmar e salvar
                                if st.button("Confirmar e Salvar Treinamento", type="primary"):
                                    if is_valid:
                                        # Upload do arquivo com ID do empregado e empresa
                                        gdrive_uploader = GoogleDriveUploader()
                                        arquivo_id = gdrive_uploader.upload_file(
                                            anexo, 
                                            f"TREINAMENTO_EMP_{selected_employee}_COMP_{selected_company}_{treinamento_info['norma']}_{treinamento_info['modulo'] if treinamento_info['modulo'] else 'N/A'}"
                                        )
                                        
                                        if arquivo_id:
                                            # Adicionar treinamento
                                            training_id = employee_manager.add_training(
                                                selected_employee,
                                                treinamento_info['data'],
                                                treinamento_info['vencimento'],
                                                treinamento_info['norma'],
                                                treinamento_info['modulo'],
                                                "Válido",
                                                arquivo_id,
                                                treinamento_info['tipo_treinamento'],
                                                treinamento_info['carga_horaria']
                                            )
                                            
                                            if training_id:
                                                st.success("Treinamento adicionado com sucesso!")
                                                # Limpar o estado do uploader
                                                if 'treinamento_uploader' in st.session_state:
                                                    del st.session_state.treinamento_uploader
                                                st.rerun()
                                            else:
                                                st.error("Erro ao adicionar treinamento")
                                        else:
                                            st.error("Erro ao fazer upload do arquivo")
                                    else:
                                        st.error("Não é possível salvar o treinamento com carga horária inválida.")
                        else:
                            st.error("Não foi possível extrair informações do PDF. Por favor, verifique se o arquivo está correto.")
    else:
        # Cadastro de nova empresa
        with st.form("cadastro_empresa"):
            st.subheader("Cadastrar Nova Empresa")
            nome_empresa = st.text_input("Nome da Empresa")
            cnpj = st.text_input("CNPJ")
            
            submitted = st.form_submit_button("Cadastrar Empresa")
            if submitted and nome_empresa and cnpj:
                company_id, message = employee_manager.add_company(nome_empresa, cnpj)
                if company_id:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
   
def mostrar_aso():
    st.header("Gestão de ASO")
    
    # Usa a instância do EmployeeManager da sessão
    if 'employee_manager' not in st.session_state:
        st.session_state.employee_manager = EmployeeManager()
    
    employee_manager = st.session_state.employee_manager
    
    # Lista as empresas disponíveis
    if not employee_manager.companies_df.empty:
        selected_company = st.selectbox(
            "Selecione uma empresa",
            employee_manager.companies_df['id'].tolist(),
            format_func=lambda x: f"{employee_manager.companies_df[employee_manager.companies_df['id'] == x]['nome'].iloc[0]} - {employee_manager.companies_df[employee_manager.companies_df['id'] == x]['cnpj'].iloc[0]}",
            key="aso_company"
        )
        
        if selected_company:
            # Obtém os funcionários da empresa selecionada
            employees = employee_manager.get_employees_by_company(selected_company)
            
            if not employees.empty:
                # Seleção do funcionário
                selected_employee = st.selectbox(
                    "Selecione um funcionário",
                    employees['id'].tolist(),
                    format_func=lambda x: f"{employees[employees['id'] == x]['nome'].iloc[0]}",
                    key="aso_employee"
                )
                
                if selected_employee:
                    with st.form("adicionar_aso_main"):
                        arquivo = st.file_uploader("Upload do ASO (PDF)", type=['pdf'], key="aso_upload")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            manual_input = st.checkbox("Inserir dados manualmente", key="aso_manual")
                        
                        if arquivo and not manual_input:
                            with st.spinner("Analisando o PDF do ASO..."):
                                aso_info = employee_manager.analyze_aso_pdf(arquivo)
                                
                            if aso_info:
                                data_aso = st.date_input("Data do ASO", value=aso_info['data_aso'] if aso_info['data_aso'] else datetime.now())
                                vencimento = st.date_input("Data de Vencimento", value=aso_info['vencimento'] if aso_info['vencimento'] else None)
                                riscos = st.text_area("Riscos", value=aso_info['riscos'])
                                cargo_aso = st.text_input("Cargo (conforme ASO)", value=aso_info['cargo'])
                            else:
                                st.error("Não foi possível extrair informações do PDF. Por favor, insira os dados manualmente.")
                                manual_input = True
                        
                        if manual_input:
                            data_aso = st.date_input("Data do ASO")
                            vencimento = st.date_input("Data de Vencimento")
                            riscos = st.text_area("Riscos", help="Liste os riscos ocupacionais identificados")
                            cargo_aso = st.text_input("Cargo (conforme ASO)")
                        
                        if st.form_submit_button("Adicionar ASO"):
                            if arquivo:
                                arquivo_id = gdrive_uploader.upload_file(arquivo, f"ASO_{selected_employee}_{data_aso}")
                                employee_manager.add_aso(
                                    selected_employee,
                                    data_aso,
                                    vencimento,
                                    arquivo_id,
                                    riscos,
                                    cargo_aso
                                )
                                st.success("ASO adicionado com sucesso!")
                                st.rerun()
                            else:
                                st.error("Por favor, faça o upload do arquivo do ASO")
            else:
                st.warning("É necessário cadastrar funcionários primeiro")
    else:
        st.warning("Nenhuma empresa cadastrada. Por favor, cadastre uma empresa primeiro.")

def mostrar_treinamentos():
    st.header("Gestão de Treinamentos")
    
    # Usa a instância do EmployeeManager da sessão
    if 'employee_manager' not in st.session_state:
        st.session_state.employee_manager = EmployeeManager()
    
    employee_manager = st.session_state.employee_manager
    
    # Mostra informações sobre as normas
    mostrar_info_normas()
    
    # Lista as empresas disponíveis
    if not employee_manager.companies_df.empty:
        selected_company = st.selectbox(
            "Selecione uma empresa",
            employee_manager.companies_df['id'].tolist(),
            format_func=lambda x: f"{employee_manager.companies_df[employee_manager.companies_df['id'] == x]['nome'].iloc[0]} - {employee_manager.companies_df[employee_manager.companies_df['id'] == x]['cnpj'].iloc[0]}",
            key="treinamento_company"
        )
        
        if selected_company:
            # Obtém os funcionários da empresa selecionada
            employees = employee_manager.get_employees_by_company(selected_company)
            
            if not employees.empty:
                # Seleção do funcionário
                selected_employee = st.selectbox(
                    "Selecione um funcionário",
                    employees['id'].tolist(),
                    format_func=lambda x: f"{employees[employees['id'] == x]['nome'].iloc[0]}",
                    key="treinamento_employee_main"
                )
                
                if selected_employee:
                    with st.form("adicionar_treinamento_main"):
                        arquivo = st.file_uploader("Upload do Certificado (PDF)", type=['pdf'], key="treinamento_upload_main")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            manual_input = st.checkbox("Inserir dados manualmente", key="treinamento_manual_main")
                        
                        if arquivo and not manual_input:
                            with st.spinner("Analisando o PDF do treinamento..."):
                                treinamento_info = employee_manager.analyze_training_pdf(arquivo)
                                
                            if treinamento_info:
                                data = st.date_input("Data do Treinamento", value=treinamento_info['data'] if treinamento_info['data'] else datetime.now())
                                norma = st.text_input("Norma", value=treinamento_info['norma'])
                                modulo = st.text_input("Módulo", value=treinamento_info['modulo'])
                                tipo_treinamento = st.selectbox(
                                    "Tipo de Treinamento",
                                    ["inicial", "reciclagem"],
                                    index=0 if treinamento_info['tipo_treinamento'] == 'inicial' else 1
                                )
                                carga_horaria = st.number_input("Carga Horária (horas)", value=treinamento_info['carga_horaria'] if treinamento_info['carga_horaria'] else 0)
                                
                                # Calcula o vencimento automaticamente
                                vencimento = employee_manager.calcular_vencimento_treinamento(data, norma, modulo, tipo_treinamento)
                                if vencimento:
                                    st.info(f"Data de vencimento calculada: {vencimento.strftime('%d/%m/%Y')}")
                                
                                # Valida a carga horária
                                valido, mensagem = employee_manager.validar_treinamento(norma, modulo, tipo_treinamento, carga_horaria)
                                if not valido:
                                    st.warning(mensagem)
                            else:
                                st.error("Não foi possível extrair informações do PDF. Por favor, insira os dados manualmente.")
                                manual_input = True
                        
                        if manual_input:
                            data = st.date_input("Data do Treinamento")
                            norma = st.selectbox("Norma", ["NR-20", "NR-35", "NR-10", "NR-18", "NR-34"])
                            
                            if norma == "NR-20":
                                modulo = st.selectbox("Módulo", ["Básico", "Intermediário", "Avançado I", "Avançado II"])
                            else:
                                modulo = "N/A"
                            
                            tipo_treinamento = st.selectbox("Tipo de Treinamento", ["inicial", "reciclagem"])
                            carga_horaria = st.number_input("Carga Horária (horas)", min_value=1)
                            
                            # Calcula o vencimento automaticamente
                            vencimento = employee_manager.calcular_vencimento_treinamento(data, norma, modulo, tipo_treinamento)
                            if vencimento:
                                st.info(f"Data de vencimento calculada: {vencimento.strftime('%d/%m/%Y')}")
                            
                            # Valida a carga horária
                            valido, mensagem = employee_manager.validar_treinamento(norma, modulo, tipo_treinamento, carga_horaria)
                            if not valido:
                                st.warning(mensagem)
                        
                            if st.form_submit_button("Adicionar Treinamento"):
                                if arquivo:
                                    if vencimento is None:
                                        st.error("Não foi possível calcular a data de vencimento. Por favor, verifique os dados do treinamento.")
                                    else:
                                        arquivo_id = gdrive_uploader.upload_file(arquivo, f"TREINAMENTO_{selected_employee}_{norma}_{data}")
                                        employee_manager.add_training(
                                            selected_employee,
                                            data,
                                            vencimento,
                                            norma,
                                            modulo,
                                            "Válido",
                                            arquivo_id,
                                            tipo_treinamento,
                                            carga_horaria
                                        )
                                        st.success("Treinamento adicionado com sucesso!")
                                        st.rerun()
                                else:
                                    st.error("Por favor, faça o upload do certificado do treinamento")
            else:
                st.warning("É necessário cadastrar funcionários primeiro")
    else:
        st.warning("Nenhuma empresa cadastrada. Por favor, cadastre uma empresa primeiro.")

   

   

   

   
   

   


   
   

   


   

   

   

   


   

   

   

   

   


   


   

   

   

   
