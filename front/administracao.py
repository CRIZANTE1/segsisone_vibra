import streamlit as st
import pandas as pd
from gdrive.matrix_manager import MatrixManager as GlobalMatrixManager
from operations.employee import EmployeeManager
from auth.auth_utils import check_permission

@st.cache_data(ttl=300)
def load_aggregated_data():
    """
    Carrega e agrega dados de TODAS as unidades.
    """
    progress_bar = st.progress(0, text="Carregando dados consolidados de todas as unidades...")
    
    matrix_manager_global = GlobalMatrixManager()
    all_units = matrix_manager_global.get_all_units()

    aggregated_companies = []
    aggregated_employees = []
    
    total_units = len(all_units)
    for i, unit in enumerate(all_units):
        unit_name = unit.get('nome_unidade')
        spreadsheet_id = unit.get('spreadsheet_id')
        folder_id = unit.get('folder_id')
        
        progress_bar.progress((i + 1) / total_units, text=f"Lendo unidade: {unit_name}...")
        
        if not spreadsheet_id or not unit_name:
            continue

        try:
            temp_manager = EmployeeManager(spreadsheet_id, folder_id)
            
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

    progress_bar.empty()
    final_companies = pd.concat(aggregated_companies, ignore_index=True) if aggregated_companies else pd.DataFrame()
    final_employees = pd.concat(aggregated_employees, ignore_index=True) if aggregated_employees else pd.DataFrame()

    return final_companies, final_employees

