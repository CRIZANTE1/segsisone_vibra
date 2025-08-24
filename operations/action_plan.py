import streamlit as st
import pandas as pd
from datetime import date
from operations.sheet import SheetOperations

import streamlit as st
import pandas as pd
from datetime import date
from operations.sheet import SheetOperations

# Import the new cached loaders
from operations.cached_loaders import (
    load_action_plan_df
)

class ActionPlanManager:
    def __init__(self, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id
        self.columns = [
            'id', 'audit_run_id', 'id_empresa', 'id_documento_original',
            'item_nao_conforme', 'referencia_normativa', 'plano_de_acao',
            'responsavel', 'prazo', 'status', 'data_criacao', 'data_conclusao'
        ]
        
        # Load data using cached functions
        self.action_plan_df = load_action_plan_df(spreadsheet_id)

    

    def add_action_item(self, audit_run_id, company_id, doc_id, item_details):
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
        sheet_ops = SheetOperations(self.spreadsheet_id)
        action_item_id = sheet_ops.adc_dados_aba("plano_acao", new_data)
        if action_item_id:
            load_action_plan_df.clear() # Clear cache after addition
        return action_item_id

    def update_action_item(self, item_id, updates: dict):
        if 'prazo' in updates and isinstance(updates['prazo'], date):
            updates['prazo'] = updates['prazo'].strftime("%d/%m/%Y")
        
        if updates.get("status") == "Concluído" and "data_conclusao" not in updates:
             updates["data_conclusao"] = date.today().strftime("%d/%m/%Y")

        sheet_ops = SheetOperations(self.spreadsheet_id)
        if sheet_ops.update_row_by_id("plano_acao", item_id, updates):
            load_action_plan_df.clear() # Clear cache after update
            return True
        return False
        
    def get_action_items_by_company(self, company_id):
        if self.action_plan_df.empty:
            return pd.DataFrame(columns=self.columns)
        return self.action_plan_df[self.action_plan_df['id_empresa'] == str(company_id)]
