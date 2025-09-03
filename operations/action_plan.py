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

    # Cole esta função dentro da classe ActionPlanManager, em operations/action_plan.py

    def add_action_item(self, audit_run_id, company_id, doc_id, item_details, employee_id=None):
        """
        Adiciona um novo item ao plano de ação, garantindo a correspondência exata com as colunas da planilha.
        """
        item_title = item_details.get('item_verificacao', 'Não conformidade não especificada')
        item_observation = item_details.get('observacao', 'Sem detalhes fornecidos.')
        full_description = f"{item_title.strip()}: {item_observation.strip()}"
        
        # --- INÍCIO DA CORREÇÃO ---
        # Garante que o employee_id seja uma string ou uma string vazia
        employee_id_str = str(employee_id) if employee_id and pd.notna(employee_id) else ""

        new_data = [
            str(audit_run_id),                      # Coluna 2: audit_run_id
            str(company_id),                        # Coluna 3: id_empresa
            str(doc_id),                            # Coluna 4: id_documento_original
            employee_id_str,                        # Coluna 5: id_funcionario
            full_description,                       # Coluna 6: item_nao_conforme
            item_details.get('referencia', ''),     # Coluna 7: referencia_normativa
            "",                                     # Coluna 8: plano_de_acao (inicialmente vazio)
            "",                                     # Coluna 9: responsavel (inicialmente vazio)
            "",                                     # Coluna 10: prazo (inicialmente vazio)
            "Aberto",                               # Coluna 11: status
            date.today().strftime("%d/%m/%Y"),      # Coluna 12: data_criacao
            ""                                      # Coluna 13: data_conclusao (inicialmente vazio)
        ]
        # --- FIM DA CORREÇÃO ---
        
        print(f"DEBUG: Tentando adicionar ao plano de ação: {new_data}")
        item_id = self.sheet_ops.adc_dados_aba("plano_acao", new_data)
        
        if item_id:
            print(f"DEBUG: Sucesso! Novo ID do item de ação: {item_id}")
            st.toast(f"Item de ação '{item_title}' criado com sucesso!", icon="✅")
            log_action("CREATE_ACTION_ITEM", {
                "item_id": item_id, "company_id": company_id,
                "original_doc_id": doc_id, "description": full_description
            })
            self.load_data()
            return item_id
        else:
            print("DEBUG: Falha! A função adc_dados_aba retornou None.")
            st.error("Falha crítica: Não foi possível salvar o item no Plano de Ação na planilha.")
            return None

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
