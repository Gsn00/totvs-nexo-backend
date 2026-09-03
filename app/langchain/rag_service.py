import os
import time
from typing import Dict, Any
from dotenv import load_dotenv

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.documents import Document
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

load_dotenv()

# Armazenamento em memória para sessões de chat ativas
store_chat_history: Dict[str, ChatMessageHistory] = {}


def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in store_chat_history:
        store_chat_history[session_id] = ChatMessageHistory()
    return store_chat_history[session_id]


# Schema para a Chain de Roteamento de Intenção
class QueryClassification(BaseModel):
    category: str = Field(
        description="Categoria da pergunta: 'REUNION_QUERY' se exige contexto da reunião (detalhes, riscos, decisões, dores, valores, participantes, próximos passos, etc.), ou 'GENERAL_QUERY' para saudações, conversas genéricas ou perguntas não relacionadas à reunião."
    )


class MeetingRAGService:
    def __init__(
        self,
        llm_model: str = "gemini-3.5-flash",
        classifier_model: str = "gemini-3.5-flash-lite",
        embedding_model: str = "gemini-embedding-2-preview",
        collection_name: str = "meeting_transcriptions",
    ):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.qdrant_url = os.getenv("QDRANT_URL")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")

        if not self.api_key or not self.qdrant_url or not self.qdrant_api_key:
            raise ValueError(
                "As variáveis de ambiente GOOGLE_API_KEY, QDRANT_URL e QDRANT_API_KEY são obrigatórias."
            )

        self.collection_name = collection_name

        # 1. Configuração do Modelo de Embeddings do Gemini (3072 dimensões)
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=embedding_model,
            google_api_key=self.api_key,
        )

        # 2. Cliente Qdrant Cloud
        self.client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key,
            timeout=60.0,
        )

        target_size = 3072  # Dimensão oficial do gemini-embedding-2-preview

        # 3. Garante que a coleção existe com o tamanho de 3072 dimensões
        if self.client.collection_exists(collection_name=self.collection_name):
            col_info = self.client.get_collection(collection_name=self.collection_name)
            if col_info.config.params.vectors.size != target_size:
                self.client.delete_collection(collection_name=self.collection_name)

        if not self.client.collection_exists(collection_name=self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=target_size,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )

        # 4. Índice para o filtro por meeting_id
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="metadata.meeting_id",
                field_schema=qdrant_models.PayloadSchemaType.INTEGER,
            )
        except Exception:
            pass

        self.vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embeddings,
        )

        # 5. LLM Principal (Gemini 3.5 Flash para RAG e Respostas Gerais)
        self.llm = ChatGoogleGenerativeAI(
            model=llm_model,
            temperature=0.2,
            google_api_key=self.api_key,
        )

        # 6. LLM Classificador Leve (Gemini 3.5 Flash Lite para Roteamento)
        self.classifier_llm_instance = ChatGoogleGenerativeAI(
            model=classifier_model,
            temperature=0.0,  # Zero temperatura para maior determinismo
            google_api_key=self.api_key,
        )
        self.classifier_llm = self.classifier_llm_instance.with_structured_output(QueryClassification)

        # Chunks para otimizar a geração de embeddings
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1800,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""],
        )

    def classify_query(self, question: str) -> str:
        """Classifica usando o Gemini 3.5 Flash Lite."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Você é um classificador de intenção especializado.\n"
                "Análise a mensagem do usuário e determine se ela necessita consultar os detalhes ou transcrição de uma reunião comercial.\n\n"
                "Diretrizes:\n"
                "- Marque como 'REUNION_QUERY' se o usuário estiver perguntando sobre assuntos, riscos, decisões, participantes, prazos, valores ou detalhes ocorridos na reunião.\n"
                "- Marque como 'GENERAL_QUERY' se for uma saudação (ex: 'olá', 'tudo bem?'), conversa genérica ou pergunta que não depende do contexto da reunião."
            )),
            ("human", "{question}"),
        ])

        chain = prompt | self.classifier_llm
        try:
            result = chain.invoke({"question": question})
            return result.category
        except Exception:
            return "REUNION_QUERY"

    def ingest_transcription(self, meeting_id: int, transcription_text: str) -> int:
        if not transcription_text or not transcription_text.strip():
            return 0

        chunks = self.text_splitter.split_text(transcription_text)

        documents = [
            Document(
                page_content=chunk,
                metadata={
                    "meeting_id": int(meeting_id),
                    "chunk_index": idx,
                },
            )
            for idx, chunk in enumerate(chunks)
        ]

        batch_size = 10
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            self.vector_store.add_documents(batch)
            time.sleep(2.0)

        return len(documents)

    def _parse_response_content(self, content: Any) -> str:
        """Trata o retorno para garantir a entrega de uma string limpa ao Pydantic."""
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
                elif hasattr(part, "text"):
                    text_parts.append(getattr(part, "text"))
            return "".join(text_parts)
        return str(content)

    def ask_question(self, meeting_id: int, session_id: str, question: str) -> str:
        # 1. ROTEAMENTO: Classifica usando Gemini 3.5 Flash Lite
        category = self.classify_query(question)

        # 2.A - CASO FORA DE ESCOPO/SAUDAÇÃO (Não acessa o Qdrant)
        if category == "GENERAL_QUERY":
            general_prompt = ChatPromptTemplate.from_messages([
                ("system", (
                    "Você é um assistente comercial especializado na plataforma TOTVS.\n"
                    "O usuário fez uma saudação ou pergunta genérica que não exige a transcrição da reunião.\n"
                    "Responda de forma curta, educada e profissional, informando que você está à disposição para esclarecer dúvidas específicas sobre esta reunião."
                )),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ])

            chain = general_prompt | self.llm
            with_history = RunnableWithMessageHistory(
                chain,
                get_session_history,
                input_messages_key="input",
                history_messages_key="chat_history",
            )

            response = with_history.invoke(
                {"input": question},
                config={"configurable": {"session_id": session_id}},
            )
            return self._parse_response_content(response.content)

        # 2.B - CASO PERGUNTA DA REUNIÃO (Consulta o Qdrant + Gemini 3.5 Flash)
        meeting_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="metadata.meeting_id",
                    match=qdrant_models.MatchValue(value=int(meeting_id)),
                )
            ]
        )

        retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": 4,
                "filter": meeting_filter,
            },
        )

        relevant_docs = retriever.invoke(question)
        context = "\n\n".join([doc.page_content for doc in relevant_docs])

        if not context.strip():
            context = "Nenhuma informação relevante foi encontrada na transcrição desta reunião."

        rag_prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Você é um assistente comercial da TOTVS especializado em analisar reuniões corporativas.\n"
                "Responda à dúvida do usuário utilizando ESTRITAMENTE o contexto abaixo.\n"
                "Se a resposta não puder ser confirmada pelo contexto fornecido, diga educadamente que essa informação não consta na transcrição.\n\n"
                "--- CONTEXTO DA REUNIÃO #{meeting_id} ---\n"
                "{context}\n"
                "------------------------------------------"
            )),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])

        # Executa com Gemini 3.5 Flash
        chain = rag_prompt | self.llm
        with_history = RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

        response = with_history.invoke(
            {
                "input": question,
                "context": context,
                "meeting_id": str(meeting_id),
            },
            config={"configurable": {"session_id": session_id}},
        )

        return self._parse_response_content(response.content)