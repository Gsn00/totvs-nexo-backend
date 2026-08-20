import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from dotenv import load_dotenv

load_dotenv()

class EntitySchema(BaseModel):
    type: str = Field(description="Tipo da entidade: competitor, product, role, painPoint ou churnRisk. Product é o nome do produto da TOTVS, role é o cargo de algum funcionário da TOTVS, não de um cliente. PainPoint é uma dor do cliente, churnRisk é um risco de churn do cliente e competitor é o nome de algum concorrente da TOTVS")
    text: str = Field(description="O trecho exato do texto que representa essa entidade. Deve ser o mais curto possível, mas ainda assim compreensível. Ex: 'Senior', 'TOTVS', 'ERP Protheus', 'Falta de suporte', 'Concorrência da Senior'. Exatamente como aparece na transcrição, incluindo maiúsculas e minúsculas.")

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
    isAnalyzable: bool = Field(description="Define se o texto é uma reunião válida com informações suficientes para análise comercial.")
    reasonForFailure: Optional[str] = Field(description="Caso is_analyzable seja falso, explique o motivo (ex: texto muito curto, assunto irrelevante, etc.)")
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
    def __init__(self, model_name: str = "gemini-3.7-flash"):
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
                "No campo 'transcript', inclua APENAS as falas que contêm entidades importantes (competitor, product, role, painPoint, churnRisk). As falas devem ser majoritariamente do cliente, com foco em informações estratégicas e com textos não muito longos.\n "
                "O transcript contém speaker, text e entities. As entities devem ser extraídas do texto, não inventadas. Ex: se o locutor fala 'A Senior é uma concorrente da TOTVS', a entity deve ser 'type': 'competitor', 'text': 'Senior'.\n "
                "Se alguma lista de output estiver vazia, retorne uma lista vazia.\n "
                "Principais produtos da TOTVS: Protheus, Datasul, RM, Logix, Backoffice, TOTVS CRM, RD Station, Tallos, Meu RH, Clockin, Atração de Talentos, Fluig, Carol, TOTVS Analytics, Agro, Saúde, Logística, Varejo, Educacional, Construção, Jurídico, Financial Services, Techfin.\n "
                "Principais concorrentes da TOTVS: SAP, S/4HANA, Business One, Oracle, NetSuite, Fusion Cloud, Microsoft Dynamics 365, Business Central, Senior Sistemas, Omie, Bling, Alterdata, Mega Sistemas, LG Lugar de Gente, ADP, Ahgora, Flash, Salesforce, HubSpot, Pipedrive, Zoho.\n "
                "Principais cargos da TOTVS: CEO, CFO, COO, CTO, CIO, CMO, CHRO, Executivo de Contas, Account Executive, Especialista de Soluções, Gerente Comercial, Diretor Comercial, SDR, BDR, Consultor de Negócios, Arquiteto de Soluções, Engenheiro de Software, Analista de Sistemas, Analista de Negócios, Analista de Implantação, Consultor de Suporte, Coordenador de Projetos, Customer Success Manager, CSM, Gerente de Projetos, Diretor de Tecnologia, Analista de Gente e Gestão, Business Partner, Gerente de Vendas, Gerente de Marketing, Gerente de Produto, Gerente de Suporte, Desenvolvedor de Software.\n "
                "Apesar de você ter acesso a uma lista de concorrentes, produtos e cargos, não se limite a eles. "
                "Ignore conversas triviais.\n{format_instructions}"
            )),
            ("user", "Analise a transcrição abaixo:\n\n{transcription}")
        ])

        chain = prompt_template | self.llm | self.parser
        
        return chain.invoke({
            "transcription": cleaned_text,
            "format_instructions": self.parser.get_format_instructions()
        })

