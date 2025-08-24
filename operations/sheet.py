import streamlit as st
import pandas as pd
import logging
from gspread_pandas import Spread, Client
from gdrive.google_api_manager import GoogleApiManager

logger = logging.getLogger(__name__)

class SheetOperations:
    def __init__(self, spreadsheet_id: str):
        if not spreadsheet_id:
            st.error("ID da Planilha não fornecido.")
            logger.error("SheetOperations inicializado sem spreadsheet_id.")
            self.spread = None
            return

        try:
            api_manager = GoogleApiManager()
            self.spread = Spread(spreadsheet_id, client=api_manager.client)
        except Exception as e:
            st.error(f"Falha ao abrir a planilha com ID: {spreadsheet_id}. Verifique as permissões.")
            logger.error(f"Erro ao inicializar Spread para ID {spreadsheet_id}: {e}")
            self.spread = None

    def get_df_from_worksheet(self, sheet_name: str) -> pd.DataFrame:
        if not self.spread:
            return pd.DataFrame()
        try:
            return self.spread.sheet_to_df(sheet=sheet_name, index=None)
        except Exception as e:
            logger.error(f"Erro ao ler a aba '{sheet_name}' como DataFrame: {e}")
            return pd.DataFrame()

    def update_worksheet_from_df(self, sheet_name: str, df: pd.DataFrame) -> bool:
        if not self.spread:
            return False
        try:
            self.spread.df_to_sheet(df, sheet=sheet_name, index=False, replace=True)
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar a aba '{sheet_name}' a partir do DataFrame: {e}")
            return False