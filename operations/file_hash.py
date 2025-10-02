import hashlib
import streamlit as st
import logging

logger = logging.getLogger('segsisone_app.file_hash')

def calcular_hash_arquivo(arquivo) -> str:
    """
    Calcula o hash SHA-256 de um arquivo para identificação única.
    
    Args:
        arquivo: Objeto de arquivo do Streamlit (UploadedFile)
    
    Returns:
        str: Hash SHA-256 do arquivo em formato hexadecimal
    """
    try:
        # Lê o conteúdo do arquivo
        conteudo = arquivo.getvalue()
        
        # Calcula o hash SHA-256
        hash_obj = hashlib.sha256(conteudo)
        arquivo_hash = hash_obj.hexdigest()
        
        logger.debug(f"Hash calculado para arquivo '{arquivo.name}': {arquivo_hash[:16]}...")
        return arquivo_hash
        
    except Exception as e:
        logger.error(f"Erro ao calcular hash do arquivo: {e}")
        st.error(f"Erro ao calcular hash do arquivo: {e}")
        return None

def verificar_hash_seguro(df: 'pd.DataFrame', coluna_hash: str = 'arquivo_hash') -> bool:
    """
    Verifica se o DataFrame possui a coluna de hash e se não está vazia.
    Compatível com registros legados sem hash.
    
    Args:
        df: DataFrame do pandas
        coluna_hash: Nome da coluna de hash
    
    Returns:
        bool: True se a coluna existe e tem pelo menos um valor
    """
    if df.empty:
        return False
    
    if coluna_hash not in df.columns:
        logger.warning(f"Coluna '{coluna_hash}' não encontrada no DataFrame. Sistema em modo de compatibilidade.")
        return False
    
    # Verifica se há pelo menos um hash não vazio
    tem_hash = df[coluna_hash].notna().any() and (df[coluna_hash] != '').any()
    
    if not tem_hash:
        logger.info(f"Coluna '{coluna_hash}' existe mas está vazia. Sistema em modo de compatibilidade.")
    
    return tem_hash
