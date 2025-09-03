import streamlit as st
import pandas as pd
from datetime import date
from operations.sheet import SheetOperations
from operations.audit_logger import log_action

class ActionPlanManager:
    def __init__(self, spreadsheet_id: str):
        self.sheet_ops = SheetOperations(spreadsheet_id)
        # Define a estrutura de colunas esperada (tudo em minúsculas)
        self.columns = [
            'id', 'audit_run_id', 'id_empresa', 'id_documento_original', 'id_funcionario',
            'item_nao_conforme', 'referencia_normativa', 'plano_de_acao',
            'responsavel', 'prazo', 'status', 'data_criacao', 'data_conclusao'
        ]
        self.data_loaded_successfully = False
        self.load_data()

    def load_data(self):
        try:
            data = self.sheet_ops.carregar_dados_aba("plano_acao")
            if data and len(data) > 1:
                # Garante que os nomes das colunas do DataFrame sejam sempre os esperados
                header = [h.strip().lower() for h in data[0]]
                df = pd.DataFrame(data[1:], columns=header)
                self.action_plan_df = df
            else:
                self.action_plan_df = pd.DataFrame(columns=self.columns)
            
            self.data_loaded_successfully = True
        except Exception as e:
            st.error(f"Erro ao carregar dados de Planos de Ação: {e}")
            self.action_plan_df = pd.DataFrame(columns=self.columns)
            self.data_loaded_successfully = False

    def add_action_item(self, audit_run_id, company_id, doc_id, item_details, employee_id=None):
        """
        Adiciona um novo item ao plano de ação.
        """
        item_title = item_details.get('item_verificacao', 'Não conformidade não especificada')
        item_observation = item_details.get('observacao', 'Sem detalhes fornecidos.')
        full_description = f"{item_title.strip()}: {item_observation.strip()}"
        
        # Monta a linha na ordem correta das colunas
        new_data = [
            str(audit_run_id),
            str(company_id),
            str(doc_id),
            str(employee_id) if employee_id else "", # id_funcionario
            full_description, # item_nao_conforme
            item_details.get('referencia', ''), # referencia_normativa
            "",  # plano_de_acao (inicialmente vazio)
            "",  # responsavel (inicialmente vazio)
            "",  # prazo (inicialmente vazio)
            "Aberto", # status
            date.today().strftime("%d/%m/%Y"), # data_criacao
            ""   # data_conclusao (inicialmente vazio)
        ]
        
        item_id = self.sheet_ops.adc_dados_aba("plano_acao", new_data)
        if item_id:
            log_action("CREATE_ACTION_ITEM", {
                "item_id": item_id, "company_id": company_id,
                "original_doc_id": doc_id, "description": full_description
            })
            self.load_data() # Recarrega os dados
        return item_id

    def update_action_item(self, item_id, updates: dict):
        if 'prazo' in updates and isinstance(updates['prazo'], date):
            updates['prazo'] = updates['prazo'].strftime("%d/%m/%Y")
        
        if updates.get("status") == "Concluído" and "data_conclusao" not in updates:
             updates["data_conclusao"] = date.today().strftime("%d/%m/%Y")

        if self.sheet_ops.update_row_by_id("plano_acao", item_id, updates):
            log_action("UPDATE_ACTION_ITEM", {"item_id": item_id, "updates": updates})
            self.load_data()
            return True
        return False
        
    def get_action_items_by_company(self, company_id):
        if self.action_plan_df.empty:
            return pd.DataFrame()
        return self.action_plan_df[self.action_plan_df['id_empresa'] == str(company_id)]
