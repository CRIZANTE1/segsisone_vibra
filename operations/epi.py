import streamlit as st
import pandas as pd
import json
import tempfile
import os
import re
from operations.sheet import SheetOperations
from AI.api_Operation import PDFQA
from operations.cached_loaders import load_epis_df
from operations.file_hash import calcular_hash_arquivo, verificar_hash_seguro

class EPIManager:
    def __init__(self, spreadsheet_id: str):
        self.sheet_ops = SheetOperations(spreadsheet_id)
        self.spreadsheet_id = spreadsheet_id
        self._pdf_analyzer = None
        self.load_epi_data()

    @property
    def pdf_analyzer(self):
        if self._pdf_analyzer is None:
            self._pdf_analyzer = PDFQA()
        return self._pdf_analyzer

    def load_epi_data(self):
        try:
            # Substitui a lógica antiga
            self.epi_df = load_epis_df(self.spreadsheet_id)
        except Exception as e:
            st.error(f"Erro ao carregar dados de EPI: {str(e)}")
            self.epi_df = pd.DataFrame()

    def get_epi_by_employee(self, employee_id):
        """
        Retorna uma lista contendo APENAS o registro mais recente para cada tipo
        de EPI (agrupado pela descrição), garantindo que a lista esteja sempre atualizada.
        """
        if self.epi_df.empty:
            return pd.DataFrame()
            
        epi_docs = self.epi_df[self.epi_df['funcionario_id'] == str(employee_id)].copy()
        if epi_docs.empty:
            return pd.DataFrame()
    
        if 'data_entrega' not in epi_docs.columns:
            return pd.DataFrame() # Não podemos prosseguir sem a data
    
        epi_docs['data_entrega_dt'] = pd.to_datetime(epi_docs['data_entrega'], format='%d/%m/%Y', errors='coerce')
        epi_docs.dropna(subset=['data_entrega_dt'], inplace=True)
        if epi_docs.empty: return pd.DataFrame()
    
        epi_docs['descricao_normalizada'] = epi_docs['descricao_epi'].astype(str).str.strip().str.lower()
        epi_docs = epi_docs.sort_values('data_entrega_dt', ascending=False)        
        latest_epis = epi_docs.groupby('descricao_normalizada').head(1).copy()        
        latest_epis = latest_epis.drop(columns=['data_entrega_dt', 'descricao_normalizada'])
        
        return latest_epis.sort_values('data_entrega', ascending=False) # Ordena para exibição

    def analyze_epi_pdf(self, pdf_file):
        """Analisa o PDF da Ficha de EPI usando IA para extrair os itens."""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(pdf_file.getvalue())
                temp_path = temp_file.name

            structured_prompt = """
            Você é um especialista em análise de Fichas de Controle de EPI. Sua tarefa é analisar o documento e extrair as informações da tabela de equipamentos fornecidos e o nome do funcionário.

            **REGRAS OBRIGATÓRIAS:**
            1.  Responda **APENAS com um bloco de código JSON válido**. Não inclua nenhum texto antes ou depois do JSON.
            2.  O JSON principal deve ter duas chaves: "nome_funcionario" e "itens_epi".
            3.  A chave "itens_epi" deve conter um **array de objetos**.
            4.  Cada objeto no array deve representar um item da ficha e conter as chaves: "item_numero", "descricao", "data_entrega" (formato DD/MM/AAAA) e "ca".
            5.  Se um valor não for encontrado para uma chave (ex: CA), o valor no JSON deve ser **null** ou uma string vazia.
            6.  Ignore as linhas vazias da tabela.

            **Exemplo de JSON de Saída:**
            ```json
            {
              "nome_funcionario": "ALAN LIMA FREITAS",
              "itens_epi": [
                {
                  "item_numero": "1",
                  "descricao": "BOTINA NOB CAD BI B/PLAS 42",
                  "data_entrega": "29/10/2024",
                  "ca": "45611"
                },
                {
                  "item_numero": "2",
                  "descricao": "Óculos Seg. Ampla Visão (Modelo: 3M GG500) - Para uso com lente graduada- REFERÊNCIA GG500",
                  "data_entrega": "29/10/2024",
                  "ca": "37640"
                }
              ]
            }
            ```
            """
            answer, _ = self.pdf_analyzer.answer_question([temp_path], structured_prompt)

        except Exception as e:
            st.error(f"Erro ao processar o PDF da Ficha de EPI: {str(e)}")
            return None
        finally:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)

        if not answer:
            st.error("A IA não retornou uma resposta para a Ficha de EPI.")
            return None

        try:
            # Limpa qualquer texto extra que o modelo possa ter adicionado
            cleaned_answer = re.search(r'\{.*\}', answer, re.DOTALL).group(0)
            data = json.loads(cleaned_answer)
            
            if 'nome_funcionario' not in data or 'itens_epi' not in data:
                st.error("O JSON retornado pela IA não contém as chaves esperadas ('nome_funcionario', 'itens_epi').")
                st.code(answer)
                return None
                
            return data

        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            st.error(f"Erro ao processar a resposta da IA para a Ficha de EPI: {e}")
            st.code(f"Resposta recebida da IA:\n{answer}")
            return None
            
    def add_epi_records(self, funcionario_id, arquivo_id, itens_epi, arquivo_hash=None):
        """Adiciona múltiplos registros de EPI a partir de uma única ficha, evitando duplicatas por hash."""
        funcionario_id_str = str(funcionario_id)
        
        # Verifica se o arquivo já foi cadastrado para este funcionário
        
        if arquivo_hash and verificar_hash_seguro(self.epi_df, 'arquivo_hash'):
            duplicata = self.epi_df[
                (self.epi_df['funcionario_id'] == funcionario_id_str) &
                (self.epi_df['arquivo_hash'] == arquivo_hash)
            ]
            
            if not duplicata.empty:
                st.warning(f"⚠️ Esta ficha de EPI já foi cadastrada anteriormente para este funcionário.")
                return None
        
        saved_ids = []
        for item in itens_epi:
            new_data = [
                funcionario_id_str,
                str(item.get('item_numero', '')),
                str(item.get('descricao', '')),
                str(item.get('ca', '')),
                str(item.get('data_entrega', '')),
                str(arquivo_id),
                arquivo_hash or ''
            ]
            try:
                new_id = self.sheet_ops.adc_dados_aba("fichas_epi", new_data)
                if new_id:
                    saved_ids.append(new_id)
            except Exception as e:
                st.error(f"Erro ao adicionar o item '{item.get('descricao')}': {e}")
                continue
        
        if saved_ids:
            st.cache_data.clear()
            self.load_epi_data()
            return saved_ids
        
        return None
