import re

def process_transcription(transcription: str) -> str:
    """
    Processa a string bruta de uma transcrição:
    - Divide em linhas
    - Remove aspas de formatação do CSV/texto bruto
    - Descarta linhas vazias
    - Reconcatena em um texto limpo com quebras de linha unificadas
    """
    if not transcription or not transcription.strip():
        return ""

    # Divide o texto por quebras de linha
    lines = transcription.splitlines()
    falas_limpas = []

    for line in lines:
        # Remove aspas das extremidades e aspas duplas internas de escape ("" -> ")
        fala = line.strip().strip('"').replace('""', '"').strip()
        
        # Ignora linhas totalmente vazias
        if fala:
            falas_limpas.append(fala)

    # Reúne as falas tratadas em um texto final com quebras de linha limpas
    return "\n".join(falas_limpas)