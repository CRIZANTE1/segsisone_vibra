import streamlit as st
from AI.api_Operation import PDFQA
import tempfile
import os
import gdown
import pandas as pd
import re
from gdrive.config import get_credentials_dict
import gspread 
from google.oauth2.service_account import Credentials 

@st.cache_data(ttl=3600)
def load_nr_knowledge_base(sheet_id: str) -> pd.DataFrame:
    """
    Carrega a planilha de RAG em um DataFrame do Pandas usando gspread.
    """
    try:
        # Define os escopos necessários para o Google Sheets e Drive API
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Pega as credenciais do secrets.toml usando a função já existente
        creds_dict = get_credentials_dict()
        
        # Cria um objeto de credenciais a partir do dicionário
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        
        # Autoriza o gspread com as credenciais
        gc = gspread.authorize(creds)
        
        # Abre a planilha pelo ID e pega a primeira aba
        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.sheet1
        
        # Converte a aba em um DataFrame do Pandas
        data = pd.DataFrame(worksheet.get_all_records())
        return data
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Planilha de RAG com ID '{sheet_id}' não encontrada. Verifique o ID no secrets.toml e as permissões de compartilhamento.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Falha ao carregar a base de conhecimento RAG da planilha com ID {sheet_id}: {e}")
        st.warning("Verifique se o e-mail da conta de serviço tem permissão de 'Leitor' nesta planilha de NR.")
        return pd.DataFrame()

class NRAnalyzer:
    def __init__(self):
        self.pdf_analyzer = PDFQA()
        try:
            self.nr_sheets_map = {
                "NR-01": st.secrets.app_settings.get("rag_nr01_id"),
                "NR-07": st.secrets.app_settings.get("rag_nr07_id"),
                "NR-34": st.secrets.app_settings.get("rag_nr34_id"),
                "NR-35": st.secrets.app_settings.get("rag_nr35_id"),
            }
            self.nr_sheets_map = {k: v for k, v in self.nr_sheets_map.items() if v}
        except (AttributeError, KeyError):
            st.error("A seção [app_settings] ou as chaves rag_nrXX_id não foram encontradas no seu arquivo secrets.toml.")
            self.nr_sheets_map = {}

    def _find_relevant_chunks(self, rag_df: pd.DataFrame, keywords: list[str]) -> str:
        """
        Busca no DataFrame de RAG por linhas que contenham as palavras-chave e retorna os trechos de resposta.
        """
        if rag_df.empty:
            return "Base de conhecimento indisponível."
        
        regex_pattern = '|'.join(keywords)
        rag_df['Keywords'] = rag_df['Keywords'].astype(str)
        relevant_rows = rag_df[rag_df['Keywords'].str.contains(regex_pattern, case=False, na=False)]
        
        if relevant_rows.empty:
            return "Nenhum trecho relevante encontrado para as palavras-chave."
            
        knowledge_text = "\n\n".join(relevant_rows['Answer_Chunk'].tolist())
        return knowledge_text

    def _get_analysis_prompt(self, doc_type: str, norma_analisada: str, nr_knowledge_base: str, keywords: list[str]) -> str:
        """Retorna o prompt apropriado com base no tipo de documento e palavras-chave."""
        
        return f"""
        Você é um auditor de Segurança do Trabalho. Sua tarefa é analisar o documento em PDF fornecido e compará-lo com os trechos relevantes da {norma_analisada} que encontrei para você.

        **Base de Conhecimento Relevante (Trechos da {norma_analisada} sobre {', '.join(keywords)}):**
        {nr_knowledge_base}
        
        **Tarefa:**
        Verifique os seguintes itens de conformidade no documento, usando a base de conhecimento acima. Para cada item, responda em uma nova linha usando o seguinte formato ESTRITO:
        
        `ITEM: [Nome do Item] | STATUS: [Conforme/Não Conforme/Não Aplicável] | OBSERVAÇÃO: [Sua justificativa citando a norma, se possível]`
        
        **Itens de Verificação para {doc_type}:**
        - ITEM: Conformidade com o conteúdo programático/estrutura mínima | STATUS: [] | OBSERVAÇÃO: []
        - ITEM: Conformidade com carga horária e validade | STATUS: [] | OBSERVAÇÃO: []
        - ITEM: Presença de informações obrigatórias (responsáveis, assinaturas, etc.) | STATUS: [] | OBSERVAÇÃO: []
        - ITEM: Pontos de atenção ou não conformidades específicas | STATUS: [] | OBSERVAÇÃO: []
        - ITEM: Resumo geral da conformidade | STATUS: [] | OBSERVAÇÃO: []
        """

    def _parse_analysis_to_dataframe(self, analysis_result: str) -> pd.DataFrame:
        lines = analysis_result.strip().split('\n')
        data = []
        for line in lines:
            line = line.strip()
            if line.startswith("ITEM:") and "STATUS:" in line and "OBSERVAÇÃO:" in line:
                try:
                    parts = line.split('|', 2)
                    item = parts[0].replace("ITEM:", "").strip()
                    status = parts[1].replace("STATUS:", "").strip()
                    obs = parts[2].replace("OBSERVAÇÃO:", "").strip()
                    data.append({"Item de Verificação": item, "Status": status, "Observação": obs})
                except ValueError: continue
        
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
            rag_df = load_nr_knowledge_base(sheet_id)

        if rag_df.empty:
            return None
        
        if doc_type == "PGR":
            keywords = ["PGR", "Gerenciamento de Riscos", "Inventário de riscos", "Plano de ação"]
        elif doc_type == "PCMSO":
            keywords = ["PCMSO", "Exames médicos", "ASO", "Relatório analítico"]
        elif doc_type == "ASO":
            keywords = ["ASO", "Atestado de Saúde", "Exame admissional", "Exame periódico", "Exame demissional"]
        elif doc_type == "Treinamento":
            keywords = ["Treinamento", "Capacitação", "Carga horária", "Certificado", norma_analisada]
        else:
            keywords = ["Requisitos", "Documentação"]
            
        with st.spinner("Buscando informações relevantes na base de conhecimento..."):
            relevant_knowledge = self._find_relevant_chunks(rag_df, keywords)

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                with st.spinner("Baixando documento do Google Drive..."):
                    gdown.download(url=document_url, output=temp_file.name, quiet=True, fuzzy=True)
                temp_path = temp_file.name
        except Exception as e:
            st.error(f"Falha ao baixar o documento do Google Drive: {document_url}."); st.code(str(e))
            if 'temp_path' in locals() and os.path.exists(temp_path): os.unlink(temp_path)
            return None

        prompt = self._get_analysis_prompt(doc_type, norma_analisada, relevant_knowledge, keywords)

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
