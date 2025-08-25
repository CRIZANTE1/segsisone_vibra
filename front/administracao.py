import streamlit as st
import pandas as pd
import re

from auth.auth_utils import check_permission
from gdrive.matrix_manager import MatrixManager
from gdrive.google_api_manager import GoogleApiManager
from gdrive.config import CENTRAL_DRIVE_FOLDER_ID


@st.cache_data(ttl=300) # Cache de 5 minutos para os dados agregados
def load_aggregated_data():
    """
    Carrega e agrega dados de TODAS as unidades.
    Esta é uma operação custosa e deve ser usada com cuidado.
    """
    st.info("Carregando dados consolidados de todas as unidades. Isso pode levar um momento...")
    
    matrix_manager_global = MatrixManager()
    all_units = matrix_manager_global.get_all_units()

    aggregated_companies = []
    aggregated_employees = []

    for unit in all_units:
        unit_name = unit['nome_unidade']
        spreadsheet_id = unit['spreadsheet_id']
        folder_id = unit['folder_id']
        
        if not spreadsheet_id:
            continue

        try:
            # Cria um manager temporário para cada unidade
            temp_manager = EmployeeManager(spreadsheet_id, folder_id)
            
            # Adiciona a coluna 'unidade' para saber de onde veio o dado
            companies_df = temp_manager.companies_df
            if not companies_df.empty:
                companies_df['unidade'] = unit_name
                aggregated_companies.append(companies_df)

            employees_df = temp_manager.employees_df
            if not employees_df.empty:
                employees_df['unidade'] = unit_name
                aggregated_employees.append(employees_df)
        except Exception as e:
            st.warning(f"Não foi possível carregar dados da unidade '{unit_name}': {e}")

    # Concatena todos os dataframes em um só
    final_companies = pd.concat(aggregated_companies, ignore_index=True) if aggregated_companies else pd.DataFrame()
    final_employees = pd.concat(aggregated_employees, ignore_index=True) if aggregated_employees else pd.DataFrame()

    return final_companies, final_employees
    
