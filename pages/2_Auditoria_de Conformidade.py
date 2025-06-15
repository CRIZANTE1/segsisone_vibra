import streamlit as st
import pandas as pd
from operations.employee import EmployeeManager
from operations.company_docs import CompanyDocsManager
from analysis.nr_analyzer import NRAnalyzer

def init_managers():
    if 'employee_manager' not in st.session_state:
        st.session_state.employee_manager = EmployeeManager()
    if 'docs_manager' not in st.session_state:
        st.session_state.docs_manager = CompanyDocsManager()
    if 'nr_analyzer' not in st.session_state:
        st.session_state.nr_analyzer = NRAnalyzer()

def style_status_table(df: pd.DataFrame):
    """Aplica cores à coluna 'Status' de um DataFrame."""
    def highlight_status(val):
        color = ''
        val_lower = str(val).lower()
        if 'não conforme' in val_lower:
            color = 'background-color: #FFCDD2'  # Vermelho claro
        elif 'conforme' in val_lower:
            color = 'background-color: #C8E6C9'  # Verde claro
        return color
    
    if 'Status' in df.columns:
        # Substitui o 'applymap' obsoleto por 'map'
        return df.style.map(highlight_status, subset=['Status'])
    return df.style # Retorna o Styler sem formatação se a coluna não existir


st.set_page_config(page_title="Auditoria de Conformidade", layout="wide")
init_managers()

employee_manager = st.session_state.employee_manager
docs_manager = st.session_state.docs_manager
nr_analyzer = st.session_state.nr_analyzer

st.title("🔍 Auditoria de Conformidade de Documentos")
st.markdown("Selecione um documento existente para realizar uma análise profunda contra a base de conhecimento de uma NR.")

if not employee_manager.companies_df.empty:
    df_companies = employee_manager.companies_df.astype({'id': 'str'})
    selected_company_id = st.selectbox(
        "Selecione a empresa para auditar",
        df_companies['id'].tolist(),
        format_func=lambda x: f"{df_companies[df_companies['id'] == x]['nome'].iloc[0]}",
        index=None, placeholder="Escolha uma empresa..."
    )

    if selected_company_id:
        asos = employee_manager.aso_df[employee_manager.aso_df['funcionario_id'].isin(employee_manager.get_employees_by_company(selected_company_id)['id'])]
        trainings = employee_manager.training_df[employee_manager.training_df['funcionario_id'].isin(employee_manager.get_employees_by_company(selected_company_id)['id'])]
        company_docs = docs_manager.get_docs_by_company(selected_company_id)
        
        docs_list = []
        if not trainings.empty:
            for _, row in trainings.iterrows():
                employee_name = employee_manager.get_employee_name(row['funcionario_id']) or "Funcionário Desconhecido"
                norma = employee_manager._padronizar_norma(row['norma'])
                docs_list.append({"label": f"Treinamento: {norma} - {employee_name}", "url": row['arquivo_id'], "norma": norma, "type": "Treinamento"})
        if not company_docs.empty:
             for _, row in company_docs.iterrows():
                doc_type = row['tipo_documento']; norma_associada = "NR-01" if doc_type == "PGR" else ("NR-07" if doc_type == "PCMSO" else "NR-01")
                docs_list.append({"label": f"Doc. Empresa: {doc_type}", "url": row['arquivo_id'], "norma": norma_associada, "type": doc_type})
        if not asos.empty:
            for _, row in asos.iterrows():
                employee_name = employee_manager.get_employee_name(row['funcionario_id']) or "Funcionário Desconhecido"
                docs_list.append({"label": f"ASO: {row.get('tipo_aso', 'N/A')} - {employee_name}", "url": row['arquivo_id'], "norma": "NR-07", "type": "ASO"})

        selected_doc = st.selectbox(
            "Selecione o documento para análise",
            options=docs_list, format_func=lambda x: x['label'],
            index=None, placeholder="Escolha um documento..."
        )

        if selected_doc:
            norma_para_analise = selected_doc.get("norma")
            st.info(f"Documento selecionado: **{selected_doc['label']}**. Será analisado contra a **{norma_para_analise}**.")
            
            if norma_para_analise in nr_analyzer.nr_sheets_map:
                if st.button(f"Analisar Conformidade com a {norma_para_analise}", type="primary"):
                    resultado_df = nr_analyzer.analyze_document_compliance(selected_doc['url'], selected_doc)
                    st.session_state.audit_result_df = resultado_df
            else:
                st.warning(f"A análise para a {norma_para_analise} não está disponível. Nenhuma planilha de RAG foi configurada para esta norma em `analysis/nr_analyzer.py`.")

            if 'audit_result_df' in st.session_state and st.session_state.audit_result_df is not None:
                st.markdown("---")
                st.subheader("Resultado da Análise de Conformidade")
                
                styled_df = style_status_table(st.session_state.audit_result_df)
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
                
                if st.button("Limpar Análise"):
                    del st.session_state.audit_result_df
                    st.rerun()
else:
    st.warning("Nenhuma empresa cadastrada. Adicione uma empresa na página principal primeiro.")
