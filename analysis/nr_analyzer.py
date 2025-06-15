# /mount/src/segsisone/analysis/nr_analyzer.py

import streamlit as st
from AI.api_Operation import PDFQA
import tempfile
import os
import gdown
import pygsheets
from gdrive.config import get_credentials_dict # Importa a função correta

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
        st.error(f"Planilha de NR com ID '{sheet_id}' não encontrada. Verifique o ID e as permissões de compartilhamento.")
        return ""
    except Exception as e:
        st.error(f"Falha ao carregar a base de conhecimento da planilha com ID {sheet_id}: {e}")
        return ""

class NRAnalyzer:
    def __init__(self):
        self.pdf_analyzer = PDFQA()
        # Mapeamento da NORMA para o ID da Planilha Google correspondente
        self.nr_sheets_map = {
            "NR-01": "1-3tT8e7nhMhvtxpSne6kJdhAlZJQFIb3lZ7Kj5_Y620",
            "NR-07": "1SY4XB7MtbvgienYzE12_GiBFx3ArEdo3N_ovtZQCOUk",
            "NR-34": "1STAeNSoTMfXGAkW1c--1uyXZAJTuY34WydoVq0N9-lc",
            "NR-35": "1ApGGwkKqWi_RSLt34SLdvb_-TQFj2R5KLABYBkwFzng",
            # Adicione outras NRs e seus IDs de planilha aqui
        }

    def _get_analysis_prompt(self, doc_type: str, norma_analisada: str, nr_knowledge_base: str) -> str:
        """Retorna o prompt apropriado com base no tipo de documento."""
        
        # Prompt para Programas (PGR, PCMSO)
        if doc_type in ["PGR", "PCMSO"]:
            return f"""
            Você é um especialista em Segurança do Trabalho e sua tarefa é auditar um programa de gerenciamento.
            
            **Base de Conhecimento (Texto da {norma_analisada}):**
            {nr_knowledge_base}
            
            **Tarefa:**
            Com base no texto da norma fornecido acima, analise o documento do programa ({doc_type}) em PDF e responda em formato Markdown:
            
            1.  **Estrutura Mínima:** O documento possui a estrutura mínima exigida pela {norma_analisada}? (ex: inventário de riscos, plano de ação para o PGR). Verifique e liste os itens obrigatórios, marcando com (✅) os presentes e (❌) os ausentes.
            2.  **Coerência:** As informações apresentadas são coerentes com os objetivos do programa descritos na norma?
            3.  **Resumo da Auditoria:** Forneça um resumo final sobre a conformidade do documento, destacando os pontos fortes e as principais não conformidades ou pontos de melhoria.
            """
        
        # Prompt para Certificados de Treinamento
        elif doc_type == "Treinamento":
            return f"""
            Você é um especialista em Segurança do Trabalho e sua tarefa é auditar um certificado de treinamento.
            
            **Base de Conhecimento (Texto da {norma_analisada}):**
            {nr_knowledge_base}
            
            **Tarefa:**
            Com base no texto da norma fornecido acima, analise o certificado em PDF e responda em formato Markdown:
            
            1.  **Conteúdo Programático:** O certificado menciona um conteúdo programático? Se sim, ele é compatível com os requisitos mínimos da {norma_analisada}?
            2.  **Carga Horária e Validade:** A carga horária e a validade do treinamento estão de acordo com o exigido pela {norma_analisada}? Justifique.
            3.  **Informações Obrigatórias:** O certificado contém todas as informações obrigatórias para ser considerado válido (nome do trabalhador, conteúdo, data, local, nome e assinatura dos instrutores)? Marque (✅) para presentes e (❌) para ausentes.
            4.  **Resumo da Auditoria:** Forneça um resumo final sobre a conformidade do certificado, apontando possíveis falhas.
            """
            
        # Prompt padrão para outros tipos de documentos
        else:
            return f"""
            Você é um especialista em Segurança do Trabalho. Analise o documento em PDF fornecido.
            Use a base de conhecimento da {norma_analisada} abaixo para verificar a conformidade do documento.
            
            **Base de Conhecimento (Texto da {norma_analisada}):**
            {nr_knowledge_base}
            
            **Tarefa:**
            Faça um resumo dos pontos principais do documento e aponte qualquer possível não conformidade em relação à norma fornecida.
            """

    def analyze_document_compliance(self, document_url: str, doc_info: dict) -> str:
        
        doc_type = doc_info.get("type")
        norma_analisada = doc_info.get("norma")
        
        st.info(f"Iniciando análise de conformidade do documento '{doc_info.get('label')}' contra a {norma_analisada}...")

        sheet_id = self.nr_sheets_map.get(norma_analisada)
        if not sheet_id:
            return f"Análise não disponível. Não há planilha de referência configurada para a {norma_analisada} em `nr_analyzer.py`."
        
        with st.spinner(f"Carregando base de conhecimento da {norma_analisada}..."):
            nr_knowledge_base = load_nr_knowledge_base(sheet_id)

        if not nr_knowledge_base:
            return f"Não foi possível continuar a análise sem a base de conhecimento para a {norma_analisada}."
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                with st.spinner("Baixando documento do Google Drive..."):
                    gdown.download(url=document_url, output=temp_file.name, quiet=True, fuzzy=True)
                temp_path = temp_file.name
        except Exception as e:
            st.error(f"Falha ao baixar o documento do Google Drive: {document_url}."); st.code(str(e))
            if 'temp_path' in locals() and os.path.exists(temp_path): os.unlink(temp_path)
            return "Erro no download do documento."

        # Seleciona o prompt correto
        prompt = self._get_analysis_prompt(doc_type, norma_analisada, nr_knowledge_base)

        try:
            with st.spinner("IA realizando a análise profunda..."):
                analysis_result, _ = self.pdf_analyzer.answer_question([temp_path], prompt)
            os.unlink(temp_path)
            return analysis_result if analysis_result else "A IA não conseguiu gerar uma análise."
        except Exception as e:
            st.error(f"Ocorreu um erro durante a análise profunda: {e}"); return "Falha na análise."