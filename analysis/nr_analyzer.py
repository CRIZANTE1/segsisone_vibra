import streamlit as st
from AI.api_Operation import PDFQA
import tempfile
import os
import pandas as pd
import re
from gdrive.config import get_credentials_dict
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

@st.cache_data(ttl=3600)
def load_nr_knowledge_base(sheet_id: str) -> pd.DataFrame:
    """Carrega a planilha de RAG em um DataFrame do Pandas usando gspread."""
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = get_credentials_dict()
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.sheet1
        return pd.DataFrame(worksheet.get_all_records())
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Planilha de RAG com ID '{sheet_id}' não encontrada.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Falha ao carregar a base de conhecimento RAG: {e}")
        return pd.DataFrame()

class NRAnalyzer:
    def __init__(self):
        self.pdf_analyzer = PDFQA()
        try:
            creds_dict = get_credentials_dict()
            creds = Credentials.from_service_account_info(creds_dict)
            self.drive_service = build('drive', 'v3', credentials=creds)
        except Exception as e:
            st.error(f"Falha ao inicializar o serviço do Google Drive: {e}")
            self.drive_service = None
        
        try:
            self.nr_sheets_map = {
                "NR-01": st.secrets.app_settings.get("rag_nr01_id"),
                "NR-07": st.secrets.app_settings.get("rag_nr07_id"),
                "NR-34": st.secrets.app_settings.get("rag_nr34_id"),
                "NR-35": st.secrets.app_settings.get("rag_nr35_id"),
            }
            self.nr_sheets_map = {k: v for k, v in self.nr_sheets_map.items() if v}
        except (AttributeError, KeyError):
            st.error("A seção [app_settings] não foi encontrada no seu secrets.toml.")
            self.nr_sheets_map = {}

    def _download_file_from_drive(self, file_id: str) -> bytes:
        if not self.drive_service:
            raise Exception("Serviço do Google Drive não inicializado.")
        request = self.drive_service.files().get_media(fileId=file_id)
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return file_buffer.getvalue()

  
    def _find_relevant_chunks(self, rag_df: pd.DataFrame, keywords: list[str]) -> str:
        """Busca por palavras-chave e retorna os trechos com a referência da seção."""
        if rag_df.empty: return "Base de conhecimento indisponível."
        regex_pattern = '|'.join(map(re.escape, keywords))
        rag_df['Keywords'] = rag_df['Keywords'].astype(str)
        relevant_rows = rag_df[rag_df['Keywords'].str.contains(regex_pattern, case=False, na=False)]
        
        if relevant_rows.empty: return "Nenhum trecho relevante encontrado para as palavras-chave."
            
       
        knowledge_text = "\n\n".join(
            f"Referência Normativa {row.get('Section_Number', '')}: {row.get('Answer_Chunk', '')}" 
            for _, row in relevant_rows.iterrows()
        )
        return knowledge_text

    def _get_analysis_prompt(self, doc_type: str, norma_analisada: str, nr_knowledge_base: str, keywords: list[str]) -> str:
        """Retorna o prompt aprimorado que exige a referência normativa."""
        return f"""
        Você é um auditor de Segurança do Trabalho altamente detalhista. Sua tarefa é analisar o documento em PDF fornecido e compará-lo com os trechos relevantes da {norma_analisada}.

        **Base de Conhecimento Relevante (Trechos da {norma_analisada} sobre {', '.join(keywords)}):**
        {nr_knowledge_base}
        
        **Tarefa:**
        Verifique os seguintes itens de conformidade no documento. Para cada item, responda em uma nova linha usando o seguinte formato ESTRITO de 4 partes, separadas por '|':
        
        `ITEM: [Nome do Item] | STATUS: [Conforme/Não Conforme/Não Aplicável] | OBSERVAÇÃO: [Sua justificativa] | REFERÊNCIA: [Cite o número da Referência Normativa usada, ex: 'Referência Normativa Exemplo NR 34 Item 34.5.1']`
        
        **Itens de Verificação para {doc_type}:**
        - ITEM: Conformidade com o conteúdo programático/estrutura mínima | STATUS: [] | OBSERVAÇÃO: [] | REFERÊNCIA: []
        - ITEM: Conformidade com carga horária e validade | STATUS: [] | OBSERVAÇÃO: [] | REFERÊNCIA: []
        - ITEM: Presença de informações obrigatórias (responsáveis, assinaturas, etc.) | STATUS: [] | OBSERVAÇÃO: [] | REFERÊNCIA: []
        - ITEM: Pontos de atenção ou não conformidades específicas | STATUS: [] | OBSERVAÇÃO: [] | REFERÊNCIA: []
        - ITEM: Resumo geral da conformidade | STATUS: [] | OBSERVAÇÃO: [] | REFERÊNCIA: []
        """

  
    def _parse_analysis_to_dataframe(self, analysis_result: str) -> pd.DataFrame:
        """Converte a resposta em texto da IA em um DataFrame do Pandas, agora com 4 colunas."""
        lines = analysis_result.strip().split('\n')
        data = []
        for line in lines:
            line = line.strip()
            # Procura por uma linha que contenha os 4 marcadores
            if all(marker in line for marker in ["ITEM:", "STATUS:", "OBSERVAÇÃO:", "REFERÊNCIA:"]):
                try:
                    parts = line.split('|', 3) # Divide no máximo 3 vezes para obter 4 partes
                    if len(parts) == 4:
                        item = parts[0].replace("ITEM:", "").strip()
                        status = parts[1].replace("STATUS:", "").strip()
                        obs = parts[2].replace("OBSERVAÇÃO:", "").strip()
                        ref = parts[3].replace("REFERÊNCIA:", "").strip()
                        data.append({
                            "Item de Verificação": item, 
                            "Status": status, 
                            "Observação": obs,
                            "Referência Normativa": ref
                        })
                except Exception:
                    continue
        
        if not data:
            return pd.DataFrame([{"Item de Verificação": "Análise Geral", "Status": "Não Estruturado", "Observação": analysis_result, "Referência Normativa": "N/A"}])
            
        return pd.DataFrame(data)

    def analyze_document_compliance(self, document_url: str, doc_info: dict) -> pd.DataFrame | None:
        doc_type = doc_info.get("type")
        norma_analisada = doc_info.get("norma")
        
        st.info(f"Iniciando análise de conformidade do documento '{doc_info.get('label')}' contra a {norma_analisada}...")

        sheet_id = self.nr_sheets_map.get(norma_analisada)
        if not sheet_id:
            st.error(f"Análise não disponível. Nenhuma planilha de RAG configurada para {norma_analisada}.")
            return None
        
        with st.spinner(f"Carregando base de conhecimento da {norma_analisada}..."):
            rag_df = load_nr_knowledge_base(sheet_id)

        if rag_df.empty: return None
        
        keywords = ["Requisitos", "Documentação"] # Default
        if doc_type == "PGR": keywords = ["PGR", "Gerenciamento de Riscos", "Inventário", "Plano de ação"]
        elif doc_type == "PCMSO": keywords = ["PCMSO", "Exames médicos", "ASO", "Relatório analítico"]
        elif doc_type == "ASO": keywords = ["ASO", "Atestado de Saúde", "Exame", "Médico"]
        elif doc_type == "Treinamento": keywords = ["Treinamento", "Capacitação", "Carga horária", "Certificado", norma_analisada]
            
        with st.spinner("Buscando informações relevantes na base de conhecimento..."):
            relevant_knowledge = self._find_relevant_chunks(rag_df, keywords)

        temp_path = None
        try:
            file_id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', document_url)
            if not file_id_match:
                st.error("Não foi possível extrair o ID do arquivo da URL do Google Drive.")
                return None
            
            file_id = file_id_match.group(1)
            
            with st.spinner("Baixando documento do Google Drive..."):
                file_content = self._download_file_from_drive(file_id)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file_content)
                temp_path = temp_file.name
                
        except Exception as e:
            st.error(f"Falha ao baixar ou processar o arquivo do Google Drive."); st.code(str(e))
            if temp_path and os.path.exists(temp_path): os.unlink(temp_path)
            return None

        prompt = self._get_analysis_prompt(doc_type, norma_analisada, relevant_knowledge, keywords)

        try:
            with st.spinner("IA realizando a análise profunda..."):
                analysis_result, _ = self.pdf_analyzer.answer_question([temp_path], prompt)
            
            if analysis_result:
                return self._parse_analysis_to_dataframe(analysis_result)
            else:
                st.warning("A IA não conseguiu gerar uma análise.")
                return None
        except Exception as e:
            st.error(f"Ocorreu um erro durante a análise profunda: {e}"); return None
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
