import streamlit as st
import pandas as pd
import tempfile
import os
import re
import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import google.generativeai as genai
import random
import gspread
from AI.api_Operation import PDFQA
from gdrive.config import get_credentials_dict
from operations.action_plan import ActionPlanManager
from google.oauth2.service_account import Credentials
from datetime import datetime



@st.cache_data(ttl=3600)
def load_and_embed_rag_base(sheet_id: str) -> tuple[pd.DataFrame, np.ndarray | None]:
    """
    Carrega a planilha RAG, gera embeddings para cada chunk e armazena em cache.
    """
    try:
        # Carrega os dados da planilha
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds_dict = get_credentials_dict()
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.sheet1
        df = pd.DataFrame(worksheet.get_all_records())

        if df.empty or "Answer_Chunk" not in df.columns:
            st.error("A planilha RAG está vazia ou não contém a coluna 'Answer_Chunk'.")
            return pd.DataFrame(), None

        with st.spinner(f"Indexando a base de conhecimento ({len(df)} itens)..."):
            chunks_to_embed = df["Answer_Chunk"].tolist()
            result = genai.embed_content(
                model='models/text-embedding-004',
                content=chunks_to_embed,
                task_type="RETRIEVAL_DOCUMENT"
            )
            embeddings = np.array(result['embedding'])
        
        st.success("Base de conhecimento indexada e pronta para uso!")
        return df, embeddings

    except Exception as e:
        # Se a chave de API não estiver configurada, um erro será capturado aqui.
        st.error(f"Falha ao carregar e gerar embeddings para a base RAG: {e}")
        st.warning("Verifique se a chave GEMINI_AUDIT_KEY está configurada corretamente nos secrets.")
        return pd.DataFrame(), None

    except Exception as e:
        st.error(f"Falha ao carregar e gerar embeddings para a base RAG: {e}")
        st.warning("Verifique sua chave de API e os limites de quota.")
        return pd.DataFrame(), None

