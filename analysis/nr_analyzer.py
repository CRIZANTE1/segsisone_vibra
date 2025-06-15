import streamlit as st
from AI.api_Operation import PDFQA
import tempfile
import os
import gdown
import pygsheets
import pandas as pd
import re
from gdrive.config import get_credentials_dict

@st.cache_data(ttl=3600)
def load_nr_knowledge_base(sheet_id: str) -> str:
    """Carrega o conteúdo de TODAS as abas de uma planilha específica e concatena."""
    try:
        creds_dict = get_credentials_dict()
        gc = pygsheets.authorize(service_account_data=creds_dict)
        spreadsheet = gc.open_by_key(sheet_id)
        full_text = ""
        for worksheet in spreadsheet.worksheets():
            sheet_text = "\n".join([" ".join(map(str, row)) for row in worksheet.get_all_values()])
            full_text += f"\n\n--- Início da {worksheet.title} ---\n{sheet_text}\n--- Fim da {worksheet.title} ---"
        return full_text
    except pygsheets.exceptions.SpreadsheetNotFound:
        st.error(f"Planilha de NR com ID '{sheet_id}' não encontrada. Verifique o ID no secrets.toml e as permissões de compartilhamento.")
        return ""
    except Exception as e:
        st.error(f"Falha ao carregar a base de conhecimento da planilha com ID {sheet_id}: {e}")
        st.warning("Verifique se o e-mail da conta de serviço tem permissão de 'Leitor' nesta planilha de NR.")
        return ""

