import streamlit as st
from datetime import date
import pandas as pd
import collections.abc 

from operations.employee import EmployeeManager
from operations.matrix_manager import MatrixManager
from ui.metrics import display_minimalist_metrics
from analysis.nr_analyzer import NRAnalyzer 
from auth.auth_utils import check_admin_permission, is_user_logged_in

st.set_page_config(page_title="Administração", page_icon="⚙️", layout="wide")

st.title("⚙️ Painel de Administração")

# --- Verificação de Segurança ---
if not is_user_logged_in():
    st.warning("Por favor, faça login para acessar esta página.")
    st.stop()
if not check_admin_permission():
    st.error("Você não tem permissão para acessar o painel de administração.")
    st.stop()

# --- Instanciação Padronizada dos Gerenciadores ---
@st.cache_resource
def get_admin_managers():
    """Instancia os gerenciadores necessários para a página de Administração."""
    return EmployeeManager(), MatrixManager(), NRAnalyzer()

employee_manager, matrix_manager, nr_analyzer = get_admin_managers()

# --- Exibição das Métricas ---
st.header("Visão Geral das Pendências")
display_minimalist_metrics(employee_manager)

# --- UI com Abas para Cadastro ---
tab_empresa, tab_funcionario, tab_matriz, tab_recomendacoes = st.tabs([
    "Cadastrar Empresa", "Cadastrar Funcionário", 
    "Gerenciar Matriz Manualmente", "Assistente de Matriz (IA)" 
])

# --- ABA DE CADASTRO DE EMPRESA ---
with tab_empresa:
    st.header("Formulário de Cadastro de Empresa")
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
                        st.cache_resource.clear() # Limpa o cache para atualizar os selectboxes
                        st.rerun()
                    else:
                        st.error(f"Falha: {message}")

# --- ABA DE CADASTRO DE FUNCIONÁRIO ---
with tab_funcionario:
    st.header("Formulário de Cadastro de Funcionário")
    if employee_manager.companies_df.empty:
        st.warning("Nenhuma empresa cadastrada. Por favor, cadastre uma empresa primeiro.")
    else:
        company_list = employee_manager.companies_df.copy()
        selected_company_id = st.selectbox(
            "Selecione a Empresa do Funcionário",
            options=company_list['id'].tolist(),
            format_func=lambda x: employee_manager.get_company_name(x),
            index=None,
            placeholder="Escolha uma empresa..."
        )
        if selected_company_id:
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
                                data_admissao=admission_date, empresa_id=selected_company_id
                            )
                            if employee_id:
                                st.success(f"Sucesso: {message} (ID: {employee_id})")
                            else:
                                st.error(f"Falha: {message}")
                                
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
                extracted_data, message = matrix_manager.analyze_matrix_pdf(uploaded_matrix_file)
            
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
                    added_funcs, added_maps = matrix_manager.save_extracted_matrix(
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
                func_id, msg = matrix_manager.add_function(func_name, func_desc)
                if func_id:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        st.markdown("---")
        

    with col2:
        st.markdown("#### Mapear Treinamentos para Funções")
        if matrix_manager.functions_df.empty:
            st.warning("Cadastre uma função à esquerda primeiro.")
        else:
            selected_function_id = st.selectbox(
                "Selecione a Função",
                options=matrix_manager.functions_df['id'].tolist(),
                format_func=lambda id: matrix_manager.functions_df.loc[matrix_manager.functions_df['id'] == id, 'nome_funcao'].iloc[0]
            )
            all_norms = sorted(list(employee_manager.nr_config.keys()))
            if 'NR-20' not in all_norms: all_norms.insert(0, 'NR-20')
            
            required_norm = st.selectbox("Selecione o Treinamento Obrigatório", options=all_norms)
            
            if st.button("Mapear Treinamento"):
                if selected_function_id and required_norm:
                    map_id, msg = matrix_manager.add_training_to_function(selected_function_id, required_norm)
                    if map_id:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    st.markdown("---")
    st.subheader("Visão Consolidada da Matriz de Treinamentos")
    
    functions_df = matrix_manager.functions_df
    matrix_df = matrix_manager.matrix_df
    
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

    if matrix_manager.functions_df.empty:
        st.warning("Nenhuma função cadastrada. Por favor, cadastre funções na aba 'Gerenciar Matriz Manualmente' primeiro.")
    else:
        selected_function_id = st.selectbox(
            "Selecione a Função para obter recomendações",
            options=matrix_manager.functions_df['id'].tolist(),
            format_func=lambda id: matrix_manager.functions_df.loc[matrix_manager.functions_df['id'] == id, 'nome_funcao'].iloc[0],
            key="rec_func_select"
        )
        
        if st.button("Gerar Recomendações da IA", type="primary"):
            selected_function_name = matrix_manager.functions_df.loc[matrix_manager.functions_df['id'] == selected_function_id, 'nome_funcao'].iloc[0]
            with st.spinner(f"A IA está pensando nos treinamentos para '{selected_function_name}'..."):
                # --- CORREÇÃO: Passamos a instância do nr_analyzer como argumento ---
                recommendations, message = matrix_manager.get_training_recommendations_for_function(
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
                        success, message = matrix_manager.update_function_mappings(function_id_to_save, norms_to_add)
                    
                    if success:
                        st.success(message)
                        # Limpa o estado para resetar a interface
                        del st.session_state.recommendations
                        del st.session_state.selected_function_for_rec
                        st.rerun()
                    else:
                        st.error(message)
