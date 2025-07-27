import streamlit as st
import pandas as pd
from datetime import datetime, date

def mostrar_info_normas():
    with st.expander("Informações sobre Normas Regulamentadoras"):
        st.markdown("""
        ### Cargas Horárias e Periodicidade dos Treinamentos
        
        #### NR-20
        | Módulo | Formação Inicial | Reciclagem (Periodicidade) | Reciclagem (C.H. Mínima) |
        |--------|------------------|----------------------------|--------------------------|
        | Básico | 8 horas          | 3 anos                     | 4 horas                  |
        | Intermediário | 16 horas         | 2 anos                     | 4 horas                  |
        | Avançado I | 20 horas         | 2 anos                     | 4 horas                  |
        | Avançado II | 32 horas         | 1 ano                      | 4 horas                  |
        
        ---

        #### Outras NRs Comuns
        | Norma | Formação Inicial (C.H.) | Reciclagem (C.H.) | Periodicidade Reciclagem |
        |-------|---------------------------|-----------------------|--------------------------|
        | NR-35 | 8 horas                   | 8 horas               | 2 anos                   |
        | NR-10 | 40 horas                  | 40 horas              | 2 anos                   |
        | NR-18 | 8 horas                   | 8 horas               | 1 ano                    |
        | NR-34 | 8 horas                   | 8 horas               | 1 ano                    |
        | NR-12 | 8 horas                   | 8 horas               | 2 anos                   |
        | NR-06 | 3 horas                   | 3 horas               | 10 anos                   |
        | NR-11 | 16-32 horas               | 16 horas              | 3 anos                   |
        | NR-33 | 16-40 horas               | 8 horas               | 1 ano                    |
        | Brigada | 24 horas (Avançado)     | 16 horas (Avançado)   | 1 ano                    |
        """)

def highlight_expired(row):
    today = datetime.now().date()
    vencimento_val = row.get('vencimento')
    if pd.notna(vencimento_val) and isinstance(vencimento_val, date):
        if vencimento_val < today:
            return ['background-color: #FFCDD2'] * len(row)
    return [''] * len(row)

def style_audit_table(row):
    """Aplica cor à linha inteira se o status for 'Não Conforme'."""
    status_val = str(row.get('Status', '')).lower()
    if 'Não Conforme' in status_val:
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

def process_company_doc_pdf():
    if st.session_state.get('doc_uploader_tab'):
        docs_manager = st.session_state.docs_manager
        with st.spinner("Analisando PDF do documento..."):
            st.session_state.doc_anexo_para_salvar = st.session_state.doc_uploader_tab
            st.session_state.doc_info_para_salvar = docs_manager.analyze_company_doc_pdf(st.session_state.doc_uploader_tab)
