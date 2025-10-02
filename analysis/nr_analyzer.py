import streamlit as st
import pandas as pd
import numpy as np
import google.generativeai as genai
import re
import json
import tempfile
import os
import random
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity
from AI.api_Operation import PDFQA
from operations.sheet import SheetOperations

@st.cache_data(ttl=3600)
def load_preprocessed_rag_base() -> tuple[pd.DataFrame, np.ndarray | None]:
    """
    Carrega o DataFrame e os embeddings pré-processados de arquivos locais.
    Esta função agora apenas carrega e retorna os dados, sem st.toast ou st.error.
    """
    try:
        df = pd.read_pickle("rag_dataframe.pkl")
        embeddings = np.load("rag_embeddings.npy")
        return df, embeddings
    except FileNotFoundError:
        return None, None
    except Exception as e:
        print(f"Falha ao carregar a base de conhecimento pré-processada: {e}")
        return None, None

class NRAnalyzer:
    def __init__(self, spreadsheet_id: str):
        """
        Inicialização que carrega a base RAG e lida com as mensagens de UI.
        """
        self.pdf_analyzer = PDFQA()
        self.sheet_ops = SheetOperations(spreadsheet_id)
        
        with st.spinner("Carregando base de conhecimento..."):
            self.rag_df, self.rag_embeddings = load_preprocessed_rag_base()

        # Verifica o resultado do carregamento e mostra as mensagens apropriadas
        if self.rag_df is None or self.rag_embeddings is None:
            st.error("ERRO CRÍTICO: Arquivos da base de conhecimento ('rag_dataframe.pkl' ou 'rag_embeddings.npy') não encontrados. A funcionalidade de auditoria com IA será desativada.")
            # Garante que os atributos sejam DataFrames vazios para evitar erros posteriores
            self.rag_df = pd.DataFrame()
            self.rag_embeddings = np.array([])
        else:
            st.toast("Base de conhecimento carregada com sucesso.", icon="🧠")
        
        try:
            if not st.secrets.get("general", {}).get("GEMINI_AUDIT_KEY"):
                 st.warning("Chave 'GEMINI_AUDIT_KEY' não encontrada. A busca na base de conhecimento será desativada.")
        except Exception:
            pass

    def _find_semantically_relevant_chunks(self, query_text: str, top_k: int = 5) -> str:
        if self.rag_df.empty or self.rag_embeddings is None or self.rag_embeddings.size == 0:
            return "Base de conhecimento indisponível ou não indexada."

        try:
            query_embedding_result = genai.embed_content(
                model='models/text-embedding-004',  # CORRIGIDO: Modelo atualizado
                content=[query_text],
                task_type="RETRIEVAL_QUERY"
            )
            query_embedding = np.array(query_embedding_result['embedding'])
            
            similarities = cosine_similarity(query_embedding, self.rag_embeddings)[0]
            top_k_indices = similarities.argsort()[-top_k:][::-1]
            relevant_chunks = self.rag_df.iloc[top_k_indices]
            
            return "\n\n---\n\n".join(relevant_chunks['Answer_Chunk'].tolist())
        except Exception as e:
            st.warning(f"Erro durante a busca semântica (verifique a chave de API): {e}")
            return "Erro ao buscar chunks relevantes na base de conhecimento."
            
    def perform_initial_audit(self, doc_info: dict, file_content: bytes) -> dict | None:
        doc_type = doc_info.get("type", "documento")
        norma = doc_info.get("norma", "")
        query = f"Quais são os principais requisitos de conformidade para um {doc_type} da norma {norma}?"
        
        relevant_knowledge = self._find_semantically_relevant_chunks(query, top_k=7)
        
        if "Base de conhecimento indisponível" in relevant_knowledge:
             return {"summary": "Falha na Auditoria", "details": [{"item_verificacao": "Base de conhecimento indisponível.", "status": "Não Conforme"}]}

        prompt = self._get_advanced_audit_prompt(doc_info, relevant_knowledge)
        
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file_content)
                temp_path = temp_file.name
            analysis_result, _ = self.pdf_analyzer.answer_question([temp_path], prompt, task_type='audit')
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
            
            1.  **Informações do Trabalhador:** Verifique se o nome completo e o CPF do trabalhador estão presentes e legíveis.
            
            2.  **Conteúdo Programático e Carga Horária:**
                *   Verifique se o certificado lista o conteúdo programático.
                *   Verifique se a carga horária está explícita e compare com o mínimo exigido pela norma na Base de Conhecimento.
                *   **REGRA:** Se a carga horária for insuficiente ou o conteúdo programático estiver ausente, aponte como 'Não Conforme'.
                
            3.  **Assinaturas dos Responsáveis:**
                *   Verifique se o certificado possui a(s) assinatura(s) do(s) instrutor(es) e/ou do responsável técnico.
                *   **REGRA:** Se estas assinaturas estiverem ausentes, o item é 'Não Conforme'.
                
            4.  **Assinatura do TRABALHADOR (Item Crítico):**
                *   Verifique se o certificado possui um campo para a assinatura do trabalhador e se ele está assinado. A assinatura do trabalhador é a evidência de que ele recebeu o treinamento.
                *   **REGRA:** Se a assinatura do trabalhador estiver ausente, este item é **'Não Conforme'**. Não aceite o documento como totalmente conforme sem ela.

            5.  **Consistência das Datas:** A data de realização do treinamento não pode ser futura em relação à data da auditoria ({data_atual}).
            """
            json_example = """
              "resumo_executivo": "O certificado de treinamento apresenta uma não conformidade crítica devido à ausência da assinatura do trabalhador, o que compromete a comprovação de que o treinamento foi efetivamente recebido.",
              "pontos_de_nao_conformidade": [
                {
                  "item": "Ausência da assinatura do trabalhador",
                  "referencia_normativa": "Princípios de auditoria e NR-01 (registro de treinamentos)",
                  "observacao": "Na página 1, o campo destinado à assinatura do funcionário está em branco. A ausência desta assinatura impede a validação de que o trabalhador participou e concluiu o treinamento."
                }
              ]
            """

        elif doc_type == "ASO":
            checklist_instrucoes = f"""
            **Checklist de Auditoria Obrigatório para Atestado de Saúde Ocupacional (ASO - NR-07):**
            
            1.  **Identificação Completa:** Verifique se o ASO contém o nome completo do trabalhador, número de CPF, e a função desempenhada.
            
            2.  **Dados do Exame:**
                *   Verifique se o tipo de exame (admissional, periódico, demissional, etc.) está claro.
                *   Confira se os riscos ocupacionais específicos (se houver) estão listados.
                *   Verifique se a data de emissão do ASO é explícita e não é uma data futura em relação à data da auditoria ({data_atual}).
            
            3.  **Assinatura do Médico (Item Crítico):**
                *   Verifique se o ASO contém o nome, número do conselho de classe (CRM) e a **assinatura** do médico responsável pelo exame.
                *   **REGRA:** Se a assinatura do médico estiver ausente, o documento é inválido. Aponte como 'Não Conforme'.

            4.  **Assinatura do Trabalhador (Item Crítico):**
                *   Verifique se o ASO contém um campo para a assinatura do trabalhador e se está assinado. A assinatura do trabalhador indica ciência do resultado.
                *   **REGRA:** Embora a ausência da assinatura do trabalhador seja uma falha de registro, a do médico é mais crítica. Se a do trabalhador faltar, aponte como 'Não Conforme' e mencione a falha.
                
            5.  **Parecer de Aptidão:** O documento deve concluir de forma clara se o trabalhador está 'Apto' ou 'Inapto' para a função.
            """
            json_example = """
              "resumo_executivo": "O ASO apresenta uma não conformidade crítica que invalida o documento: a ausência da assinatura do médico responsável. Sem esta assinatura, não há comprovação legal da avaliação de saúde.",
              "pontos_de_nao_conformidade": [
                {
                  "item": "Ausência da assinatura do médico responsável",
                  "referencia_normativa": "NR-07, item 7.5.19.1.g",
                  "observacao": "Na página 1, embora o nome e o CRM do médico estejam impressos, o campo destinado à sua assinatura está em branco. Isso torna o documento legalmente inválido para comprovar a aptidão do trabalhador."
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
        **Persona:** Você é um Auditor Líder de SST. Sua análise é baseada em duas fontes: (1) As regras da sua tarefa e (2) a Base de Conhecimento fornecida.

        **Contexto Crítico:** A data de hoje é **{data_atual}**.

        **Base de Conhecimento Normativa (Fonte da Verdade):**
        A seguir estão trechos de Normas Regulamentadoras. USE ESTA FONTE para preencher a chave "referencia_normativa" no JSON.
        ---
        {relevant_knowledge}
        ---

        **Sua Tarefa (Regras de Análise):**
        1.  **Análise Crítica:** Use o **Checklist de Auditoria** abaixo para auditar o documento PDF.
        
            {checklist_instrucoes}

        2.  **Formatação da Resposta:** Apresente suas conclusões no seguinte formato JSON ESTRITO.

        3.  **Justificativa Robusta com Evidências:**
            *   Para cada "ponto_de_nao_conformidade", a 'observacao' deve citar a página e a evidência do PDF.
            *   **REGRA CRUCIAL:** A chave "referencia_normativa" DEVE ser preenchida com o item ou seção relevante encontrado na **'Base de Conhecimento Normativa'** acima. **NUNCA cite o 'Checklist de Auditoria' como referência.**

        **Estrutura JSON de Saída Obrigatória (Siga o exemplo):**
        ```json
        {{
          "parecer_final": "Conforme | Não Conforme | Conforme com Ressalvas",
          "resumo_executivo": "...",
          "pontos_de_nao_conformidade": [
            {{
              "item": "Ausência da assinatura do trabalhador no certificado",
              "referencia_normativa": "NR-01, item 1.7.1.1",
              "observacao": "Na página 1, o campo para assinatura do funcionário está em branco. A Base de Conhecimento, no item 1.7.1.1 da NR-01, exige a assinatura do trabalhador como item obrigatório no certificado."
            }}
          ]
        }}
        ```
        """

    def _parse_advanced_audit_result(self, json_string: str) -> dict:
        try:
            match = re.search(r'\{.*\}', json_string, re.DOTALL)
            if not match:
                return {"summary": "Falha na Análise", "details": [{"item_verificacao": "Resposta Bruta da IA", "observacao": json_string, "status": "Não Conforme"}]}
            data = json.loads(match.group(0))
            summary = data.get("parecer_final", "Indefinido")
            details = []
            
            if data.get("resumo_executivo"):
                status_resumo = "Conforme" if "conforme" in summary.lower() else "Não Conforme"
                details.append({"item_verificacao": "Resumo Executivo da Auditoria", "referencia_normativa": "N/A", "observacao": data["resumo_executivo"], "status": status_resumo})
            
            for item in data.get("pontos_de_nao_conformidade", []):
                details.append({"item_verificacao": item.get("item", ""), "referencia_normativa": item.get("referencia_normativa", ""), "observacao": item.get("observacao", ""), "status": "Não Conforme"})

            for item in data.get("pontos_de_ressalva", []):
                details.append({
                    "item_verificacao": f"Ressalva: {item.get('item', '')}",
                    "referencia_normativa": item.get("referencia_normativa", ""),
                    "observacao": item.get("observacao", ""),
                    "status": "Ressalva"
                })

            return {"summary": summary, "details": details}
        except (json.JSONDecodeError, AttributeError):
            return {"summary": "Falha na Análise (Erro de JSON)", "details": [{"item_verificacao": "Resposta Bruta da IA", "observacao": json_string, "status": "Não Conforme"}]}

    def create_action_plan_from_audit(self, audit_result: dict, company_id: str, doc_id: str, employee_id: str | None = None):
        """
        O employee_id ainda pode ser passado para o LOG, mas NÃO será inserido na planilha.
        """
        if "não conforme" not in audit_result.get("summary", "").lower():
            return 0
            
        actionable_items = [
            item for item in audit_result.get("details", []) 
            if item.get("status", "").lower() == "não conforme" 
            and "resumo executivo" not in item.get("item_verificacao", "").lower()
        ]
        
        if not actionable_items: 
            return 0
        
        from operations.action_plan import ActionPlanManager
        action_plan_manager = ActionPlanManager(self.sheet_ops.spreadsheet_id)
        
        audit_run_id = f"audit_{doc_id}_{random.randint(1000, 9999)}"
        created_count = 0
        
        for item in actionable_items:
            # ✅ Passa employee_id apenas para o LOG interno
            if action_plan_manager.add_action_item(
                audit_run_id, company_id, doc_id, item, employee_id=employee_id
            ):
                created_count += 1
        
        if created_count > 0:
            st.info(f"{created_count} item(ns) de não conformidade foram adicionados ao Plano de Ação.")
        
        return created_count
