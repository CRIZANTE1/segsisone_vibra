import streamlit as st
import pandas as pd
import tempfile
import os
import re
from datetime import datetime
import random
import io

from AI.api_Operation import PDFQA
from gdrive.config import get_credentials_dict, AUDIT_RESULTS_SHEET_NAME
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from operations.action_plan import ActionPlanManager

@st.cache_data(ttl=3600)
def load_unified_rag_base(sheet_id: str) -> pd.DataFrame:
    """Carrega a planilha de RAG unificada em um DataFrame."""
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = get_credentials_dict()
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.sheet1
        df = pd.DataFrame(worksheet.get_all_records())

        expected_columns = [
            "Norma_Referencia",
            "ID",
            "Section_Number",
            "Page",
            "Keywords",
            "Question",
            "Answer_Chunk",
            "Chunk" 
        ]
        columns_to_keep = [col for col in expected_columns if col in df.columns]

        if "Norma_Referencia" not in df.columns:
            st.error("Erro crítico: A planilha RAG unificada não contém a coluna 'Norma_Referencia'.")
            return pd.DataFrame()

        df['Norma_Referencia'] = df['Norma_Referencia'].astype(str)
        return df[columns_to_keep]

    except Exception as e:
        st.error(f"Falha ao carregar a base de conhecimento RAG unificada: {e}")
        return pd.DataFrame()

