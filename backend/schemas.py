from typing import List, Optional

from pydantic import BaseModel, Field


class SourceDocument(BaseModel):
    """Model for a source document citation."""

    content: str = Field(..., description="Excerpt from the source document")
    metadata: dict = Field(default_factory=dict, description="Document metadata")


class ConversationMessage(BaseModel):
    """Model for a conversation message."""

    role: str = Field(..., description="Role of the message sender (user or assistant)")
    content: str = Field(..., description="Content of the message")


class RAGRequest(BaseModel):
    """Request model for RAG query."""

    question: str = Field(
        ...,
        min_length=10,
        description="The current question to ask the RAG system",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="UUID identifying the conversation session",
    )
    conversation_history: Optional[List[ConversationMessage]] = Field(
        default_factory=list,
        description="Previous conversation messages for context",
    )


class RAGResponse(BaseModel):
    """Response model for RAG query."""

    answer: str = Field(..., description="The answer from the LLM")
    conversation_id: str = Field(..., description="UUID identifying the conversation session")
    sources: List[SourceDocument] = Field(
        default_factory=list,
        description="List of source documents used to generate the answer",
    )

