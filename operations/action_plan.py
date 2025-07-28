import streamlit as st
import pandas as pd
from datetime import date
from operations.sheet import SheetOperations
from gdrive.config import ACTION_PLAN_SHEET_NAME

@st.cache_resource
def get_sheet_ops_action_plan():
    return SheetOperations()

class ActionPlanManager:
    def __init__(self):
        self.sheet_ops = get_sheet_ops_action_plan()
        self.columns = [ # Define a estrutura de colunas uma vez
            'id', 'audit_run_id', 'id_empresa', 'id_documento_original',
            'item_nao_conforme', 'referencia_normativa', 'plano_de_acao',
            'responsavel', 'prazo', 'status', 'data_criacao', 'data_conclusao'
        ]
        if not self.initialize_sheets():
            st.error("Erro ao inicializar a aba de Planos de Ação.")
        self.load_data()

    def initialize_sheets(self):
        try:
            if not self.sheet_ops.carregar_dados_aba(ACTION_PLAN_SHEET_NAME):
                self.sheet_ops.criar_aba(ACTION_PLAN_SHEET_NAME, self.columns)
            return True
        except Exception as e:
            st.error(f"Erro ao inicializar aba de Planos de Ação: {e}")
            return False

    def load_data(self):
        try:
            data = self.sheet_ops.carregar_dados_aba(ACTION_PLAN_SHEET_NAME)
            if data and len(data) > 1:
                df = pd.DataFrame(data[1:], columns=data[0])
                df.columns = [col.strip().lower() for col in df.columns]
                self.action_plan_df = df
            else:
                self.action_plan_df = pd.DataFrame(columns=self.columns)
        except Exception as e:
            st.error(f"Erro ao carregar dados de Planos de Ação: {e}")
            self.action_plan_df = pd.DataFrame(columns=self.columns)

    def add_action_item(self, audit_run_id, company_id, doc_id, item_details):
        """
        Adiciona um item ao plano de ação, combinando o título e a observação
        para uma descrição completa.
        """
        item_title = item_details.get('item_verificacao', 'Não conformidade não especificada')
        
        item_observation = item_details.get('observacao', 'Sem detalhes fornecidos.')

        full_description = f"{item_title.strip()}: {item_observation.strip()}"

        new_data = [
            str(audit_run_id),
            str(company_id),
            str(doc_id),
            full_description,  
            item_details.get('referencia', ''), 
            "",  
            "",  
            "",  
            "Aberto",
            date.today().strftime("%d/%m/%Y"),
            ""  
        ]
        return self.sheet_ops.adc_dados_aba(ACTION_PLAN_SHEET_NAME, new_data)

    def update_action_item(self, item_id, updates: dict):
        if 'prazo' in updates and isinstance(updates['prazo'], date):
            updates['prazo'] = updates['prazo'].strftime("%d/%m/%Y")
        
        if updates.get("status") == "Concluído" and "data_conclusao" not in updates:
             updates["data_conclusao"] = date.today().strftime("%d/%m/%Y")

        if self.sheet_ops.update_row_by_id(ACTION_PLAN_SHEET_NAME, item_id, updates):
            st.cache_data.clear()
            return True
        return False
        
    def get_action_items_by_company(self, company_id):
        if self.action_plan_df.empty:
            return pd.DataFrame(columns=self.columns) # Garante retorno com colunas
        return self.action_plan_df[self.action_plan_df['id_empresa'] == str(company_id)]
