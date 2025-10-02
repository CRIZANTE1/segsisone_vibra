import streamlit as st
import pandas as pd
from datetime import date
from operations.sheet import SheetOperations
from operations.audit_logger import log_action
from operations.cached_loaders import load_action_plan_df


class ActionPlanManager:
    def __init__(self, spreadsheet_id: str):
        self.sheet_ops = SheetOperations(spreadsheet_id)
        self.spreadsheet_id = spreadsheet_id
        
        # ✅ ESTRUTURA ATUALIZADA COM id_funcionario
        self.columns = [
            'id', 'audit_run_id', 'id_empresa', 'id_documento_original', 
            'id_funcionario',  # ✅ ADICIONAR AQUI
            'item_nao_conforme', 'referencia_normativa', 'plano_de_acao',
            'responsavel', 'prazo', 'status', 'data_criacao', 'data_conclusao'
        ]
        
        self.data_loaded_successfully = False
        self.load_data()

    def add_action_item(self, audit_run_id, company_id, doc_id, item_details, employee_id=None):
        """
        Adiciona um novo item ao plano de ação.
        
        ✅ AGORA COM id_funcionario na planilha
        """
        if not self.data_loaded_successfully:
            st.error("Não é possível adicionar item de ação, pois os dados da planilha não foram carregados.")
            return None
    
        item_title = item_details.get('item_verificacao', 'Não conformidade não especificada')
        item_observation = item_details.get('observacao', 'Sem detalhes fornecidos.')
        full_description = f"{item_title.strip()}: {item_observation.strip()}"
        
        # ✅ ORDEM CORRETA COM id_funcionario
        new_data = [
            str(audit_run_id),                                  # audit_run_id
            str(company_id),                                    # id_empresa
            str(doc_id),                                        # id_documento_original
            str(employee_id) if employee_id else "",            # id_funcionario
            full_description,                                   # item_nao_conforme
            item_details.get('referencia_normativa', ''),       # referencia_normativa
            "",                                                 # plano_de_acao
            "",                                                 # responsavel
            "",                                                 # prazo
            "Aberto",                                           # status
            date.today().strftime("%d/%m/%Y"),                  # data_criacao
            ""                                                  # data_conclusao
        ]
        
        item_id = self.sheet_ops.adc_dados_aba("plano_acao", new_data)
        
        if item_id:
            st.toast(f"Item de ação '{item_title}' criado com sucesso!", icon="✅")
            log_action("CREATE_ACTION_ITEM", {
                "item_id": item_id, 
                "company_id": company_id,
                "original_doc_id": doc_id,
                "employee_id": employee_id if employee_id else "N/A",
                "description": full_description
            })
            self.load_data()
            return item_id
        else:
            st.error("Falha crítica: Não foi possível salvar o item no Plano de Ação na planilha.")
            return None
    
    def get_action_items_by_employee(self, employee_id: str):
        """
        ✅ NOVA FUNÇÃO: Retorna itens do plano de ação para um funcionário específico
        """
        if self.action_plan_df.empty:
            return pd.DataFrame()
        
        return self.action_plan_df[
            self.action_plan_df['id_funcionario'] == str(employee_id)
        ]
