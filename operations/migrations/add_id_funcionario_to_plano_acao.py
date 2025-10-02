import logging
import pandas as pd
from gdrive.matrix_manager import MatrixManager
from operations.sheet import SheetOperations
import gspread

logger = logging.getLogger(__name__)

def adicionar_coluna_id_funcionario(spreadsheet_id: str) -> dict:
    """
    Adiciona a coluna id_funcionario na aba plano_acao de uma unidade.
    Retorna um dicionário com o resultado da operação.
    """
    try:
        sheet_ops = SheetOperations(spreadsheet_id)
        worksheet = sheet_ops._get_worksheet("plano_acao")
        
        if not worksheet:
            return {
                "sucesso": False,
                "mensagem": "Aba 'plano_acao' não encontrada",
                "registros_populados": 0
            }
        
        # Verifica se a coluna já existe
        headers = worksheet.row_values(1)
        
        if 'id_funcionario' in headers:
            return {
                "sucesso": True,
                "mensagem": "Coluna 'id_funcionario' já existe",
                "registros_populados": 0
            }
        
        # Encontra a posição após 'id_documento_original'
        try:
            pos_doc = headers.index('id_documento_original') + 1
            posicao_insercao = pos_doc + 1  # Coluna após id_documento_original
        except ValueError:
            return {
                "sucesso": False,
                "mensagem": "Coluna 'id_documento_original' não encontrada",
                "registros_populados": 0
            }
        
        # Insere a nova coluna
        worksheet.insert_cols([[]], col=posicao_insercao)
        worksheet.update_cell(1, posicao_insercao, 'id_funcionario')
        
        # Popula valores existentes (ASOs e Treinamentos têm id_funcionario)
        registros_populados = 0
        
        # Carrega dados para popular
        try:
            from operations.employee import EmployeeManager
            emp_manager = EmployeeManager(spreadsheet_id, "")
            
            # Busca registros que possam ser populados
            plano_df = sheet_ops.get_df_from_worksheet("plano_acao")
            
            if not plano_df.empty and 'id_documento_original' in plano_df.columns:
                for idx, row in plano_df.iterrows():
                    doc_id = str(row.get('id_documento_original', ''))
                    
                    # Tenta encontrar em ASOs
                    if not emp_manager.aso_df.empty:
                        aso_match = emp_manager.aso_df[emp_manager.aso_df['id'] == doc_id]
                        if not aso_match.empty:
                            func_id = aso_match.iloc[0].get('funcionario_id')
                            if func_id:
                                row_num = idx + 2  # +2 porque índice começa em 0 e linha 1 é header
                                worksheet.update_cell(row_num, posicao_insercao, str(func_id))
                                registros_populados += 1
                                continue
                    
                    # Tenta encontrar em Treinamentos
                    if not emp_manager.training_df.empty:
                        training_match = emp_manager.training_df[emp_manager.training_df['id'] == doc_id]
                        if not training_match.empty:
                            func_id = training_match.iloc[0].get('funcionario_id')
                            if func_id:
                                row_num = idx + 2
                                worksheet.update_cell(row_num, posicao_insercao, str(func_id))
                                registros_populados += 1
        except Exception as e:
            logger.warning(f"Erro ao popular valores existentes: {e}")
        
        return {
            "sucesso": True,
            "mensagem": "Coluna adicionada com sucesso",
            "registros_populados": registros_populados
        }
        
    except Exception as e:
        logger.error(f"Erro ao adicionar coluna: {e}", exc_info=True)
        return {
            "sucesso": False,
            "mensagem": f"Erro: {str(e)}",
            "registros_populados": 0
        }


def executar_migracao_em_todas_unidades():
    """
    Executa a migração em todas as unidades do sistema.
    Retorna um dicionário com os resultados por unidade.
    """
    matrix_manager = MatrixManager()
    all_units = matrix_manager.get_all_units()
    
    resultados = {}
    
    for unit in all_units:
        unit_name = unit.get('nome_unidade')
        spreadsheet_id = unit.get('spreadsheet_id')
        
        if not spreadsheet_id:
            resultados[unit_name] = {
                "sucesso": False,
                "mensagem": "ID da planilha não encontrado",
                "registros_populados": 0
            }
            continue
        
        logger.info(f"Executando migração para unidade: {unit_name}")
        resultado = adicionar_coluna_id_funcionario(spreadsheet_id)
        resultados[unit_name] = resultado
    
    return resultados
