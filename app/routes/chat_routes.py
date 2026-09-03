from fastapi import APIRouter, Form, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.langchain.rag_service import MeetingRAGService

router = APIRouter(prefix="/meetings", tags=["Chatbot RAG"])

# Instância única do serviço de RAG
rag_service = MeetingRAGService()

# Schema de resposta mantido limpo para retornos JSON
class ChatResponse(BaseModel):
    meeting_id: int
    session_id: str
    question: str
    answer: str


@router.post("/{meeting_id}/chat", response_model=ChatResponse)
async def ask_meeting_chat(
    meeting_id: int,
    question: str = Form(..., description="Pergunta do usuário sobre a reunião"),
    session_id: Optional[str] = Form(
        default=None,
        description="ID da sessão de chat. Se omitido, usará um ID padrão baseado na reunião"
    )
):
    """
    Endpoint para realizar perguntas sobre uma reunião específica usando RAG + Qdrant.
    Recebe os campos via Form Data (multipart/form-data).
    """
    try:
        # Se não enviar session_id, define um padrão fixo associado à reunião
        active_session_id = session_id or f"session_meeting_{meeting_id}"

        # Chama o serviço RAG para buscar contexto no Qdrant e gerar a resposta com o Gemini
        answer = rag_service.ask_question(
            meeting_id=meeting_id,
            session_id=active_session_id,
            question=question
        )

        return ChatResponse(
            meeting_id=meeting_id,
            session_id=active_session_id,
            question=question,
            answer=answer
        )

    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar a pergunta do chat: {str(e)}"
        )