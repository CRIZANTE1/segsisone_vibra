import streamlit as st
from datetime import datetime, date
from operations.employee import EmployeeManager
from gdrive.gdrive_upload import GoogleDriveUploader
import pandas as pd
from auth.auth_utils import check_admin_permission

# ... (funções mostrar_info_normas, highlight_expired, process_...pdf sem alterações) ...
def mostrar_info_normas():
    with st.expander("Informações sobre Normas Regulamentadoras"):
        st.markdown("...")

def highlight_expired(row):
    today = datetime.now().date()
    vencimento_val = row.get('vencimento')
    if isinstance(vencimento_val, date) and vencimento_val < today:
        return ['background-color: #FFCDD2'] * len(row)
    return [''] * len(row)

def process_aso_pdf():
    if st.session_state.get('aso_uploader_tab'):
        employee_manager = st.session_state.employee_manager
        with st.spinner("Analisando PDF do ASO..."):
            st.session_state.aso_anexo_para_salvar = st.session_state.aso_uploader_tab
            st.session_state.aso_funcionario_para_salvar = st.session_state.aso_employee_add
            st.session_state.aso_info_para_salvar = employee_manager.analyze_aso_pdf(st.session_state.aso_uploader_tab)

def process_training_pdf():
    if st.session_state.get('training_uploader_tab'):
        employee_manager = st.session_state.employee_manager
        with st.spinner("Analisando PDF do Treinamento..."):
            st.session_state.training_anexo_para_salvar = st.session_state.training_uploader_tab
            st.session_state.training_funcionario_para_salvar = st.session_state.training_employee_add
            st.session_state.training_info_para_salvar = employee_manager.analyze_training_pdf(st.session_state.training_uploader_tab)