class NRAnalyzer:
    def __init__(self):
        self.pdf_analyzer = PDFQA()
        self.action_plan_manager = ActionPlanManager()
        from operations.sheet import SheetOperations
        self.sheet_ops = SheetOperations()
        try:
            creds_dict = get_credentials_dict()
            creds = Credentials.from_service_account_info(creds_dict)
            self.drive_service = build('drive', 'v3', credentials=creds)
        except Exception as e:
            st.error(f"Falha ao inicializar o serviço do Google Drive: {e}")
            self.drive_service = None

        try:
            self.rag_sheet_id = st.secrets.app_settings.get("rag_sheet_id")
            if not self.rag_sheet_id:
                st.error("ID da planilha RAG unificada ('rag_sheet_id') não encontrado nos secrets.")

            self.doc_type_to_nr_map = {
                "PGR": "NR-01",
                "PCMSO": "NR-07",
                "ASO": "NR-07",
                "Treinamento": None
            }
        except (AttributeError, KeyError):
            st.error("A seção [app_settings] com 'rag_sheet_id' não foi encontrada no seu secrets.toml.")
            self.rag_sheet_id = None

    def _get_initial_audit_prompt(self, norma_analisada: str, nr_knowledge_base: str) -> str:
        return f"""
        Você é um auditor de Segurança do Trabalho rigoroso e eficiente. Sua tarefa é realizar uma auditoria rápida de conformidade no documento fornecido, usando os trechos da {norma_analisada} como referência.

        **Base de Conhecimento (Trechos da {norma_analisada}):**
        {nr_knowledge_base}

        **TAREFA:**
        1.  Forneça um parecer final na primeira linha, no formato ESTRITO: `PARECER FINAL: [Conforme/Não Conforme]`
        2.  Se o parecer for "Não Conforme", liste APENAS os pontos de falha abaixo da primeira linha.
        3.  Para cada ponto de falha, use o formato ESTRITO de 3 partes, separadas por '|':
            `ITEM: [Descrição do item não conforme] | REFERÊNCIA: [Seção ou item da norma, se encontrado] | OBSERVAÇÃO: [Justificativa curta e objetiva da falha]`

        **Exemplo de Saída (Não Conforme):**
        PARECER FINAL: Não Conforme
        ITEM: Carga horária insuficiente para reciclagem | REFERÊNCIA: Item 20.11.12 | OBSERVAÇÃO: O certificado informa 2 horas, mas a norma exige no mínimo 4 horas para reciclagem do módulo básico.
        ITEM: Ausência da assinatura do responsável técnico | REFERÊNCIA: Item 1.5.7.3 | OBSERVAÇÃO: O documento não possui a assinatura do engenheiro de segurança responsável.

        **Exemplo de Saída (Conforme):**
        PARECER FINAL: Conforme
        """

    def _parse_audit_result(self, analysis_text: str) -> dict:
        if not analysis_text:
            return {"summary": "Falha na Análise", "details": []}

        lines = analysis_text.strip().split('\n')
        summary = "Indefinido"
        details = []

        if lines and lines[0].strip().upper().startswith("PARECER FINAL:"):
            summary = lines[0].replace("PARECER FINAL:", "").strip()
            lines = lines[1:]

        for line in lines:
            line = line.strip()
            if line.startswith("ITEM:"):
                try:
                    parts = line.split('|')
                    item = parts[0].replace("ITEM:", "").strip()
                    ref = parts[1].replace("REFERÊNCIA:", "").strip()
                    obs = parts[2].replace("OBSERVAÇÃO:", "").strip()
                    details.append({"item_verificacao": item, "referencia": ref, "observacao": obs, "status": "Não Conforme"})
                except IndexError:
                    continue

        if summary.lower() == 'não conforme' and not details:
             details.append({"item_verificacao": "Resumo da Auditoria", "referencia": "N/A", "observacao": "A IA indicou não conformidade, mas não detalhou os itens.", "status": "Não Conforme"})
        elif summary.lower() == 'conforme':
             details.append({"item_verificacao": "Resumo da Auditoria", "referencia": "N/A", "observacao": "O documento parece estar em conformidade com os pontos chave da norma.", "status": "Conforme"})

        return {"summary": summary, "details": details}

    def _find_relevant_chunks(self, rag_df: pd.DataFrame, keywords: list[str]) -> str:
        if rag_df.empty: return "Base de conhecimento para esta norma indisponível."
        regex_pattern = '|'.join(map(re.escape, keywords))
        if 'Keywords' not in rag_df.columns: return "Coluna 'Keywords' não encontrada na planilha de RAG."
        rag_df['Keywords'] = rag_df['Keywords'].astype(str)
        relevant_rows = rag_df[rag_df['Keywords'].str.contains(regex_pattern, case=False, na=False)]

        if relevant_rows.empty: return "Nenhum trecho relevante encontrado para as palavras-chave."

        knowledge_text = "\n\n".join(relevant_rows['Answer_Chunk'].tolist())
        return knowledge_text

    def perform_initial_audit(self, doc_info: dict, file_content: bytes) -> dict | None:
        doc_type = doc_info.get("type")
        norma_analisada = doc_info.get("norma") if doc_type == "Treinamento" else self.doc_type_to_nr_map.get(doc_type)

        if not norma_analisada:
            st.info(f"Auditoria automática não aplicável para o tipo de documento: {doc_type}")
            return {"summary": "Não Aplicável", "details": []}

        if not self.rag_sheet_id: return None

        rag_df_completo = load_unified_rag_base(self.rag_sheet_id)
        if rag_df_completo.empty: return None

        rag_df_filtrado = rag_df_completo[rag_df_completo['Norma_Referencia'].str.upper() == norma_analisada.upper()]

        if rag_df_filtrado.empty:
            st.info(f"Nenhum conhecimento encontrado para a norma {norma_analisada} na base RAG.")
            return {"summary": "Não Aplicável", "details": []}

        keywords = ["Requisitos", "Documentação", "Certificado", "Validade", "Conteúdo", "Assinatura"]
        relevant_knowledge = self._find_relevant_chunks(rag_df_filtrado, keywords)

        prompt = self._get_initial_audit_prompt(norma_analisada, relevant_knowledge)

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file_content)
                temp_path = temp_file.name

            with st.spinner(f"Executando auditoria rápida contra a {norma_analisada}..."):
                analysis_result, _ = self.pdf_analyzer.answer_question([temp_path], prompt)

            if analysis_result:
                return self._parse_audit_result(analysis_result)
            else:
                st.warning("A IA não gerou um resultado para a auditoria.")
                return None
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def save_audit_results(self, audit_details: list, doc_info: dict, company_id: str, original_doc_id: str):
        if not audit_details: return True

        saved_count = 0
        total_items = len(audit_details)
        data_auditoria_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        audit_run_id = random.randint(10000, 99999)
        norma_analisada = doc_info.get("norma", "N/A")

        for row in audit_details:
            new_audit_row = [
                audit_run_id,
                data_auditoria_atual,
                company_id,
                original_doc_id,
                doc_info.get('employee_id', 'N/A'),
                doc_info.get('type', 'N/A'),
                norma_analisada,
                row.get('item_verificacao', ''),
                row.get('status', ''),
                row.get('observacao', '')
            ]
            save_id = self.sheet_ops.adc_dados_aba(AUDIT_RESULTS_SHEET_NAME, new_audit_row)
            if save_id:
                saved_count += 1

        return saved_count == total_items

    def create_action_plan_from_audit(self, audit_result: dict, company_id: str, doc_id: str):
        """Cria itens no plano de ação para cada falha encontrada na auditoria."""
        if audit_result.get("summary", "").lower() != 'não conforme':
            return 0 # Nenhum item criado

        non_compliant_items = [d for d in audit_result.get("details", []) if d.get("status", "").lower() == "não conforme"]
        if not non_compliant_items:
            return 0

        audit_run_id = f"audit_{doc_id}" 
        
        created_count = 0
        for item in non_compliant_items:
            if self.action_plan_manager.add_action_item(audit_run_id, company_id, doc_id, item):
                created_count += 1
        
        return created_count
