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

def _run_analysis_and_audit(analysis_func, uploader_key, doc_type_str, employee_id_key=None):
    """
    Função genérica e interna para executar a análise de dados E a auditoria de conformidade.
    """
    if not st.session_state.get(uploader_key):
        return

    nr_analyzer = st.session_state.nr_analyzer
    
    anexo = st.session_state[uploader_key]
    st.session_state[f"{doc_type_str}_anexo_para_salvar"] = anexo
    
    employee_id = st.session_state.get(employee_id_key) if employee_id_key else None
    if employee_id:
        st.session_state[f"{doc_type_str}_funcionario_para_salvar"] = employee_id

    with st.spinner(f"Analisando conteúdo do PDF..."):
        info = analysis_func(anexo)

    if not info:
        st.error("Não foi possível extrair informações básicas do documento.")
        return

    info['type'] = doc_type_str
    if employee_id:
        info['employee_id'] = employee_id

    with st.spinner(f"Executando auditoria de conformidade..."):
        audit_result = nr_analyzer.perform_initial_audit(info, anexo.getvalue())

    if audit_result:
        info['audit_result'] = audit_result
    else:
        info['audit_result'] = {"summary": "Falha na Auditoria", "details": []}
    
    st.session_state[f"{doc_type_str}_info_para_salvar"] = info

def process_aso_pdf():
    _run_analysis_and_audit(
        analysis_func=st.session_state.employee_manager.analyze_aso_pdf,
        uploader_key='aso_uploader_tab',
        doc_type_str='ASO',
        employee_id_key='aso_employee_add'
    )

def process_training_pdf():
    _run_analysis_and_audit(
        analysis_func=st.session_state.employee_manager.analyze_training_pdf,
        uploader_key='training_uploader_tab',
        doc_type_str='Treinamento',
        employee_id_key='training_employee_add'
    )

def process_company_doc_pdf():
    _run_analysis_and_audit(
        analysis_func=st.session_state.docs_manager.analyze_company_doc_pdf,
        uploader_key='doc_uploader_tab',
        doc_type_str='Doc. Empresa'
    )

def process_epi_pdf():
    """
    A Ficha de EPI não passa pela auditoria de NR, então mantemos sua lógica simples.
    """
    if st.session_state.get('epi_uploader_tab'):
        epi_manager = st.session_state.epi_manager
        with st.spinner("Analisando PDF da Ficha de EPI..."):
            st.session_state.epi_anexo_para_salvar = st.session_state.epi_uploader_tab
            st.session_state.epi_funcionario_para_salvar = st.session_state.epi_employee_add
            st.session_state.epi_info_para_salvar = epi_manager.analyze_epi_pdf(st.session_state.epi_uploader_tab)            
