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
        doc_type = doc_info.get("type", "documento")
        norma = doc_info.get("norma", "normas aplicáveis")
        data_atual = datetime.now().strftime('%d/%m/%Y')

        checklist_instrucoes = ""
        json_example = ""

        if doc_type == "PGR" or norma == "NR-01":
            checklist_instrucoes = """
            **Checklist de Auditoria Crítica para PGR (NR-01) - NÃO ACEITE RESPOSTAS SUPERFICIAIS:**
            
            1.  **Inventário de Riscos (Qualidade vs. Presença):**
                *   NÃO BASTA TER A SEÇÃO. O inventário deve, para cada risco, apresentar uma **avaliação**, indicando o **nível de risco** (ex: baixo, médio, alto) baseado em critérios de **severidade e probabilidade** (NR 01, item 1.5.4.4.2).
                *   Verifique se os riscos são específicos para as funções/atividades da empresa e não genéricos.
                *   **REGRA:** Se o documento apresentar apenas uma lista de riscos sem uma classificação clara de nível de risco, considere o item **'Inventário de Riscos incompleto' como 'Não Conforme'**.

            2.  **Plano de Ação (Estrutura vs. Lista):**
                *   NÃO BASTA TER A SEÇÃO. O plano de ação deve conter um **cronograma** com datas ou prazos definidos e **responsáveis** pelas ações (NR 01, item 1.5.5.2.2).
                *   As ações devem ser específicas para os riscos identificados, e não apenas itens genéricos como "Atualização anual do PGR".
                *   **REGRA:** Se o plano de ação for uma lista de tópicos sem cronograma e responsáveis, considere o item **'Plano de Ação não estruturado' como 'Não Conforme'**.

            3.  **Procedimentos de Emergência:**
                *   Verifique se o documento descreve, mesmo que minimamente, os procedimentos de resposta a emergências (NR 01, item 1.5.6.1).
                *   **REGRA:** Se não houver menção a como responder a emergências, considere o item **'Ausência de plano de emergência' como 'Não Conforme'**.
                
            4.  **Vigência e Assinaturas:**
                *   Verifique se o documento tem data de emissão e assinatura do responsável.
                *   A data de emissão/aprovação NÃO PODE ser futura em relação à data da auditoria.
            """
            json_example = """
              "resumo_executivo": "O PGR apresentado é fundamentalmente inadequado, pois não cumpre os requisitos estruturais básicos da NR-01. O documento falha em avaliar os riscos e em apresentar um plano de ação com cronograma, sendo pouco mais que uma declaração de intenções.",
              "pontos_de_nao_conformidade": [
                {
                  "item": "Inventário de Riscos incompleto (sem avaliação de nível de risco)",
                  "referencia_normativa": "NR-01, item 1.5.4.4.2",
                  "observacao": "Na página 2, a seção 'Inventário de Riscos' apenas lista agentes de risco. Falta a avaliação da combinação de severidade e probabilidade para determinar o nível de risco, o que é um pilar do gerenciamento de riscos."
                },
                {
                  "item": "Plano de Ação não estruturado (sem cronograma e responsáveis)",
                  "referencia_normativa": "NR-01, item 1.5.5.2.2",
                  "observacao": "Na página 2, o 'Plano de Ação' apresenta uma lista de atividades genéricas sem definir um cronograma para sua implementação ou atribuir responsáveis, o que o descaracteriza como um plano acionável."
                }
              ]
            """
        
        elif doc_type == "Treinamento":
            checklist_instrucoes = f"""
            **Checklist de Auditoria Obrigatório para Certificado de Treinamento (Norma: {norma}):**
            1.  **Informações do Trabalhador:** Verifique se o nome completo e o CPF (ou outro identificador válido) do trabalhador estão presentes e legíveis.
            2.  **Conteúdo Programático (Cronograma):** Verifique se o certificado lista o conteúdo programático/cronograma do curso. Compare os tópicos listados com os requisitos da **Base de Conhecimento** para a norma '{norma}'. **Aponte como 'Não Conforme' se tópicos essenciais estiverem ausentes.**
            3.  **Carga Horária e Validade:** Verifique se a carga horária e a data de realização estão explícitas. Compare a carga horária com o mínimo exigido pela norma para o tipo de treinamento (formação/reciclagem), consultando a Base de Conhecimento. **Aponte como 'Não Conforme' se a carga horária for insuficiente.**
            4.  **Assinaturas e Responsáveis:** Verifique se o certificado possui as assinaturas do(s) instrutor(es) e do responsável técnico.
            5.  **Consistência das Datas:** A data de realização do treinamento não pode ser futura em relação à data da auditoria ({data_atual}).
            """
            json_example = """
              "resumo_executivo": "O certificado de NR-35 apresenta uma não conformidade crítica relacionada ao conteúdo programático obrigatório...",
              "pontos_de_nao_conformidade": [
                {
                  "item": "Conteúdo programático incompleto",
                  "referencia_normativa": "NR-35, item 35.4.2.1(d)",
                  "observacao": "Na página 2, o conteúdo programático listado não menciona 'sistemas de proteção coletiva', que é um tópico obrigatório para o treinamento de trabalho em altura, conforme a norma."
                }
              ]
            """
        
        else:
            checklist_instrucoes = """
            **Checklist de Auditoria Geral para Documentos de SST:**
            1.  **Identificação e Propósito:** Verifique se o documento identifica claramente a empresa, o trabalhador (se aplicável), e seu propósito (ex: Atestado de Saúde Ocupacional, Ordem de Serviço).
            2.  **Datas e Validade:** Identifique todas as datas presentes (emissão, realização, validade, assinatura). Verifique se são consistentes entre si e se não são datas futuras em relação à data da auditoria. **Aponte como 'Não Conforme' qualquer data de emissão/aprovação futura.**
            3.  **Conteúdo Essencial:** Verifique se o documento contém as informações mínimas esperadas para seu tipo. Para um ASO, por exemplo, isso inclui o tipo de exame (admissional, periódico), os riscos e o parecer de aptidão (apto/inapto).
            4.  **Responsáveis e Assinaturas:** Verifique se o documento foi emitido e assinado pelos profissionais responsáveis (ex: médico do trabalho para ASO, técnico de segurança para Ordem de Serviço).
            """
            json_example = """
              "resumo_executivo": "O Atestado de Saúde Ocupacional apresenta uma inconsistência crítica na data de emissão...",
              "pontos_de_nao_conformidade": [
                {
                  "item": "Emissão do documento com data futura",
                  "referencia_normativa": "Princípios gerais de auditoria de registros",
                  "observacao": "Na página 1, o campo de data de emissão indica '15 DE DEZEMBRO DE 2025'. Considerando a data da auditoria, este documento é datado no futuro, tornando-o inválido para comprovar a aptidão na data corrente."
                }
              ]
            """

        return f"""
        **Persona:** Você é um Auditor Líder de SST, especialista em conformidade documental. Seu objetivo é validar se o documento apresentado cumpre os requisitos mínimos legais, com foco na **qualidade e completude** das informações, não apenas na sua existência.

        **Contexto Crítico:** A data de hoje é **{data_atual}**.

        **Sua Tarefa (em 3 etapas):**
        1.  **Análise Crítica:** Use o **Checklist de Auditoria Crítica** abaixo para auditar o documento. Seja extremamente rigoroso e não aceite seções que sejam apenas placeholders.
        
        {checklist_instrucoes}

        2.  **Formatação da Resposta:** Apresente suas conclusões no seguinte formato JSON ESTRITO.

        3.  **Justificativa Robusta com Evidências:** Para cada item 'Não Conforme', a 'observacao' DEVE citar a página e explicar por que o requisito do checklist não foi atendido em termos de **qualidade e detalhe**.

        **Estrutura JSON de Saída Obrigatória (use o exemplo como guia):**
        ```json
        {{
          "parecer_final": "Conforme | Não Conforme | Conforme com Ressalvas",
          {json_example}
        }}
        ```
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
