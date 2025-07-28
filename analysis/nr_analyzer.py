import streamlit as st
import pandas as pd
import tempfile
import os
import re
import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import google.generativeai as genai

from AI.api_Operation import PDFQA
from gdrive.config import get_credentials_dict
from operations.action_plan import ActionPlanManager


try:
    embedding_model = genai.GenerativeModel('models/text-embedding-004')
except Exception as e:
    st.error(f"Não foi possível inicializar o modelo de embedding do Gemini. Verifique sua chave de API. Erro: {e}")
    embedding_model = None

@st.cache_data(ttl=3600)
def load_and_embed_rag_base(sheet_id: str) -> tuple[pd.DataFrame, np.ndarray | None]:
    """
    Carrega a planilha RAG, gera embeddings para cada chunk e armazena em cache.
    Esta é a etapa de "indexação" que acontece uma vez.
    """
    if not embedding_model:
        st.warning("Modelo de embedding não está disponível. A análise RAG será desativada.")
        return pd.DataFrame(), None
        
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

        with st.spinner(f"Indexando a base de conhecimento ({len(df)} itens)... Isso acontece apenas uma vez."):
            # Gera embeddings para todos os chunks de uma vez
            chunks_to_embed = df["Answer_Chunk"].tolist()
            result = embedding_model.embed_content(chunks_to_embed, task_type="RETRIEVAL_DOCUMENT")
            embeddings = np.array(result['embedding'])
        
        st.success("Base de conhecimento indexada e pronta para uso!")
        return df, embeddings

    except Exception as e:
        st.error(f"Falha ao carregar e gerar embeddings para a base RAG: {e}")
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
                st.error("ID da planilha RAG unificada ('rag_sheet_id') não encontrado nos secrets.")
            else:
                # Carrega e gera os embeddings na inicialização da classe
                self.rag_df, self.rag_embeddings = load_and_embed_rag_base(self.rag_sheet_id)

        except (AttributeError, KeyError):
            st.error("A seção [app_settings] com 'rag_sheet_id' não foi encontrada no seu secrets.toml.")

    def _find_semantically_relevant_chunks(self, query_text: str, top_k: int = 5) -> str:
        """
        Encontra os 'top_k' chunks mais relevantes usando busca por similaridade de cosseno.
        """
        if self.rag_df.empty or self.rag_embeddings is None or self.rag_embeddings.size == 0:
            return "Base de conhecimento indisponível ou não indexada."

        try:
            query_embedding_result = embedding_model.embed_content([query_text], task_type="RETRIEVAL_QUERY")
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