# --- FUNÇÃO PRINCIPAL DA PÁGINA ---
def show_admin_page():
    if not check_permission(level='admin'):
        st.stop()

    st.title("🚀 Painel de Administração")

    is_global_view = st.session_state.get('unit_name') == 'Global'

    if is_global_view:
        st.header("Visão Global (Todas as Unidades)")
        st.info("Este modo é para consulta consolidada. Para cadastrar ou gerenciar detalhes, selecione uma unidade na barra lateral.")
        
        all_companies, all_employees = load_aggregated_data()
        
        st.subheader("Todas as Empresas Cadastradas")
        if not all_companies.empty:
            st.dataframe(all_companies[['unidade', 'nome', 'cnpj', 'status']], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma empresa encontrada em todas as unidades.")
            
        st.subheader("Todos os Funcionários Cadastrados")
        if not all_employees.empty:
            st.dataframe(all_employees[['unidade', 'nome', 'cargo', 'status']], use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum funcionário encontrado em todas as unidades.")
        
        st.stop() # Interrompe a execução aqui para o modo global

    # --- CÓDIGO PARA VISÃO DE UNIDADE ESPECÍFICA ---
    unit_name = st.session_state.get('unit_name', 'Nenhuma')
    st.header(f"Gerenciamento da Unidade: '{unit_name}'")

    if not st.session_state.get('managers_initialized'):
        st.warning("Aguardando a inicialização dos dados da unidade...")
        st.stop()

    employee_manager = st.session_state.employee_manager
    matrix_manager_unidade = st.session_state.matrix_manager_unidade
    nr_analyzer = st.session_state.nr_analyzer

    tab_empresa, tab_funcionario, tab_matriz, tab_recomendacoes = st.tabs([
        "Gerenciar Empresas", "Gerenciar Funcionários", 
        "Gerenciar Matriz Manualmente", "Assistente de Matriz (IA)"
    ])

    with tab_empresa:
        with st.expander("➕ Cadastrar Nova Empresa"):
            with st.form("form_add_company", clear_on_submit=True):
                company_name = st.text_input("Nome da Empresa", placeholder="Digite o nome completo da empresa")
                company_cnpj = st.text_input("CNPJ", placeholder="Digite o CNPJ")
                submitted = st.form_submit_button("Cadastrar Empresa")
                if submitted and company_name and company_cnpj:
                    with st.spinner("Cadastrando..."):
                        company_id, message = employee_manager.add_company(company_name, company_cnpj)
                        if company_id:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)

        st.subheader("Empresas Cadastradas na Unidade")
        show_archived = st.toggle("Mostrar empresas arquivadas", key="toggle_companies")
        
        df_to_show = employee_manager.companies_df if show_archived else employee_manager.companies_df[employee_manager.companies_df['status'].str.lower() == 'ativo']
        
        if df_to_show.empty:
            st.info("Nenhuma empresa para exibir.")
        else:
            for _, row in df_to_show.sort_values('nome').iterrows():
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 1])
                    col1.markdown(f"**{row['nome']}**")
                    col2.caption(f"CNPJ: {row['cnpj']} | Status: {row['status']}")
                    with col3:
                        if str(row['status']).lower() == 'ativo':
                            if st.button("Arquivar", key=f"archive_comp_{row['id']}", use_container_width=True):
                                employee_manager.archive_company(row['id'])
                                st.rerun()
                        else:
                            if st.button("Reativar", key=f"unarchive_comp_{row['id']}", type="primary", use_container_width=True):
                                employee_manager.unarchive_company(row['id'])
                                st.rerun()

    with tab_funcionario:
        with st.expander("➕ Cadastrar Novo Funcionário"):
            active_companies = employee_manager.companies_df[employee_manager.companies_df['status'].str.lower() == 'ativo']
            if active_companies.empty:
                st.warning("Cadastre ou reative uma empresa primeiro.")
            else:
                company_id = st.selectbox("Selecione a Empresa", options=active_companies['id'], format_func=employee_manager.get_company_name)
                with st.form("form_add_employee", clear_on_submit=True):
                    name = st.text_input("Nome do Funcionário")
                    role = st.text_input("Cargo")
                    adm_date = st.date_input("Data de Admissão")
                    if st.form_submit_button("Cadastrar"):
                        if all([name, role, adm_date, company_id]):
                            _, msg = employee_manager.add_employee(name, role, adm_date, company_id)
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error("Todos os campos são obrigatórios.")
        
        st.subheader("Funcionários Cadastrados na Unidade")
        company_filter = st.selectbox("Filtrar por Empresa", options=['Todas'] + employee_manager.companies_df['id'].tolist(), format_func=lambda x: 'Todas' if x == 'Todas' else employee_manager.get_company_name(x))
        
        employees_to_show = employee_manager.employees_df
        if company_filter != 'Todas':
            employees_to_show = employees_to_show[employees_to_show['empresa_id'] == str(company_filter)]

        if employees_to_show.empty:
            st.info("Nenhum funcionário encontrado para a empresa selecionada.")
        else:
            for _, row in employees_to_show.sort_values('nome').iterrows():
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
        
        with st.expander("🤖 Importar Matriz com IA (via PDF)"):
            uploaded_file = st.file_uploader("Selecione um PDF com a matriz", type="pdf", key="matrix_uploader")
            if uploaded_file and st.button("Analisar Matriz com IA"):
                with st.spinner("Analisando..."):
                    data, msg = matrix_manager_unidade.analyze_matrix_pdf(uploaded_file)
                if data:
                    st.success(msg)
                    st.session_state.extracted_matrix_data = data
                else:
                    st.error(msg)

        if 'extracted_matrix_data' in st.session_state:
            st.info("Revise os dados extraídos e salve se estiverem corretos.")
            st.json(st.session_state.extracted_matrix_data)
            if st.button("Confirmar e Salvar Matriz", type="primary"):
                with st.spinner("Salvando..."):
                    funcs, maps = matrix_manager_unidade.save_extracted_matrix(st.session_state.extracted_matrix_data)
                st.success(f"Matriz salva! {funcs} novas funções e {maps} mapeamentos adicionados.")
                del st.session_state.extracted_matrix_data
                st.rerun()

        st.subheader("Gerenciamento Manual")
        col1, col2 = st.columns(2)
        with col1:
            with st.form("form_add_function"):
                st.markdown("#### Adicionar Função")
                func_name = st.text_input("Nome da Nova Função")
                if st.form_submit_button("Adicionar"):
                    if func_name:
                        _, msg = matrix_manager_unidade.add_function(func_name, "")
                        st.success(msg)
                        st.rerun()
        with col2:
            with st.form("form_map_training"):
                st.markdown("#### Mapear Treinamento para Função")
                if not matrix_manager_unidade.functions_df.empty:
                    func_id = st.selectbox("Selecione a Função", options=matrix_manager_unidade.functions_df['id'], format_func=lambda id: matrix_manager_unidade.functions_df[matrix_manager_unidade.functions_df['id'] == id]['nome_funcao'].iloc[0])
                    norm = st.selectbox("Selecione o Treinamento", options=sorted(list(employee_manager.nr_config.keys())))
                    if st.form_submit_button("Mapear"):
                        _, msg = matrix_manager_unidade.add_training_to_function(func_id, norm)
                        st.success(msg)
                        st.rerun()
                else:
                    st.warning("Cadastre uma função primeiro.")
                                    
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
