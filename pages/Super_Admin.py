import streamlit as st
import pandas as pd
from auth.auth_utils import check_permission, get_user_role
from operations.matrix_manager import MatrixManager
from gdrive.google_api_manager import GoogleApiManager
from gdrive.config import CENTRAL_DRIVE_FOLDER_ID

def show_super_admin_page():
    """
    Renderiza a página de super administração, acessível apenas por admins.
    """
    st.title("🚀 Painel de Super Administração")

    # Verificação de permissão rigorosa no início da página
    if not check_permission(level='admin'):
        st.stop() # Interrompe a execução se o usuário não for admin

    # Garante que apenas admins globais possam provisionar novas unidades
    is_global_admin = st.session_state.get('unit_name') == 'Global'

    # --- Sidebar para seleção de unidade (apenas para admins globais) ---
    if is_global_admin:
        st.sidebar.header("Trocar Contexto de Unidade")
        matrix_manager = MatrixManager()
        all_units = matrix_manager.get_all_units()
        
        unit_options = {"Global": {"nome_unidade": "Global", "spreadsheet_id": None, "folder_id": None}}
        for unit in all_units:
            unit_options[unit['nome_unidade']] = unit

        selected_unit_name = st.sidebar.selectbox(
            "Selecione uma Unidade Operacional:",
            options=list(unit_options.keys()),
            index=list(unit_options.keys()).index(st.session_state.get('unit_name', 'Global')),
            key="super_admin_unit_selector"
        )

        if st.sidebar.button("Aplicar Seleção"):
            selected_unit_info = unit_options[selected_unit_name]
            st.session_state.unit_name = selected_unit_info['nome_unidade']
            st.session_state.spreadsheet_id = selected_unit_info['spreadsheet_id']
            st.session_state.folder_id = selected_unit_info['folder_id']
            st.session_state.authenticated = True # Re-autentica a sessão com o novo contexto
            st.rerun() # Recarrega a página para aplicar o novo contexto
        st.sidebar.markdown("---")

    tab1, tab2 = st.tabs(["🏢 Gestão de Unidades", "➕ Provisionar Nova Unidade"])

    with tab1:
        render_units_management()

    with tab2:
        if is_global_admin:
            render_provision_new_unit()
        else:
            st.warning("Apenas Administradores Globais podem provisionar novas unidades.")

def render_units_management():
    """
    Renderiza a aba de gerenciamento de unidades.
    """
    st.header("Unidades Operacionais do SEGMA-SIS")
    
    try:
        matrix_manager = MatrixManager()
        units_df = matrix_manager.units_df

        if units_df.empty:
            st.info("Nenhuma unidade foi provisionada ainda.")
            return

        # Formatação para exibição
        display_df = units_df.copy()
        display_df['spreadsheet_link'] = display_df['spreadsheet_id'].apply(
            lambda id: f"https://docs.google.com/spreadsheets/d/{id}" if id else "N/A"
        )
        display_df['folder_link'] = display_df['folder_id'].apply(
            lambda id: f"https://drive.google.com/drive/folders/{id}" if id else "N/A"
        )

        st.dataframe(
            display_df,
            column_config={
                "id": st.column_config.TextColumn("ID da Unidade"),
                "nome_unidade": st.column_config.TextColumn("Nome da Unidade"),
                "spreadsheet_id": st.column_config.TextColumn("ID da Planilha"),
                "folder_id": st.column_config.TextColumn("ID da Pasta"),
                "spreadsheet_link": st.column_config.LinkColumn("Link da Planilha", display_text="Abrir Planilha 🔗"),
                "folder_link": st.column_config.LinkColumn("Link da Pasta", display_text="Abrir Pasta 📂"),
            },
            hide_index=True,
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Erro ao carregar as unidades: {e}")

def render_provision_new_unit():
    """
    Renderiza a aba para provisionar uma nova unidade.
    """
    st.header("Provisionar Nova Unidade (Tenant)")

    with st.form("provision_form"):
        unit_name = st.text_input("Nome da Nova Unidade", placeholder="Ex: SEGMA-SIS Filial RJ")
        submitted = st.form_submit_button("🚀 Provisionar Agora")

        if submitted and unit_name:
            provision_new_unit(unit_name)

def provision_new_unit(unit_name: str):
    """
    Executa o fluxo completo de criação de uma nova unidade (tenant).
    """
    with st.spinner(f"Provisionando a unidade '{unit_name}'... Este processo pode levar um minuto."):
        try:
            api_manager = GoogleApiManager()
            matrix_manager = MatrixManager()

            # 1. Criar a pasta no Drive
            st.write("1/4 - Criando pasta no Google Drive...")
            new_folder_id = api_manager.create_folder(unit_name, CENTRAL_DRIVE_FOLDER_ID)
            if not new_folder_id:
                st.error("Falha ao criar a pasta no Google Drive. Abortando.")
                return

            # 2. Criar a Planilha Google
            st.write("2/4 - Criando a Planilha Google...")
            spreadsheet_name = f"SEGMA-SIS - {unit_name}"
            new_spreadsheet = api_manager.create_spreadsheet(spreadsheet_name, new_folder_id)
            if not new_spreadsheet:
                st.error("Falha ao criar a Planilha Google. Abortando.")
                # Idealmente, aqui teríamos uma lógica para deletar a pasta criada
                return
            new_spreadsheet_id = new_spreadsheet.id

            # 3. Popular a planilha com as abas e cabeçalhos
            st.write("3/4 - Configurando as abas da planilha a partir do template...")
            api_manager.setup_sheets_from_config(new_spreadsheet, "sheets_config.yaml")

            # 4. Registrar a nova unidade na Planilha Matriz
            st.write("4/4 - Registrando a nova unidade no sistema...")
            new_unit_data = [unit_name, new_spreadsheet_id, new_folder_id]
            unit_id = matrix_manager.add_unit(new_unit_data)
            if not unit_id:
                st.error("Falha ao registrar a nova unidade na Planilha Matriz.")
                # Lógica de rollback seria ideal aqui
                return

            st.success(f"✅ Unidade '{unit_name}' provisionada com sucesso!")
            st.balloons()
            
            st.markdown(f"""
            ### Detalhes da Nova Unidade:
            - **Nome:** `{unit_name}`
            - **ID do Registro:** `{unit_id}`
            - **ID da Planilha:** `{new_spreadsheet_id}`
            - **Link da Planilha:** [Abrir Planilha](https://docs.google.com/spreadsheets/d/{new_spreadsheet_id})
            - **ID da Pasta:** `{new_folder_id}`
            - **Link da Pasta:** [Abrir Pasta no Drive](https://drive.google.com/drive/folders/{new_folder_id})

            **Próximos Passos:**
            1.  Acesse a `Planilha Matriz`.
            2.  Vá para a aba `usuarios`.
            3.  Adicione um novo usuário e, na coluna `unidade_associada`, insira `{unit_name}` para dar a ele acesso a esta nova unidade.
            """)

        except Exception as e:
            st.error(f"Ocorreu um erro inesperado durante o provisionamento: {e}")

# Ponto de entrada da página
if __name__ == "__main__":
    # Este check garante que a página só renderize se o usuário for admin
    if 'role' in st.session_state and st.session_state.role == 'admin':
        show_super_admin_page()
    else:
        st.error("Você não tem permissão para acessar esta página.")
        st.info("Faça login como um administrador para visualizar este painel.")
