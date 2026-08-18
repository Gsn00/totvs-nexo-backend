import os
import json
from typing import List
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from dotenv import load_dotenv

load_dotenv()

class EntitySchema(BaseModel):
    type: str = Field(description="Tipo da entidade: competitor, product, role, painPoint ou churnRisk")
    text: str = Field(description="O trecho exato do texto que representa essa entidade")

class TranscriptItemSchema(BaseModel):
    speaker: str = Field(description="Identificador do locutor (ex: LOCUTOR 3)")
    text: str = Field(description="A fala completa de onde a informação foi extraída")
    entities: List[EntitySchema] = Field(description="Lista de entidades identificadas nesta fala")

class InsightsSchema(BaseModel):
    painPoints: List[str] = Field(description="Lista de dores identificadas")
    positiveHighlights: List[str] = Field(description="Lista de pontos positivos")
    riskPoints: List[str] = Field(description="Lista de sinais de churn ou concorrência")
    aiSuggestions: List[str] = Field(description="Próximos passos sugeridos")

class SentimentPointSchema(BaseModel):
    time: str = Field(description="Porcentagem do tempo da reunião (ex: '10%', '50%') ou 'Início da Reunião' / 'Fechamento da Reunião'")
    sentiment: float = Field(description="Score de 0 a 100 da saúde da reunião naquele momento")
    label: str = Field(description="Uma frase curta explicando o que causou esse sentimento (ex: 'Risco: Avaliação da Senior')")

class MeetingAnalysisSchema(BaseModel):
    participants: List[str] = Field(description="Lista de participantes e seus cargos identificados")
    totvsSpeakers: List[str] = Field(description="Lista de locutores da TOTVS identificados. Quero apenas a identificação do locutor identico ao documento original, ex: LOCUTOR 1, LOCUTOR 2, etc. Não quero o nome real do funcionário da TOTVS")
    clientSpeakers: List[str] = Field(description="Lista de locutores do cliente identificados. Quero apenas a identificação do locutor identico ao documento original, ex: LOCUTOR 1, LOCUTOR 2, etc. Não quero o nome real do funcionário do cliente")
    upsellOpportunities: List[str] = Field(description="Lista de oportunidades de upsell identificadas")
    churnRisk: int = Field(description="Score de 0 a 100 do risco de churn do cliente")
    healthScore: int = Field(description="Score de 0 a 100 da saúde da reunião")
    sentiment: str = Field(description="Sentimento geral: POSITIVE, NEGATIVE ou NEUTRAL (é importante que estejam maiúsculas)")
    transcript: List[TranscriptItemSchema] = Field(description="Apenas as falas cruciais com suas entidades marcadas")
    insights: InsightsSchema = Field(description="Bloco de insights estratégicos")
    sentimentData: List[SentimentPointSchema] = Field(description="Lista de 10 a 15 pontos estratégicos para o gráfico de humor")

class NexoEngine:
    def __init__(self, model_name: str = "gemini-3.6-flash"):
            self.llm = ChatGoogleGenerativeAI(
                model=model_name,
                temperature=0,
                google_api_key=os.getenv("GOOGLE_API_KEY")
            )
            self.parser = PydanticOutputParser(pydantic_object=MeetingAnalysisSchema)

    def analyze_transcription(self, cleaned_text: str) -> MeetingAnalysisSchema:
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", (
                "Você é um analista comercial sênior da TOTVS. "
                "Sua missão é minerar uma transcrição e extrair inteligência acionável. "
                "Ao gerar o 'sentimentData', siga estas regras:\n"
                "1. O primeiro label (0%) deve conter 'Início da Reunião' e alguma informação relevante sobre o humor dos participantes.\n"
                "2. O último label (100%) deve ser 'Fechamento da Reunião' e alguma informação relevante sobre o resultado da reunião.\n"
                "3. Use porcentagens (ex: '25%', '50%') para os pontos intermediários.\n"
                "4. Gere entre 10 a 15 pontos que mapeiem os momentos mais críticos de mudança de humor na conversa.\n"
                "No campo 'transcript', inclua APENAS as falas que contêm entidades importantes (competitor, product, role, painPoint, churnRisk) e tente extrair no mínimo 10 falas. "
                "Se alguma lista de output estiver vazia, retorne uma lista vazia. "
                "Ignore conversas triviais.\n{format_instructions}"
            )),
            ("user", "Analise a transcrição abaixo:\n\n{transcription}")
        ])

        chain = prompt_template | self.llm | self.parser
        
        return chain.invoke({
            "transcription": cleaned_text,
            "format_instructions": self.parser.get_format_instructions()
        })

