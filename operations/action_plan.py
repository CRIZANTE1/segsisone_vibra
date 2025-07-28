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
        if not self.initialize_sheets():
            st.error("Erro ao inicializar a aba de Planos de Ação.")
        self.load_data()

    def initialize_sheets(self):
        try:
            columns = [
                'id', 'audit_run_id', 'id_empresa', 'id_documento_original',
                'item_nao_conforme', 'referencia_normativa', 'plano_de_acao',
                'responsavel', 'prazo', 'status', 'data_criacao', 'data_conclusao'
            ]
            if not self.sheet_ops.carregar_dados_aba(ACTION_PLAN_SHEET_NAME):
                self.sheet_ops.criar_aba(ACTION_PLAN_SHEET_NAME, columns)
            return True
        except Exception as e:
            st.error(f"Erro ao inicializar aba de Planos de Ação: {e}")
            return False

    def load_data(self):
        try:
            data = self.sheet_ops.carregar_dados_aba(ACTION_PLAN_SHEET_NAME)
            self.action_plan_df = pd.DataFrame(data[1:], columns=data[0]) if data and len(data) > 0 else pd.DataFrame()
        except Exception as e:
            st.error(f"Erro ao carregar dados de Planos de Ação: {e}")
            self.action_plan_df = pd.DataFrame()

    def add_action_item(self, audit_run_id, company_id, doc_id, item_details):
        new_data = [
            str(audit_run_id),
            str(company_id),
            str(doc_id),
            item_details.get('item_verificacao', ''),
            item_details.get('referencia', ''),
            "",  # plano_de_acao (inicialmente vazio)
            "",  # responsavel (inicialmente vazio)
            "",  # prazo (inicialmente vazio)
            "Aberto",  # status
            date.today().strftime("%d/%m/%Y"),  # data_criacao
            "",  # data_conclusao (inicialmente vazio)
        ]
        return self.sheet_ops.adc_dados_aba(ACTION_PLAN_SHEET_NAME, new_data)

    def update_action_item(self, item_id, updates: dict):
        """Atualiza um item do plano de ação usando seu ID único."""
        if 'prazo' in updates and isinstance(updates['prazo'], date):
            updates['prazo'] = updates['prazo'].strftime("%d/%m/%Y")
        
        if updates.get("status") == "Concluído" and "data_conclusao" not in updates:
             updates["data_conclusao"] = date.today().strftime("%d/%m/%Y")

        if self.sheet_ops.update_row_by_id(ACTION_PLAN_SHEET_NAME, item_id, updates):
            st.cache_data.clear() # Limpa o cache para forçar o recarregamento dos dados
            return True
        return False
        
    def get_action_items_by_company(self, company_id):
        if self.action_plan_df.empty:
            return pd.DataFrame()
        return self.action_plan_df[self.action_plan_df['id_empresa'] == str(company_id)]