class NRAnalyzer:
    def __init__(self):
        self.pdf_analyzer = PDFQA()
        from operations.sheet import SheetOperations
        self.sheet_ops = SheetOperations()
        self.action_plan_manager = ActionPlanManager()

        self.rag_sheet_id = None
        self.rag_df = pd.DataFrame()
        self.rag_embeddings = np.array([])
        
        try:
            self.rag_sheet_id = st.secrets.app_settings.get("rag_sheet_id")
            if not self.rag_sheet_id:
                st.error("ID da planilha RAG ('rag_sheet_id') não encontrado nos secrets.")
            else:
                self.rag_df, self.rag_embeddings = load_and_embed_rag_base(self.rag_sheet_id)
        except (AttributeError, KeyError):
            st.error("Seção [app_settings] com 'rag_sheet_id' não encontrada no secrets.toml.")

    def _find_semantically_relevant_chunks(self, query_text: str, top_k: int = 5) -> str:
        if self.rag_df.empty or self.rag_embeddings is None or self.rag_embeddings.size == 0:
            return "Base de conhecimento indisponível ou não indexada."

        try:
            query_embedding_result = genai.embed_content(
                model='models/text-embedding-004',
                content=[query_text],
                task_type="RETRIEVAL_QUERY"
            )
            query_embedding = np.array(query_embedding_result['embedding'])
            similarities = cosine_similarity(query_embedding, self.rag_embeddings)[0]
            top_k_indices = similarities.argsort()[-top_k:][::-1]
            relevant_chunks = self.rag_df.iloc[top_k_indices]
            context_text = "\n\n---\n\n".join(relevant_chunks['Answer_Chunk'].tolist())
            return context_text
        except Exception as e:
            st.warning(f"Erro durante a busca semântica: {e}")
            return "Erro ao buscar chunks relevantes na base de conhecimento."

    def perform_initial_audit(self, doc_info: dict, file_content: bytes) -> dict | None:
        doc_type = doc_info.get("type", "documento")
        norma = doc_info.get("norma", "")
        query = f"Quais são os principais requisitos de conformidade, validade e conteúdo para um {doc_type} da norma {norma}?"

        relevant_knowledge = self._find_semantically_relevant_chunks(query, top_k=5)

        prompt = self._get_advanced_audit_prompt(doc_info, relevant_knowledge)
        
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file_content)
                temp_path = temp_file.name

            analysis_result, _ = self.pdf_analyzer.answer_question([temp_path], prompt)
            return self._parse_advanced_audit_result(analysis_result) if analysis_result else None
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
        
    def _get_advanced_audit_prompt(self, doc_info: dict, relevant_knowledge: str) -> str:
        """
        PROMPT AVANÇADO: Agora instrui a IA a citar a página e a evidência para cada não conformidade.
        """
        doc_type = doc_info.get("type", "documento")
        norma = doc_info.get("norma", "normas aplicáveis")
        data_atual = datetime.now().strftime('%d/%m/%Y')

        return f"""
        **Persona:** Você é um Auditor Líder de Saúde e Segurança do Trabalho com mais de 20 anos de experiência. Seu trabalho é famoso pela precisão e pela clareza. Para cada apontamento, você SEMPRE fornece a evidência concreta.

        **Contexto Crítico:** A data de hoje é **{data_atual}**.

        **Contexto da Tarefa:** Você está auditando um(a) '{doc_type}' para a norma '{norma}'. O PDF do documento e trechos relevantes da base de conhecimento estão sendo fornecidos.

        **Trechos Relevantes da Base de Conhecimento:**
        {relevant_knowledge}

        **Sua Tarefa (em 3 etapas):**

        1.  **Análise Crítica:** Analise o documento PDF em profundidade, procurando por não conformidades.
        2.  **Formatação da Resposta:** Apresente suas conclusões no seguinte formato JSON ESTRITO. Não adicione nenhum texto fora do bloco de código JSON.
        3.  **Justificativa Robusta com Evidências:** Esta é a regra mais importante. Para cada item na chave "pontos_de_nao_conformidade", a 'observacao' DEVE OBRIGATORIAMENTE conter:
            *   **A página** onde a evidência da não conformidade foi encontrada (ex: "p. 5", "página 12").
            *   **O trecho exato** do texto do documento que comprova a falha, entre aspas.
            *   Uma explicação clara de por que aquele trecho representa uma não conformidade.

        **Estrutura JSON de Saída Obrigatória:**
        ```json
        {{
          "parecer_final": "Conforme | Não Conforme | Conforme com Ressalvas",
          "resumo_executivo": "Um parágrafo curto resumindo sua conclusão geral sobre o documento.",
          "pontos_de_nao_conformidade": [
            {{
              "item": "Descrição clara do requisito não atendido. Ex: 'Cronograma do Plano de Ação inconsistente com a vigência do PGR.'",
              "referencia_normativa": "O item específico da norma. Ex: 'NR-01, item 1.5.4.4.3'",
              "observacao": "A justificativa detalhada COM EVIDÊNCIA. Ex: 'Na página 25, o cronograma apresenta a atividade 'Treinamento de CIPA' com data 'Dez/2025'. Como a vigência do PGR termina em Out/2025, esta atividade está fora do escopo temporal do plano de ação.'"
            }},
            {{
              "item": "Carga horária insuficiente para reciclagem.",
              "referencia_normativa": "NR-35, item 35.3.3.1",
              "observacao": "Na página 1, o certificado afirma que a 'Carga Horária foi de 4 (quatro) horas'. A norma exige um mínimo de 8 horas para a reciclagem, tornando este certificado inválido para esse fim."
            }}
          ]
        }}
        ```
        **Importante:** Se o documento estiver 'Conforme', a chave "pontos_de_nao_conformidade" deve ser um array vazio `[]`.
        """

    def _parse_advanced_audit_result(self, json_string: str) -> dict:
        try:
            match = re.search(r'\{.*\}', json_string, re.DOTALL)
            if not match:
                return {"summary": "Falha na Análise (Formato Inválido)", "details": [{"item_verificacao": "Resposta Bruta da IA", "observacao": json_string, "status": "Não Conforme"}]}
            
            data = json.loads(match.group(0))
            summary = data.get("parecer_final", "Indefinido")
            details = []

            if data.get("resumo_executivo"):
                status_resumo = "Conforme" if summary.lower() == 'conforme' else "Não Conforme"
                details.append({"item_verificacao": "Resumo Executivo da Auditoria", "referencia": "N/A", "observacao": data["resumo_executivo"], "status": status_resumo})
            
            for item in data.get("pontos_de_nao_conformidade", []):
                details.append({"item_verificacao": item.get("item", ""), "referencia": item.get("referencia_normativa", ""), "observacao": item.get("observacao", ""), "status": "Não Conforme"})

            return {"summary": summary, "details": details}
        except (json.JSONDecodeError, AttributeError):
            return {"summary": "Falha na Análise (Erro de JSON)", "details": [{"item_verificacao": "Resposta Bruta da IA", "observacao": json_string, "status": "Não Conforme"}]}

    def create_action_plan_from_audit(self, audit_result: dict, company_id: str, doc_id: str, employee_id: str | None = None):
        """
        Cria itens no plano de ação para cada não conformidade real.
        Agora aceita um 'employee_id' opcional.
        """
        if "não conforme" not in audit_result.get("summary", "").lower():
            return 0
        
        all_details = audit_result.get("details", [])
        
        actionable_items = [
            item for item in all_details 
            if item.get("status", "").lower() == "não conforme" 
            and "resumo executivo" not in item.get("item_verificacao", "").lower()
        ]
        
        if not actionable_items:
            return 0
        
        audit_run_id = f"audit_{doc_id}_{random.randint(1000, 9999)}"
        created_count = 0
        
        for item in actionable_items:
           
            item['employee_id'] = employee_id if employee_id else 'N/A'
            
            if self.action_plan_manager.add_action_item(audit_run_id, company_id, doc_id, item):
                created_count += 1
                
        return created_count