class NRAnalyzer:
    def __init__(self):
        self.pdf_analyzer = PDFQA()
        # Carrega o mapeamento de NRs diretamente da seção [app_settings] dos secrets
        try:
            self.nr_sheets_map = {
                "NR-01": st.secrets.app_settings.get("rag_nr01_id"),
                "NR-07": st.secrets.app_settings.get("rag_nr07_id"),
                "NR-34": st.secrets.app_settings.get("rag_nr34_id"),
                "NR-35": st.secrets.app_settings.get("rag_nr35_id"),
                # Adicione outras NRs aqui, lendo dos secrets
                # Ex: "NR-10": st.secrets.app_settings.get("rag_nr10_id"),
            }
            # Filtra entradas que não foram encontradas nos secrets (retornam None)
            self.nr_sheets_map = {k: v for k, v in self.nr_sheets_map.items() if v}
        except (AttributeError, KeyError):
            st.error("A seção [app_settings] ou as chaves rag_nrXX_id não foram encontradas no seu arquivo secrets.toml.")
            self.nr_sheets_map = {}


    def _get_analysis_prompt(self, doc_type: str, norma_analisada: str, nr_knowledge_base: str) -> str:
        """Retorna o prompt apropriado com base no tipo de documento."""
        
        # Prompt para Programas (PGR, PCMSO)
        if doc_type in ["PGR", "PCMSO"]:
            return f"""
            Você é um auditor de Segurança do Trabalho. Sua tarefa é analisar o documento em PDF fornecido e compará-lo com a base de conhecimento da {norma_analisada}.

            **Base de Conhecimento (Texto da {norma_analisada}):**
            {nr_knowledge_base}
            
            **Tarefa:**
            Verifique cada um dos itens de conformidade listados abaixo. Para cada item, responda em uma nova linha usando o seguinte formato ESTRITO:
            
            `ITEM: [Nome do Item] | STATUS: [Conforme/Não Conforme/Não Aplicável] | OBSERVAÇÃO: [Sua justificativa ou observação]`
            
            **Itens de Verificação para o documento ({doc_type}):**
            - ITEM: Estrutura Mínima do Documento | STATUS: [] | OBSERVAÇÃO: []
            - ITEM: Inventário de Riscos Ocupacionais | STATUS: [] | OBSERVAÇÃO: []
            - ITEM: Plano de Ação | STATUS: [] | OBSERVAÇÃO: []
            - ITEM: Vigência e Periodicidade | STATUS: [] | OBSERVAÇÃO: []
            - ITEM: Identificação do Responsável Técnico | STATUS: [] | OBSERVAÇÃO: []
            """
        
        # Prompt para Certificados de Treinamento
        elif doc_type == "Treinamento":
            return f"""
            Você é um especialista em Segurança do Trabalho e sua tarefa é auditar um certificado de treinamento.
            
            **Base de Conhecimento (Texto da {norma_analisada}):**
            {nr_knowledge_base}
            
            **Tarefa:**
            Verifique cada um dos itens de conformidade listados abaixo. Para cada item, responda em uma nova linha usando o seguinte formato ESTRITO:
            
            `ITEM: [Nome do Item] | STATUS: [Conforme/Não Conforme/Não Aplicável] | OBSERVAÇÃO: [Sua justificativa ou observação]`
            
            **Itens de Verificação para o documento ({doc_type}):**
            - ITEM: Conteúdo Programático Mínimo | STATUS: [] | OBSERVAÇÃO: []
            - ITEM: Carga Horária Mínima | STATUS: [] | OBSERVAÇÃO: []
            - ITEM: Validade do Treinamento | STATUS: [] | OBSERVAÇÃO: []
            - ITEM: Identificação do Responsável Técnico/Instrutor | STATUS: [] | OBSERVAÇÃO: []
            - ITEM: Assinatura dos Instrutores e Responsáveis | STATUS: [] | OBSERVAÇÃO: []
            - ITEM: Informações do Trabalhador (Nome e CPF) | STATUS: [] | OBSERVAÇÃO: []
            """
            
        # Prompt padrão para outros tipos de documentos (como ASO)
        else:
            return f"""
            Você é um especialista em Segurança do Trabalho. Analise o documento em PDF fornecido.
            Use a base de conhecimento da {norma_analisada} abaixo para verificar a conformidade do documento.
            
            **Base de Conhecimento (Texto da {norma_analisada}):**
            {nr_knowledge_base}

            **Tarefa:**
            Verifique cada um dos itens de conformidade listados abaixo. Para cada item, responda em uma nova linha usando o seguinte formato ESTRITO:
            
            `ITEM: [Nome do Item] | STATUS: [Conforme/Não Conforme/Não Aplicável] | OBSERVAÇÃO: [Sua justificativa ou observação]`
            
            **Itens de Verificação para o documento ({doc_type}):**
            - ITEM: Identificação do Tipo de Exame (Admissional, Periódico, etc.) | STATUS: [] | OBSERVAÇÃO: []
            - ITEM: Indicação dos Riscos Ocupacionais | STATUS: [] | OBSERVAÇÃO: []
            - ITEM: Indicação dos Exames Realizados | STATUS: [] | OBSERVAÇÃO: []
            - ITEM: Data de Emissão e Validade | STATUS: [] | OBSERVAÇÃO: []
            - ITEM: Identificação do Médico do Trabalho (CRM) | STATUS: [] | OBSERVAÇÃO: []
            """

    def _parse_analysis_to_dataframe(self, analysis_result: str) -> pd.DataFrame:
        """Converte a resposta em texto da IA em um DataFrame do Pandas."""
        lines = analysis_result.strip().split('\n')
        data = []
        for line in lines:
            line = line.strip()
            if line.startswith("ITEM:") and "STATUS:" in line and "OBSERVAÇÃO:" in line:
                try:
                    item_part, status_part, obs_part = line.split('|', 2)
                    item = item_part.replace("ITEM:", "").strip()
                    status = status_part.replace("STATUS:", "").strip()
                    obs = obs_part.replace("OBSERVAÇÃO:", "").strip()
                    data.append({"Item de Verificação": item, "Status": status, "Observação": obs})
                except ValueError:
                    continue
        
        if not data:
            return pd.DataFrame([{"Item de Verificação": "Análise Geral", "Status": "Não Estruturado", "Observação": analysis_result}])
            
        return pd.DataFrame(data)

    def analyze_document_compliance(self, document_url: str, doc_info: dict) -> pd.DataFrame | None:
        doc_type = doc_info.get("type")
        norma_analisada = doc_info.get("norma")
        
        st.info(f"Iniciando análise de conformidade do documento '{doc_info.get('label')}' contra a {norma_analisada}...")

        sheet_id = self.nr_sheets_map.get(norma_analisada)
        if not sheet_id:
            st.error(f"Análise não disponível. Nenhuma planilha de RAG configurada para {norma_analisada} no arquivo secrets.toml.")
            return None
        
        with st.spinner(f"Carregando base de conhecimento da {norma_analisada}..."):
            nr_knowledge_base = load_nr_knowledge_base(sheet_id)

        if not nr_knowledge_base:
            return None
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                with st.spinner("Baixando documento do Google Drive..."):
                    gdown.download(url=document_url, output=temp_file.name, quiet=True, fuzzy=True)
                temp_path = temp_file.name
        except Exception as e:
            st.error(f"Falha ao baixar o documento do Google Drive: {document_url}."); st.code(str(e))
            if 'temp_path' in locals() and os.path.exists(temp_path): os.unlink(temp_path)
            return None

        prompt = self._get_analysis_prompt(doc_type, norma_analisada, nr_knowledge_base)

        try:
            with st.spinner("IA realizando a análise profunda..."):
                analysis_result, _ = self.pdf_analyzer.answer_question([temp_path], prompt)
            os.unlink(temp_path)
            
            if analysis_result:
                return self._parse_analysis_to_dataframe(analysis_result)
            else:
                st.warning("A IA não conseguiu gerar uma análise.")
                return None
        except Exception as e:
            st.error(f"Ocorreu um erro durante a análise profunda: {e}"); return None
