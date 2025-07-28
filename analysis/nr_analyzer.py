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
        PROMPT AVANÇADO: Agora inclui a data atual para dar contexto temporal à IA.
        """
        doc_type = doc_info.get("type", "documento")
        norma = doc_info.get("norma", "normas aplicáveis")
        
        data_atual = datetime.now().strftime('%d/%m/%Y')

        return f"""
        **Persona:** Você é um Auditor Líder de Saúde e Segurança do Trabalho com mais de 20 anos de experiência, especializado em conformidade regulatória no Brasil. Você é extremamente meticuloso e suas conclusões são sempre baseadas em evidências claras.

        **Contexto Crítico:** A data de hoje é **{data_atual}**. Qualquer data de emissão, aprovação ou assinatura no documento que seja posterior a hoje deve ser considerada uma inconsistência grave, pois um documento não pode ser aprovado no futuro.

        **Contexto da Tarefa:** Você está auditando um(a) '{doc_type}' para a norma '{norma}'. O PDF deste documento e trechos relevantes da base de conhecimento estão sendo fornecidos a você.

        **Trechos Relevantes da Base de Conhecimento:**
        {relevant_knowledge}

        **Sua Tarefa (em 3 etapas):**

        1.  **Análise Crítica:** Analise o documento PDF em profundidade. Verifique todos os aspectos essenciais de conformidade, prestando **atenção especial à consistência das datas**.
            *   **Validade e Emissão:** Compare todas as datas (emissão, vigência, aprovação, assinatura) com a data atual ({data_atual}). Uma data de aprovação futura para um programa já vigente é uma não conformidade crítica.
            *   **Conteúdo Obrigatório:** Presença de todos os tópicos exigidos pela(s) norma(s) relevante(s).
            *   **Responsabilidades:** Assinaturas e dados dos responsáveis técnicos.
            *   **Dados Formais:** Nomes, CNPJ, CPF, carga horária, etc.

        2.  **Formatação da Resposta:** Apresente suas conclusões no seguinte formato JSON ESTRITO. Não adicione nenhum texto fora do bloco de código JSON.

        3.  **Justificativa Robusta:** Para cada item de não conformidade, a 'observacao' deve ser uma explicação clara, citando o requisito faltante ou a inconsistência encontrada.

        **Estrutura JSON de Saída Obrigatória:**
        ```json
        {{
          "parecer_final": "Conforme | Não Conforme | Conforme com Ressalvas",
          "resumo_executivo": "Um parágrafo curto resumindo sua conclusão geral, mencionando explicitamente qualquer inconsistência de data encontrada.",
          "pontos_de_nao_conformidade": [
            {{
              "item": "Descrição clara do requisito não atendido. Ex: 'Data de aprovação futura.'",
              "referencia_normativa": "O item específico da norma ou procedimento. Ex: 'NR-01, item 1.5.7.1'",
              "observacao": "A justificativa detalhada. Ex: 'O documento, com vigência iniciada em 03/10/2023, apresenta uma data de aprovação de 21/07/2025. Esta data futura invalida a formalização do documento no período vigente.'"
            }}
          ]
        }}
        ```
        **Importante:** Se o documento estiver totalmente 'Conforme', a chave "pontos_de_nao_conformidade" deve ser um array vazio `[]`.
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

    def create_action_plan_from_audit(self, audit_result: dict, company_id: str, doc_id: str):
        """
        Cria itens no plano de ação. A referência a 'random' agora funcionará.
        """
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