def front_page():
    if 'employee_manager' not in st.session_state:
        st.session_state.employee_manager = EmployeeManager()
    
    employee_manager = st.session_state.employee_manager
    employee_manager.load_data()
    
    # Instanciamos o uploader aqui para que esteja disponível em todo o escopo da página
    gdrive_uploader = GoogleDriveUploader()
    
    st.title("Gestão de Documentação de Contratada")
    
    selected_company = None
    if not employee_manager.companies_df.empty:
        df = employee_manager.companies_df.astype({'id': 'str'})
        selected_company = st.selectbox(
            "Selecione uma empresa",
            df['id'].tolist(),
            format_func=lambda x: f"{df[df['id'] == x]['nome'].iloc[0]} - {df[df['id'] == x]['cnpj'].iloc[0]}",
            key="company_select"
        )
    
    tab_dados, tab_aso, tab_treinamento = st.tabs(["**Situação dos Funcionários**", "**Adicionar ASO**", "**Adicionar Treinamento**"])

    with tab_dados:
        # ... (código da tab_dados sem alterações) ...
        if selected_company:
            # ... (código do expander sem alterações) ...
            pass
        else:
            # ...
            pass

    # --- ABA ADICIONAR ASO COM CORREÇÃO ---
    with tab_aso:
        if selected_company:
            if check_admin_permission():
                st.subheader("Adicionar Novo ASO")
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="aso_employee_add")
                    st.file_uploader("Anexar ASO (PDF)", type=['pdf'], key="aso_uploader_tab", on_change=process_aso_pdf)
                    
                    if st.session_state.get('aso_info_para_salvar'):
                        aso_info = st.session_state.aso_info_para_salvar
                        if aso_info and aso_info.get('data_aso'):
                            with st.container(border=True):
                                st.markdown("### Confirme as Informações Extraídas")
                                # ... (exibição dos dados extraídos) ...
                                if st.button("Confirmar e Salvar ASO", type="primary"):
                                    with st.spinner("Salvando ASO..."):
                                        anexo_aso = st.session_state.aso_anexo_para_salvar
                                        selected_employee_aso = st.session_state.aso_funcionario_para_salvar
                                        
                                        # Passo 1: Tenta fazer o upload do arquivo
                                        arquivo_id = gdrive_uploader.upload_file(anexo_aso, f"ASO_{selected_employee_aso}_{aso_info['data_aso']}")
                                        
                                        # Passo 2: Se o upload deu certo, tenta salvar na planilha
                                        if arquivo_id:
                                            aso_id = employee_manager.add_aso(
                                                id=selected_employee_aso,
                                                arquivo_id=arquivo_id,
                                                **aso_info
                                            )
                                            # Passo 3: Verifica se a adição à planilha deu certo
                                            if aso_id:
                                                st.success(f"ASO adicionado com sucesso! ID: {aso_id}")
                                                # Limpa o estado para evitar re-envio
                                                for key in ['aso_info_para_salvar', 'aso_anexo_para_salvar', 'aso_funcionario_para_salvar']:
                                                    if key in st.session_state:
                                                        del st.session_state[key]
                                                st.rerun()
                                            else:
                                                st.error("Falha ao salvar os dados na planilha. O anexo foi criado, mas os dados não foram registrados.")
                                        else:
                                            st.error("Falha ao fazer o upload do anexo para o Google Drive. Verifique as permissões.")
                        else:
                            st.error("Não foi possível extrair informações válidas do PDF.")
                            if 'aso_info_para_salvar' in st.session_state:
                                del st.session_state.aso_info_para_salvar
                else: st.warning("Cadastre funcionários nesta empresa primeiro.")
            else: st.error("Você não tem permissão para esta ação.")
        else: st.info("Selecione uma empresa na primeira aba.")

    # --- ABA ADICIONAR TREINAMENTO COM CORREÇÃO ---
    with tab_treinamento:
        if selected_company:
            if check_admin_permission():
                st.subheader("Adicionar Novo Treinamento")
                mostrar_info_normas()
                current_employees = employee_manager.get_employees_by_company(selected_company)
                if not current_employees.empty:
                    st.selectbox("Funcionário", current_employees['id'].tolist(), format_func=employee_manager.get_employee_name, key="training_employee_add")
                    st.file_uploader("Anexar Certificado (PDF)", type=['pdf'], key="training_uploader_tab", on_change=process_training_pdf)
                    
                    if st.session_state.get('training_info_para_salvar'):
                        training_info = st.session_state.training_info_para_salvar
                        if training_info and training_info.get('data'):
                            with st.container(border=True):
                                st.markdown("### Confirme as Informações Extraídas")
                                # ... (exibição dos dados extraídos) ...
                                if st.button("Confirmar e Salvar Treinamento", type="primary"):
                                    with st.spinner("Salvando Treinamento..."):
                                        anexo_training = st.session_state.training_anexo_para_salvar
                                        selected_employee_training = st.session_state.training_funcionario_para_salvar
                                        
                                        arquivo_id = gdrive_uploader.upload_file(anexo_training, f"TRAINING_{selected_employee_training}_{training_info.get('norma')}")
                                        
                                        if arquivo_id:
                                            vencimento = employee_manager.calcular_vencimento_treinamento(**training_info)
                                            training_info.update({'id': selected_employee_training, 'anexo': arquivo_id, 'vencimento': vencimento, 'status': "Válido"})
                                            
                                            training_id = employee_manager.add_training(**training_info)
                                            
                                            if training_id:
                                                st.success(f"Treinamento adicionado com sucesso! ID: {training_id}")
                                                for key in ['training_info_para_salvar', 'training_anexo_para_salvar', 'training_funcionario_para_salvar']:
                                                    if key in st.session_state:
                                                        del st.session_state[key]
                                                st.rerun()
                                            else:
                                                st.error("Falha ao salvar os dados na planilha. O anexo foi criado, mas os dados não foram registrados.")
                                        else:
                                            st.error("Falha ao fazer o upload do anexo para o Google Drive. Verifique as permissões.")
                        else:
                            st.error("Não foi possível extrair informações válidas do PDF.")
                            if 'training_info_para_salvar' in st.session_state:
                                del st.session_state.training_info_para_salvar
                else: st.warning("Cadastre funcionários nesta empresa primeiro.")
            else: st.error("Você não tem permissão para esta ação.")
        else: st.info("Selecione uma empresa na primeira aba.")
   

   


   


   

   

   

   
