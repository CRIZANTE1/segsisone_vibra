import hashlib
import streamlit as st

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
        
        return arquivo_hash
    except Exception as e:
        st.error(f"Erro ao calcular hash do arquivo: {e}")
        return None
