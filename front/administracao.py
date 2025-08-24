import streamlit as st
import pandas as pd
from auth.auth_utils import check_permission, get_user_role
from gdrive.matrix_manager import MatrixManager
from gdrive.google_api_manager import GoogleApiManager
from gdrive.config import CENTRAL_DRIVE_FOLDER_ID

def show_admin_page(matrix_manager: MatrixManager):
    if not check_permission(level='admin'):
        st.stop()

    if not matrix_manager:
        st.warning("Matrix manager not available.")
        return

    st.title("🚀 Painel de Super Administração")

    # Placeholder for the content of the Super Admin page
    st.write("Aqui você pode gerenciar usuários, unidades e provisionamento.")

    google_api_manager = GoogleApiManager() # GoogleApiManager is a utility, can be instantiated directly

    st.subheader("Gerenciamento de Unidades")

    with st.expander("Adicionar Nova Unidade", expanded=False):
        with st.form("add_unit_form", clear_on_submit=True):
            new_unit_name = st.text_input("Nome da Nova Unidade", help="Nome único para identificar a unidade operacional.")
            new_spreadsheet_id = st.text_input("ID da Planilha Google (existente)", help="ID da planilha Google Sheets já criada para esta unidade.")
            new_folder_id = st.text_input("ID da Pasta Google Drive (existente)", help="ID da pasta no Google Drive já criada para esta unidade.")
            
            submitted = st.form_submit_button("Adicionar Unidade")

            if submitted:
                if new_unit_name and new_spreadsheet_id and new_folder_id:
                    # Verifica se a unidade já existe
                    if matrix_manager.get_unit_info(new_unit_name):
                        st.error(f"A unidade '{new_unit_name}' já existe.")
                    else:
                        unit_data = [new_unit_name, new_spreadsheet_id, new_folder_id]
                        if matrix_manager.add_unit(unit_data):
                            st.success(f"Unidade '{new_unit_name}' adicionada com sucesso!")
                            st.rerun()
                        else:
                            st.error("Erro ao adicionar unidade. Verifique os logs.")
                else:
                    st.warning("Por favor, preencha todos os campos para adicionar uma nova unidade.")

    st.subheader("Unidades Cadastradas")
    units_data = matrix_manager.get_all_units()
    if units_data:
        units_df = pd.DataFrame(units_data)
        st.dataframe(units_df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma unidade cadastrada ainda.")

    st.subheader("Gerenciamento de Usuários")

    with st.expander("Adicionar Novo Usuário", expanded=False):
        with st.form("add_user_form", clear_on_submit=True):
            new_user_email = st.text_input("E-mail do Usuário")
            new_user_name = st.text_input("Nome do Usuário")
            new_user_role = st.selectbox("Função", ["viewer", "editor", "admin"])
            
            all_units = matrix_manager.get_all_units()
            unit_names = [unit['nome_unidade'] for unit in all_units] + ['*'] # Add global admin option
            selected_unit_for_user = st.selectbox("Unidade Associada", unit_names)

            submitted_user = st.form_submit_button("Adicionar Usuário")

            if submitted_user:
                if new_user_email and new_user_name and new_user_role and selected_unit_for_user:
                    user_data = [new_user_email, new_user_name, new_user_role, selected_unit_for_user]
                    if matrix_manager.get_user_info(new_user_email):
                        st.error(f"O e-mail '{new_user_email}' já está cadastrado.")
                    else:
                        if matrix_manager.add_user(user_data):
                            st.success(f"Usuário '{new_user_name}' adicionado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Erro ao adicionar usuário. Verifique os logs.")
                else:
                    st.warning("Por favor, preencha todos os campos para adicionar um novo usuário.")

    st.subheader("Usuários Cadastrados")
    users_data = matrix_manager.users_df.to_dict(orient='records') # Assuming users_df is accessible and loaded
    if users_data:
        users_df = pd.DataFrame(users_data)
        st.dataframe(users_df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum usuário cadastrado ainda.")

    st.subheader("Provisionamento de Novas Unidades")

    with st.expander("Provisionar Nova Unidade (Criar Planilha e Pasta)", expanded=False):
        with st.form("provision_unit_form", clear_on_submit=True):
            new_provision_unit_name = st.text_input("Nome da Nova Unidade para Provisionamento", help="Nome da unidade a ser criada no Google Drive e na Planilha Matriz.")
            
            provision_submitted = st.form_submit_button("Provisionar Unidade")

            if provision_submitted:
                if new_provision_unit_name:
                    if matrix_manager.get_unit_info(new_provision_unit_name):
                        st.error(f"A unidade '{new_provision_unit_name}' já existe na Planilha Matriz.")
                    else:
                        with st.spinner(f"Provisionando unidade '{new_provision_unit_name}'..."):
                            try:
                                # 1. Criar pasta no Google Drive
                                st.info("Criando pasta no Google Drive...")
                                new_folder_id = google_api_manager.create_folder(new_provision_unit_name, CENTRAL_DRIVE_FOLDER_ID)
                                if not new_folder_id:
                                    st.error("Falha ao criar pasta no Google Drive.")
                                    return
                                st.success(f"Pasta criada: {new_folder_id}")

                                # 2. Criar planilha Google Sheets
                                st.info("Criando planilha Google Sheets...")
                                new_spreadsheet = google_api_manager.create_spreadsheet(new_provision_unit_name, new_folder_id)
                                if not new_spreadsheet:
                                    st.error("Falha ao criar planilha Google Sheets.")
                                    return
                                new_spreadsheet_id = new_spreadsheet.id
                                st.success(f"Planilha criada: {new_spreadsheet_id}")

                                # 3. Configurar abas da planilha a partir de sheets_config.yaml
                                st.info("Configurando abas da planilha...")
                                google_api_manager.setup_sheets_from_config(new_spreadsheet, "sheets_config.yaml")
                                st.success("Abas configuradas com sucesso.")

                                # 4. Adicionar unidade à Planilha Matriz
                                st.info("Adicionando unidade à Planilha Matriz...")
                                unit_data = [new_provision_unit_name, new_spreadsheet_id, new_folder_id]
                                if matrix_manager.add_unit(unit_data):
                                    st.success(f"Unidade '{new_provision_unit_name}' provisionada e adicionada à Planilha Matriz com sucesso!")
                                    st.rerun()
                                else:
                                    st.error("Falha ao adicionar unidade à Planilha Matriz.")

                            except Exception as e:
                                st.error(f"Erro durante o provisionamento da unidade: {e}")
                else:
                    st.warning("Por favor, insira o nome da nova unidade para provisionar.")
