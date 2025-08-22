import streamlit as st
from auth.auth_utils import check_permission, get_user_role
from gdrive.matrix_manager import MatrixManager
from gdrive.google_api_manager import GoogleApiManager
from gdrive.config import CENTRAL_DRIVE_FOLDER_ID

def show_admin_page():
    st.set_page_config(page_title="Super Admin", layout="wide")

    if not check_permission(level='admin'): st.stop()

    st.title("🚀 Painel de Super Administração")

    # Placeholder for the content of the Super Admin page
    st.write("Aqui você pode gerenciar usuários, unidades e provisionamento.")

    # Example of how to use the managers (to be expanded later)
    matrix_manager = MatrixManager()
    google_api_manager = GoogleApiManager()

    st.subheader("Gerenciamento de Unidades")
    # Add unit creation form, listing units, etc.

    st.subheader("Gerenciamento de Usuários")
    # Add user management features

    st.subheader("Provisionamento de Novas Unidades")
    # Add functionality to provision new units (create spreadsheets, folders, update matrix)
