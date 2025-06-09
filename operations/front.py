import streamlit as st
from datetime import datetime
from gdrive.gdrive_upload import GoogleDriveUploader
from .employee import EmployeeManager
import pandas as pd

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
    st.title("Gestão de Documentação de Contratada")
    
    # Inicializa o gerenciador de funcionários
    employee_manager = EmployeeManager()
    
    # Seleção da empresa
    if not employee_manager.companies_df.empty:
        selected_company = st.selectbox(
            "Selecione uma empresa",
            employee_manager.companies_df['id'].tolist(),
            format_func=lambda x: f"{employee_manager.companies_df[employee_manager.companies_df['id'] == x]['nome'].iloc[0]} - {employee_manager.companies_df[employee_manager.companies_df['id'] == x]['cnpj'].iloc[0]}"
        )
        
        if selected_company:
            # Obtém os funcionários da empresa selecionada
            employees = employee_manager.get_employees_by_company(selected_company)
            
            # Criar abas para diferentes operações
            tab_dados, tab_documentos = st.tabs(["Dados da Empresa", "Adicionar Documentos"])
            
            with tab_dados:
                if not employees.empty:
                    st.subheader("Funcionários")
                    st.dataframe(employees[['nome', 'cargo', 'data_admissao']])
                    
                    # Mostrar treinamentos e ASOs
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("Treinamentos")
                        treinamentos = pd.DataFrame()
                        for _, employee in employees.iterrows():
                            _, training_docs = employee_manager.get_employee_docs(employee['id'])
                            if not training_docs.empty:
                                training_docs['funcionario'] = employee['nome']
                                treinamentos = pd.concat([treinamentos, training_docs])
                        
                        if not treinamentos.empty:
                            st.dataframe(treinamentos[[
                                'funcionario', 'norma', 'modulo', 'data', 
                                'vencimento', 'status', 'tipo_treinamento'
                            ]])
                        else:
                            st.info("Nenhum treinamento registrado")
                    
                    with col2:
                        st.subheader("ASOs")
                        asos = pd.DataFrame()
                        for _, employee in employees.iterrows():
                            aso_docs, _ = employee_manager.get_employee_docs(employee['id'])
                            if not aso_docs.empty:
                                aso_docs['funcionario'] = employee['nome']
                                asos = pd.concat([asos, aso_docs])
                        
                        if not asos.empty:
                            st.dataframe(asos[[
                                'funcionario', 'data_aso', 'vencimento', 
                                'cargo', 'riscos'
                            ]])
                        else:
                            st.info("Nenhum ASO registrado")
                else:
                    st.info("Nenhum funcionário cadastrado para esta empresa")
                    
                # Botão para cadastrar novo funcionário
                with st.expander("Cadastrar Novo Funcionário"):
                    with st.form("cadastro_funcionario"):
                        nome = st.text_input("Nome do Funcionário")
                        cargo = st.text_input("Cargo")
                        data_admissao = st.date_input("Data de Admissão")
                        
                        submitted = st.form_submit_button("Cadastrar")
                        if submitted and nome and cargo:
                            employee_id, message = employee_manager.add_employee(
                                nome, selected_company, cargo, data_admissao
                            )
                            if employee_id:
                                st.success(message)
                            else:
                                st.error(message)
            
            with tab_documentos:
                if not employees.empty:
                    # Seleção do funcionário
                    selected_employee = st.selectbox(
                        "Selecione um funcionário",
                        employees['id'].tolist(),
                        format_func=lambda x: f"{employees[employees['id'] == x]['nome'].iloc[0]}"
                    )
                    
                    if selected_employee:
                        doc_type = st.radio("Tipo de Documento", ["ASO", "Treinamento"])
                        
                        if doc_type == "ASO":
                            with st.form("adicionar_aso"):
                                arquivo = st.file_uploader("Upload do ASO (PDF)", type=['pdf'])
                                
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    manual_input = st.checkbox("Inserir dados manualmente")
                                
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
                        
                        else:  # Treinamento
                            mostrar_info_normas()
                            
                            with st.form("adicionar_treinamento"):
                                arquivo = st.file_uploader("Upload do Certificado (PDF)", type=['pdf'])
                                
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    manual_input = st.checkbox("Inserir dados manualmente")
                                
                                if arquivo and not manual_input:
                                    with st.spinner("Analisando o PDF do treinamento..."):
                                        pdf_info = employee_manager.analyze_training_pdf(arquivo)
                                        
                                    if pdf_info:
                                        # Informações básicas do treinamento
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            norma = st.text_input("Norma", value=pdf_info['norma'])
                                            modulo = st.text_input("Módulo", value=pdf_info['modulo'])
                                            data = st.date_input("Data do Treinamento", value=pdf_info['data'] if pdf_info['data'] else datetime.now())
                                            tipo_treinamento = st.selectbox("Tipo de Treinamento", 
                                                                          ["inicial", "reciclagem"],
                                                                          index=0 if pdf_info['tipo_treinamento'] == 'inicial' else 1)
                                        with col2:
                                            carga_horaria = st.number_input("Carga Horária (horas)", 
                                                                          value=pdf_info['carga_horaria'] if pdf_info['carga_horaria'] else 0,
                                                                          min_value=0)
                                            vencimento_calculado = employee_manager.calcular_vencimento_treinamento(
                                                data, norma, modulo, tipo_treinamento)
                                            if vencimento_calculado:
                                                vencimento = st.date_input("Data de Vencimento", value=vencimento_calculado)
                                            else:
                                                vencimento = st.date_input("Data de Vencimento")
                                        
                                        # Informações do instrutor e empresa
                                        st.subheader("Informações do Instrutor e Empresa")
                                        col3, col4 = st.columns(2)
                                        with col3:
                                            instrutor = st.text_input("Nome do Instrutor", value=pdf_info['instrutor'])
                                            registro = st.text_input("Registro do Instrutor", value=pdf_info['registro_instrutor'])
                                        with col4:
                                            cnpj_empresa = st.text_input("CNPJ da Empresa", value=pdf_info['cnpj_empresa'])
                                        
                                        # Conteúdo do treinamento
                                        st.subheader("Conteúdo do Treinamento")
                                        topicos = st.text_area("Tópicos Abordados", value=pdf_info['topicos'], height=100)
                                        observacoes = st.text_area("Observações", value=pdf_info['observacoes'], height=100)
                                        
                                        status = st.selectbox("Status", ["Válido", "Vencido", "A vencer"])
                                    else:
                                        st.error("Não foi possível extrair informações do PDF. Por favor, insira os dados manualmente.")
                                        manual_input = True
                                
                                if manual_input:
                                    # Informações básicas do treinamento
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        norma = st.text_input("Norma", help="Ex: NR-10, NR-35, etc.")
                                        modulo = st.text_input("Módulo", help="Módulo ou tipo específico do treinamento")
                                        data = st.date_input("Data do Treinamento")
                                        tipo_treinamento = st.selectbox("Tipo de Treinamento", ["inicial", "reciclagem"])
                                    with col2:
                                        carga_horaria = st.number_input("Carga Horária (horas)", min_value=0)
                                        vencimento = st.date_input("Data de Vencimento")
                                    
                                    # Informações do instrutor e empresa
                                    st.subheader("Informações do Instrutor e Empresa")
                                    col3, col4 = st.columns(2)
                                    with col3:
                                        instrutor = st.text_input("Nome do Instrutor")
                                        registro = st.text_input("Registro do Instrutor")
                                    with col4:
                                        cnpj_empresa = st.text_input("CNPJ da Empresa")
                                    
                                    # Conteúdo do treinamento
                                    st.subheader("Conteúdo do Treinamento")
                                    topicos = st.text_area("Tópicos Abordados", height=100)
                                    observacoes = st.text_area("Observações", height=100)
                                    
                                    status = st.selectbox("Status", ["Válido", "Vencido", "A vencer"])
                                
                                if st.form_submit_button("Adicionar Treinamento"):
                                    if arquivo:
                                        arquivo_id = gdrive_uploader.upload_file(arquivo, f"TREIN_{selected_employee}_{norma}_{data}")
                                        employee_manager.add_training(
                                            selected_employee,
                                            norma,
                                            data,
                                            vencimento,
                                            status,
                                            arquivo_id,
                                            tipo_treinamento,
                                            carga_horaria,
                                            instrutor,
                                            registro,
                                            cnpj_empresa,
                                            topicos,
                                            observacoes
                                        )
                                        st.success("Treinamento adicionado com sucesso!")
                                        st.rerun()
                                    else:
                                        st.error("Por favor, preencha todos os campos obrigatórios")
                else:
                    st.warning("É necessário cadastrar funcionários primeiro")
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
   
