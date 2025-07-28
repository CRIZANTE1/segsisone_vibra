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
        return df
    except Exception as e:
        st.error(f"Falha ao carregar a base de conhecimento RAG unificada: {e}")
        return pd.DataFrame()

class NRAnalyzer:
    def __init__(self):
        self.pdf_analyzer = PDFQA()
        from operations.sheet import SheetOperations
        self.sheet_ops = SheetOperations()
        self.action_plan_manager = ActionPlanManager()

        try:
            self.rag_sheet_id = st.secrets.app_settings.get("rag_sheet_id")
            if not self.rag_sheet_id:
                st.error("ID da planilha RAG unificada ('rag_sheet_id') não encontrado nos secrets.")
        except (AttributeError, KeyError):
            st.error("A seção [app_settings] com 'rag_sheet_id' não foi encontrada no seu secrets.toml.")
            self.rag_sheet_id = None

    def _get_advanced_audit_prompt(self, doc_info: dict) -> str:
        """
        NOVO PROMPT AVANÇADO: Define uma persona de auditor sênior e uma tarefa de análise complexa.
        """
        doc_type = doc_info.get("type", "documento")
        norma = doc_info.get("norma", "normas aplicáveis")
        
        return f"""
        **Persona:** Você é um Auditor Líder de Saúde e Segurança do Trabalho com mais de 20 anos de experiência, especializado em conformidade regulatória no Brasil. Você é extremamente meticuloso, analítico e suas conclusões são sempre baseadas em evidências claras encontradas no documento e referências normativas.

        **Contexto:** Você está auditando um(a) '{doc_type}' para a norma '{norma}'. O PDF deste documento e uma extensa base de conhecimento com Normas Regulamentadoras e procedimentos internos estão sendo fornecidos a você como contexto.

        **Sua Tarefa (em 3 etapas):**

        1.  **Análise Crítica:** Analise o documento PDF em profundidade. Verifique todos os aspectos essenciais de conformidade, como:
            *   **Validade e Emissão:** Datas, periodicidade, vencimentos.
            *   **Conteúdo Obrigatório:** Presença de todos os tópicos, anexos e informações exigidas pela(s) norma(s) relevante(s).
            *   **Responsabilidades:** Assinaturas do responsável técnico, do trabalhador, do médico, etc.
            *   **Dados Formais:** Nome correto da empresa, do funcionário, CNPJ, CPF, carga horária, etc.

        2.  **Formatação da Resposta:** Apresente suas conclusões no seguinte formato JSON ESTRITO. Não adicione nenhum texto ou comentário fora do bloco de código JSON.

        3.  **Justificativa Robusta:** Para cada item de não conformidade, a 'observacao' deve ser uma explicação clara, concisa e profissional, citando o requisito faltante e, se possível, a referência normativa encontrada na base de conhecimento.

        **Estrutura JSON de Saída Obrigatória:**
        ```json
        {{
          "parecer_final": "Conforme | Não Conforme | Conforme com Ressalvas",
          "resumo_executivo": "Um parágrafo curto resumindo sua conclusão geral sobre o documento. Ex: 'O documento está em conformidade, porém recomenda-se atenção ao prazo de reciclagem.' ou 'O documento apresenta falhas críticas de conformidade que o invalidam.'",
          "pontos_de_nao_conformidade": [
            {{
              "item": "Descrição clara do requisito não atendido. Ex: 'Carga horária insuficiente para formação inicial.'",
              "referencia_normativa": "O item específico da norma ou procedimento. Ex: 'NR-35, Anexo II, item 2.1.a'",
              "observacao": "A justificativa detalhada. Ex: 'O certificado apresenta carga horária de 4h, enquanto a norma exige um mínimo de 8h para a formação inicial de trabalho em altura.'"
            }}
          ]
        }}
        ```
        **Importante:** Se o documento estiver totalmente 'Conforme', a chave "pontos_de_nao_conformidade" deve ser um array vazio `[]`.
        """

    def _parse_advanced_audit_result(self, json_string: str) -> dict:
        """Processa a resposta JSON da IA."""
        try:
            match = re.search(r'\{.*\}', json_string, re.DOTALL)
            if not match:
                return {"summary": "Falha na Análise (Formato Inválido)", "details": []}
            
            data = json.loads(match.group(0))
            
            summary = data.get("parecer_final", "Indefinido")
            details = []

            if data.get("resumo_executivo"):
                status_resumo = "Conforme" if summary.lower() == 'conforme' else "Não Conforme"
                details.append({
                    "item_verificacao": "Resumo Executivo da Auditoria",
                    "referencia": "N/A",
                    "observacao": data["resumo_executivo"],
                    "status": status_resumo
                })
            
            for item in data.get("pontos_de_nao_conformidade", []):
                details.append({
                    "item_verificacao": item.get("item", ""),
                    "referencia": item.get("referencia_normativa", ""),
                    "observacao": item.get("observacao", ""),
                    "status": "Não Conforme"
                })

            return {"summary": summary, "details": details}

        except (json.JSONDecodeError, AttributeError):
            return {"summary": "Falha na Análise (Erro de JSON)", "details": []}

    def perform_initial_audit(self, doc_info: dict, file_content: bytes) -> dict | None:
        """
        Versão avançada que audita o documento contra a base de conhecimento completa.
        """
        if not self.rag_sheet_id: return None

        rag_df = load_unified_rag_base(self.rag_sheet_id)
        if rag_df.empty: return None

        knowledge_base_text = "\n\n---\n\n".join(rag_df['Answer_Chunk'].tolist())

        prompt = self._get_advanced_audit_prompt(doc_info)

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file_content)
                temp_path = temp_file.name

            full_prompt = f"{prompt}\n\n**Base de Conhecimento para Consulta:**\n{knowledge_base_text}"
            
            analysis_result, _ = self.pdf_analyzer.answer_question([temp_path], full_prompt)
            
            return self._parse_advanced_audit_result(analysis_result) if analysis_result else None
        
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def create_action_plan_from_audit(self, audit_result: dict, company_id: str, doc_id: str):
        # (Esta função não precisa de alterações)
        if audit_result.get("summary", "").lower() == 'conforme':
            return 0
        non_compliant_items = [d for d in audit_result.get("details", []) if d.get("status", "").lower() == "não conforme"]
        if not non_compliant_items: return 0
        
        audit_run_id = f"audit_{doc_id}_{random.randint(100,999)}"
        created_count = 0
        for item in non_compliant_items:
            if self.action_plan_manager.add_action_item(audit_run_id, company_id, doc_id, item):
                created_count += 1
        return created_count