def show_admin_page():
    if not check_permission(level='admin'):
        st.stop()

    # --- INÍCIO DO BLOCO DE DEPURAÇÃO ---
    st.subheader("Status de Inicialização (Depuração)")
    
    required_managers = [
        'employee_manager',
        'matrix_manager_unidade', # O manager da matriz de treinamentos
        'nr_analyzer'
    ]
    
    all_managers_ok = True
    for manager_name in required_managers:
        if manager_name in st.session_state:
            st.success(f"✅ Manager '{manager_name}' encontrado na sessão.")
        else:
            st.error(f"❌ ERRO: Manager '{manager_name}' NÃO foi encontrado na sessão. A página não pode ser renderizada.")
            all_managers_ok = False
            
    if not all_managers_ok:
        st.warning("A falha na inicialização de um manager geralmente ocorre por problemas de permissão ou abas faltando na planilha da unidade. Verifique as permissões da conta de serviço e a existência das abas 'funcoes' e 'matriz_treinamentos'.")
        st.stop() # Interrompe a execução se um manager estiver faltando
        
    st.markdown("---")
    # --- FIM DO BLOCO DE DEPURAÇÃO ---


    st.title("🚀 Painel de Administração")

    matrix_manager_global = MatrixManager()
    google_api_manager = GoogleApiManager()

    # --- SEÇÃO DE GERENCIAMENTO DE TENANTS (USUÁRIOS E UNIDADES) ---
    st.header("Gerenciamento Global do Sistema")
    with st.expander("Gerenciar Unidades e Usuários"):
        st.subheader("Unidades Cadastradas")
        units_data = matrix_manager_global.get_all_units()
        if units_data:
            st.dataframe(pd.DataFrame(units_data), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma unidade cadastrada.")

        st.subheader("Usuários Cadastrados")
        users_data = matrix_manager_global.get_all_users()
        if users_data:
            st.dataframe(pd.DataFrame(users_data), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum usuário cadastrado.")
        
        # A lógica de adicionar/provisionar pode ser adicionada aqui se necessário,
        # mas vamos focar em restaurar a matriz primeiro.

    st.markdown("---")

    # --- SEÇÃO DE GERENCIAMENTO DA UNIDADE SELECIONADA ---
    st.header(f"Gerenciamento da Unidade: '{st.session_state.get('unit_name', 'Nenhuma')}'")

    if not st.session_state.get('managers_initialized'):
        st.warning("Selecione uma unidade operacional na barra lateral para gerenciar suas empresas, funcionários e matriz de treinamentos.")
        st.stop()

    # Carrega os managers específicos da unidade da sessão
    employee_manager = st.session_state.employee_manager
    # O MatrixManager para funções/treinamentos também deve ser específico da unidade
    # Vamos assumir que ele é inicializado junto com os outros managers
    matrix_manager_unidade = st.session_state.get('matrix_manager_unidade') # Você precisará adicionar isso à sua inicialização
    if not matrix_manager_unidade:
        # Se não existir, podemos criá-lo aqui, mas o ideal é na inicialização central
        from operations.matrix_manager import MatrixManager as UnitMatrixManager
        st.session_state.matrix_manager_unidade = UnitMatrixManager(st.session_state.spreadsheet_id)
        matrix_manager_unidade = st.session_state.matrix_manager_unidade

    nr_analyzer = st.session_state.nr_analyzer

    # --- UI COM ABAS PARA CADASTRO (LÓGICA RESTAURADA) ---
    tab_empresa, tab_funcionario, tab_matriz, tab_recomendacoes = st.tabs([
        "Gerenciar Empresas", "Gerenciar Funcionários", 
        "Gerenciar Matriz Manualmente", "Assistente de Matriz (IA)" 
    ])

    # --- ABA DE CADASTRO DE EMPRESA ---
    with tab_empresa:
        st.header("Gerenciar Empresas")
        
        # Seção de Cadastro dentro de um expander
        with st.expander("➕ Cadastrar Nova Empresa"):
            with st.form("form_add_company", clear_on_submit=True):
                company_name = st.text_input("Nome da Empresa", placeholder="Digite o nome completo da empresa")
                company_cnpj = st.text_input("CNPJ", placeholder="Digite o CNPJ (apenas números)")
                submitted = st.form_submit_button("Cadastrar Empresa")
                if submitted:
                    if not company_name or not company_cnpj:
                        st.error("Por favor, preencha todos os campos.")
                    else:
                        cnpj_clean = "".join(filter(str.isdigit, company_cnpj))
                        with st.spinner("Cadastrando empresa..."):
                            company_id, message = employee_manager.add_company(company_name, cnpj_clean)
                            if company_id:
                                st.success(f"Sucesso: {message} (ID: {company_id})")
                                st.rerun()
                            else:
                                st.error(f"Falha: {message}")

        st.markdown("---")
        
        # Seção de Gerenciamento de Empresas Existentes
        st.subheader("Empresas Cadastradas")
        
        show_archived_companies = st.toggle("Mostrar empresas arquivadas", key="toggle_companies")
        
        # Filtra o DataFrame com base no toggle
        if show_archived_companies:
            companies_to_show = employee_manager.companies_df
        else:
            companies_to_show = employee_manager.companies_df[employee_manager.companies_df['status'].str.lower() == 'ativo']

        if companies_to_show.empty:
            st.info("Nenhuma empresa para exibir com os filtros atuais.")
        else:
            # Itera sobre as empresas filtradas para exibição
            for index, row in companies_to_show.sort_values('nome').iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 1])
                    col1.markdown(f"**{row['nome']}**")
                    col2.caption(f"CNPJ: {row['cnpj']} | Status: {row['status']}")
                    
                    with col3:
                        # Botão muda de acordo com o status
                        if str(row['status']).lower() == 'ativo':
                            if st.button("Arquivar", key=f"archive_comp_{row['id']}", use_container_width=True):
                                employee_manager.archive_company(row['id'])
                                st.rerun()
                        else:
                            if st.button("Reativar", key=f"unarchive_comp_{row['id']}", type="primary", use_container_width=True):
                                employee_manager.unarchive_company(row['id'])
                                st.rerun()

    # --- ABA DE CADASTRO DE FUNCIONÁRIO ---
    with tab_funcionario:
        st.header("Gerenciar Funcionários")
        
        # Seção de Cadastro dentro de um expander
        with st.expander("➕ Cadastrar Novo Funcionário"):
            # Mostra apenas empresas ativas no selectbox de cadastro
            active_companies = employee_manager.companies_df[employee_manager.companies_df['status'].str.lower() == 'ativo']
            if active_companies.empty:
                st.warning("Nenhuma empresa ativa cadastrada. Por favor, cadastre ou reative uma empresa primeiro.")
            else:
                selected_company_id_add = st.selectbox(
                    "Selecione a Empresa do Funcionário",
                    options=active_companies['id'].tolist(),
                    format_func=lambda x: employee_manager.get_company_name(x),
                    index=None,
                    placeholder="Escolha uma empresa..."
                )
                if selected_company_id_add:
                    with st.form("form_add_employee", clear_on_submit=True):
                        employee_name = st.text_input("Nome do Funcionário")
                        employee_role = st.text_input("Cargo")
                        admission_date = st.date_input("Data de Admissão", value=None, format="DD/MM/YYYY")
                        submitted_employee = st.form_submit_button("Cadastrar Funcionário")
                        if submitted_employee:
                            if not all([employee_name, employee_role, admission_date]):
                                st.error("Por favor, preencha todos os campos do funcionário.")
                            else:
                                with st.spinner("Cadastrando funcionário..."):
                                    employee_id, message = employee_manager.add_employee(
                                        nome=employee_name, cargo=employee_role,
                                        data_admissao=admission_date, empresa_id=selected_company_id_add
                                    )
                                    if employee_id:
                                        st.success(f"Sucesso: {message}")
                                        st.rerun()
                                    else:
                                        st.error(f"Falha: {message}")
        
        st.markdown("---")
        st.subheader("Funcionários Cadastrados")
        
        # Filtro para visualizar funcionários de uma empresa específica
        company_list_filter = employee_manager.companies_df[employee_manager.companies_df['status'].str.lower() == 'ativo']
        selected_company_id_filter = st.selectbox(
            "Filtrar por Empresa",
            options=company_list_filter['id'].tolist(),
            format_func=lambda x: employee_manager.get_company_name(x),
            index=None, placeholder="Selecione uma empresa para ver os funcionários..."
        )
        
        if selected_company_id_filter:
            show_archived_employees = st.toggle("Mostrar funcionários arquivados", key="toggle_employees")
            
            # Usa a função get_employees_by_company com o parâmetro include_archived
            employees_to_show = employee_manager.get_employees_by_company(
                selected_company_id_filter, 
                include_archived=show_archived_employees
            )
                
            if employees_to_show.empty:
                st.info("Nenhum funcionário para exibir com os filtros atuais.")
            else:
                for index, row in employees_to_show.sort_values('nome').iterrows():
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([3, 2, 1])
                        col1.markdown(f"**{row['nome']}**")
                        col2.caption(f"Cargo: {row['cargo']} | Status: {row['status']}")
                        with col3:
                            if str(row['status']).lower() == 'ativo':
                                if st.button("Arquivar", key=f"archive_emp_{row['id']}", use_container_width=True):
                                    employee_manager.archive_employee(row['id'])
                                    st.rerun()
                            else:
                                if st.button("Reativar", key=f"unarchive_emp_{row['id']}", type="primary", use_container_width=True):
                                    employee_manager.unarchive_employee(row['id'])
                                    st.rerun()
                                    
    with tab_matriz:
        st.header("Matriz de Treinamento por Função")
        
        st.subheader("1. Importar Matriz a partir de um Documento (PDF)")
        
        uploaded_matrix_file = st.file_uploader(
            "Selecione um arquivo PDF com a sua matriz de treinamentos",
            type="pdf",
            key="matrix_uploader"
        )

        if uploaded_matrix_file:
            if st.button("Analisar Matriz com IA"):
                with st.spinner("A IA está lendo e interpretando sua matriz..."):
                    extracted_data, message = matrix_manager_unidade.analyze_matrix_pdf(uploaded_matrix_file)
                
                if extracted_data:
                    st.success(message)
                    st.session_state.extracted_matrix_data = extracted_data
                else:
                    st.error(message)

        # Se houver dados extraídos aguardando confirmação, exibe a visualização aprimorada
        if 'extracted_matrix_data' in st.session_state:
            st.markdown("---")
            st.subheader("Dados Extraídos para Confirmação")
            st.info("Revise a relação entre Funções e Treinamentos extraída pela IA. Se estiver correta, clique em 'Salvar'.")
            
            try:
                matrix_to_display = {
                    item.get('funcao', 'Função não identificada'): item.get('normas_obrigatorias', [])
                    for item in st.session_state.extracted_matrix_data
                }
                
                # Exibe o dicionário formatado com st.json
                st.json(matrix_to_display, expanded=True)

                if st.button("Confirmar e Salvar Matriz", type="primary"):
                    with st.spinner("Salvando dados na planilha..."):
                        # A função de salvar ainda recebe a lista original de dicionários
                        added_funcs, added_maps = matrix_manager_unidade.save_extracted_matrix(
                            st.session_state.extracted_matrix_data
                        )
                    
                    st.success(f"Matriz salva! {added_funcs} novas funções e {added_maps} mapeamentos adicionados.")
                    del st.session_state.extracted_matrix_data
                    st.rerun()

            except Exception as e:
                st.error(f"Erro ao exibir ou processar dados extraídos: {e}")
                del st.session_state.extracted_matrix_data

        st.markdown("---")
        
        st.subheader("2. Gerenciamento Manual")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Adicionar/Ver Funções")
            with st.form("form_add_function"):
                func_name = st.text_input("Nome da Nova Função (ex: Soldador)")
                func_desc = st.text_area("Descrição (opcional)")
                submitted_func = st.form_submit_button("Adicionar Função")
                if submitted_func and func_name:
                    func_id, msg = matrix_manager_unidade.add_function(func_name, func_desc)
                    if func_id:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            st.markdown("---")
            

        with col2:
            st.markdown("#### Mapear Treinamentos para Funções")
            if matrix_manager_unidade.functions_df.empty:
                st.warning("Cadastre uma função à esquerda primeiro.")
            else:
                selected_function_id = st.selectbox(
                    "Selecione a Função",
                    options=matrix_manager_unidade.functions_df['id'].tolist(),
                    format_func=lambda id: matrix_manager_unidade.functions_df.loc[matrix_manager_unidade.functions_df['id'] == id, 'nome_funcao'].iloc[0]
                )
                all_norms = sorted(list(employee_manager.nr_config.keys()))
                if 'NR-20' not in all_norms: all_norms.insert(0, 'NR-20')
                
                required_norm = st.selectbox("Selecione o Treinamento Obrigatório", options=all_norms)
                
                if st.button("Mapear Treinamento"):
                    if selected_function_id and required_norm:
                        map_id, msg = matrix_manager_unidade.add_training_to_function(selected_function_id, required_norm)
                        if map_id:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        st.markdown("---")
        st.subheader("Visão Consolidada da Matriz de Treinamentos")
        
        functions_df = matrix_manager_unidade.functions_df
        matrix_df = matrix_manager_unidade.matrix_df
        
        if functions_df.empty:
            st.info("Nenhuma função cadastrada. Adicione uma função acima para começar.")
        else:
            # --- LÓGICA DE CONSOLIDAÇÃO (EXISTENTE) ---
            if not matrix_df.empty:
                mappings_grouped = matrix_df.groupby('id_funcao')['norma_obrigatoria'].apply(list).reset_index()
                
                consolidated_df = pd.merge(
                    functions_df.drop_duplicates(subset=['id']),
                    mappings_grouped,
                    left_on='id',
                    right_on='id_funcao',
                    how='left'
                )
            else:
                consolidated_df = functions_df.drop_duplicates(subset=['id']).copy()
                consolidated_df['norma_obrigatoria'] = [[] for _ in range(len(consolidated_df))]
        
            # --- TRANSFORMAÇÃO PARA DICIONÁRIO E EXIBIÇÃO EM JSON ---
        
            # Garante que a coluna exista e preenche valores nulos (funções sem mapeamentos) com listas vazias
            if 'norma_obrigatoria' not in consolidated_df.columns:
                consolidated_df['norma_obrigatoria'] = [[] for _ in range(len(consolidated_df))]
            consolidated_df['norma_obrigatoria'] = consolidated_df['norma_obrigatoria'].apply(
                lambda x: x if isinstance(x, list) else []
            )
        
            # Cria o dicionário final para exibição
            # A chave será 'nome_funcao', o valor será a lista de 'norma_obrigatoria'
            matrix_to_display = pd.Series(
                consolidated_df.norma_obrigatoria.values,
                index=consolidated_df.nome_funcao
            ).to_dict()
        
            # Ordena as listas de treinamentos dentro do dicionário
            for function_name, trainings in matrix_to_display.items():
                # Se a lista estiver vazia, adiciona a mensagem
                if not trainings:
                    matrix_to_display[function_name] = ["Nenhum treinamento mapeado"]
                else:
                    matrix_to_display[function_name] = sorted(trainings)
        
            # Exibe o dicionário final em formato JSON
            st.json(matrix_to_display, expanded=True)

    with tab_recomendacoes:
        st.header("🤖 Assistente de Matriz de Treinamentos com IA")
        st.info("Selecione uma função e a IA irá analisar sua base de conhecimento para recomendar os treinamentos obrigatórios.")

        if matrix_manager_unidade.functions_df.empty:
            st.warning("Nenhuma função cadastrada. Por favor, cadastre funções na aba 'Gerenciar Matriz Manualmente' primeiro.")
        else:
            selected_function_id = st.selectbox(
                "Selecione a Função para obter recomendações",
                options=matrix_manager_unidade.functions_df['id'].tolist(),
                format_func=lambda id: matrix_manager_unidade.functions_df.loc[matrix_manager_unidade.functions_df['id'] == id, 'nome_funcao'].iloc[0],
                key="rec_func_select"
            )
            
            if st.button("Gerar Recomendações da IA", type="primary"):
                selected_function_name = matrix_manager_unidade.functions_df.loc[matrix_manager_unidade.functions_df['id'] == selected_function_id, 'nome_funcao'].iloc[0]
                with st.spinner(f"A IA está pensando nos treinamentos para '{selected_function_name}'..."):
                    # --- CORREÇÃO: Passamos a instância do nr_analyzer como argumento ---
                    recommendations, message = matrix_manager_unidade.get_training_recommendations_for_function(
                        selected_function_name, 
                        nr_analyzer
                    )
                
                if recommendations is not None:
                    st.session_state.recommendations = recommendations
                    st.session_state.selected_function_for_rec = selected_function_id
                else:
                    st.error(message)

        # Se houver recomendações no session_state, exibe a seção de confirmação
        if 'recommendations' in st.session_state:
            st.markdown("---")
            st.subheader("Recomendações Geradas")
            
            recommendations = st.session_state.recommendations
            
            if not recommendations:
                st.success("A IA não identificou nenhum treinamento de NR obrigatório para esta função.")
            else:
                # Prepara os dados para exibição e seleção
                rec_data = pd.DataFrame(recommendations)
                rec_data['aceitar'] = True # Adiciona uma coluna de checkbox, todos marcados por padrão
                
                st.write("Marque os treinamentos que você deseja adicionar à matriz para esta função:")
                
                edited_df = st.data_editor(
                    rec_data,
                    column_config={
                        "aceitar": st.column_config.CheckboxColumn("Aceitar?", default=True),
                        "treinamento_recomendado": "Treinamento",
                        "justificativa_normativa": "Justificativa da IA (não será salvo)"
                    },
                    use_container_width=True,
                    hide_index=True,
                    key="rec_editor"
                )

                if st.button("Salvar Mapeamentos Selecionados"):
                    # Filtra apenas as recomendações que o usuário deixou marcadas
                    accepted_recommendations = edited_df[edited_df['aceitar']]
                    norms_to_add = accepted_recommendations['treinamento_recomendado'].tolist()
                    
                    if not norms_to_add:
                        st.warning("Nenhum treinamento foi selecionado para salvar.")
                    else:
                        function_id_to_save = st.session_state.selected_function_for_rec
                        with st.spinner("Salvando mapeamentos..."):
                            success, message = matrix_manager_unidade.update_function_mappings(function_id_to_save, norms_to_add)
                        
                        if success:
                            st.success(message)
                            # Limpa o estado para resetar a interface
                            del st.session_state.recommendations
                            del st.session_state.selected_function_for_rec
                            st.rerun()
                        else:
                            st.error(message)
