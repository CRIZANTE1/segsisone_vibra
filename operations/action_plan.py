
import streamlit as st
import pandas as pd
from datetime import date
from operations.sheet import SheetOperations
from operations.audit_logger import log_action, logger
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

    def load_data(self):
        """Carrega os dados do plano de ação da planilha."""
        try:
            self.action_plan_df = load_action_plan_df(self.spreadsheet_id)
            
            if not self.action_plan_df.empty:
                self.data_loaded_successfully = True
                logger.info(f"Plano de ação carregado: {len(self.action_plan_df)} itens.")
            else:
                self.data_loaded_successfully = False
                logger.warning("Aba 'plano_acao' está vazia.")
        
        except Exception as e:
            logger.error(f"Erro ao carregar plano de ação: {e}")
            self.action_plan_df = pd.DataFrame(columns=self.columns)
            self.data_loaded_successfully = False

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
        
        # A ordem dos dados corresponde à ordem das colunas na planilha, exceto pelo 'id',
        # que é gerado automaticamente pelo método adc_dados_aba.
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

    def get_action_items_by_company(self, company_id: str):
        """Retorna todos os itens do plano de ação para uma empresa."""
        if self.action_plan_df.empty:
            return pd.DataFrame()
        
        return self.action_plan_df[
            self.action_plan_df['id_empresa'] == str(company_id)
        ].copy()

    def update_action_item(self, item_id: str, updates: dict):
        """Atualiza um item do plano de ação (ex: status, responsável, prazo)."""
        if not self.data_loaded_successfully:
            st.error("Plano de ação não foi carregado corretamente.")
            return False
        
        success = self.sheet_ops.update_row_by_id("plano_acao", item_id, updates)
        
        if success:
            log_action("UPDATE_ACTION_ITEM", {
                "item_id": item_id,
                "updated_fields": list(updates.keys())
            })
            self.load_data()
            return True
        
        return False
