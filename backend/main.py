import json
from typing import Any, List

import boto3
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from conversation_history_manager import get_conversation_manager
from rag_service import get_rag_service
from schemas import RAGRequest, RAGResponse, SourceDocument
import os

app = FastAPI(
    title="SuperHRAI Backend",
    description="RAG-powered HR assistant backend",
    version="0.1.0",
)

# Configure CORS to allow remote connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# Bedrock model selection
# For Nova models, use inference profile ID format (required for on-demand access):
# - us.amazon.nova-micro-v1:0  (US regions - fastest, cheapest)
# - us.amazon.nova-lite-v1:0   (US regions - balanced, default)
# - us.amazon.nova-pro-v1:0    (US regions - most capable, higher cost)
# - eu.amazon.nova-lite-v1:0   (EU regions - balanced)
# Model ID is configured via BEDROCK_MODEL_ID environment variable
# If not provided, automatically uses us.amazon.nova-lite-v1:0 for US regions or eu.amazon.nova-lite-v1:0 for EU regions

USE_S3 = os.getenv("USE_S3", "false").lower() == "true"
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "")
MEMORY_DIR = os.getenv("MEMORY_DIR", "./persistent_conversation_history")

if USE_S3:
    s3_client = boto3.client("s3")
else:
    s3_client = None


def load_conversation(session_id: str) -> List[dict]:
    """
    Load conversation history for a given session_id.

    Args:
        session_id: UUID string identifying the conversation session

    Returns:
        List of conversation messages (dict with 'role' and 'content' keys)
    """
    if USE_S3:
        # Load from S3 bucket
        if not S3_BUCKET:
            raise ValueError("S3_BUCKET_NAME environment variable is not set when USE_S3 is true")
        
        try:
            s3_key = f"{session_id}.json"
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
            conversation_data = json.loads(response["Body"].read().decode("utf-8"))
            return conversation_data.get("messages", [])
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                # Conversation doesn't exist in S3
                return []
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error loading conversation from S3: {str(e)}"
                )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error loading conversation from S3: {str(e)}"
            )
    else:
        # Load from local persistent_conversation_history directory
        conversation_manager = get_conversation_manager(storage_dir=MEMORY_DIR)
        return conversation_manager.get_conversation_history(session_id)


@app.get("/health")
def read_root() -> dict[str, Any]:
    """
    Lightweight health check endpoint that doesn't require RAG service initialization.
    This endpoint should respond quickly even on cold starts.
    """
    # Check if required environment variables are set (without initializing services)
    env_status: dict[str, bool] = {
        "AWS_REGION": bool(os.getenv("DEFAULT_AWS_REGION")),
        "BEDROCK_MODEL_ID": bool(os.getenv("BEDROCK_MODEL_ID")),
        "CHROMA_API_KEY": bool(os.getenv("CHROMA_API_KEY")),
        "USE_S3": os.getenv("USE_S3", "false").lower() == "true",
    }
    
    if env_status["USE_S3"]:
        env_status["S3_BUCKET_NAME"] = bool(os.getenv("S3_BUCKET_NAME"))
    
    return {
        "status": "ok",
        "message": "SuperHRAI Backend API",
        "environment": env_status
    }


@app.post("/api/rag/query", response_model=RAGResponse)
def query_rag(request: RAGRequest) -> RAGResponse:
    """
    Query the RAG system with a question.

    This endpoint:
    1. Receives a question and optional conversation_id as input
    2. Loads conversation history from persistent storage (S3 or local) if conversation_id is provided
    3. Retrieves the top 5 relevant documents from ChromaDB using conversation context
    4. Passes them as context to Amazon Bedrock LLM (nova-lite) via LangChain
    5. Returns the answer, conversation_id, and source citations in JSON format

    Conversation Tracking:
    - If conversation_id is provided: Loads existing conversation history and continues the conversation
    - If conversation_id is not provided: Generates a new conversation_id and starts a new conversation
    - Always returns conversation_id in response for client to track and send in subsequent requests
    
    Note: This endpoint may take 10-30 seconds to respond due to LLM processing.
    Ensure your Lambda function has sufficient timeout configured (recommended: 60+ seconds).
    """
    conversation_id = None
    try:
        rag_service = get_rag_service()
        # Get conversation manager with environment-based configuration
        conversation_manager = get_conversation_manager(storage_dir=MEMORY_DIR)

        # Generate conversation ID if not provided (for new conversations)
        conversation_id = request.conversation_id
        if not conversation_id:
            conversation_id = conversation_manager.generate_conversation_id()

        # Load conversation history from persistent storage (S3 or local)
        # Always load from storage when conversation_id is provided to use stored memory
        conversation_history = None
        
        if conversation_id:
            # Always load from persistent storage (S3 or local based on USE_S3)
            stored_history = conversation_manager.get_conversation_history(conversation_id)
            if stored_history:
                # Convert stored messages to the format expected by RAG service
                conversation_history = [
                    {"role": msg.get("role"), "content": msg.get("content")}
                    for msg in stored_history
                ]
        
        # If no stored history found and history provided in request, use request history
        # (This allows initial conversation setup, but stored history takes precedence)
        if not conversation_history and request.conversation_history:
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]

        result = rag_service.query(
            question=request.question,
            conversation_id=conversation_id,
            conversation_history=conversation_history,
        )
        
        # Ensure conversation_id is always returned (from result or generated)
        returned_conversation_id = result.get("conversation_id", conversation_id)
        
        # Convert source dictionaries to SourceDocument objects
        sources = [
            SourceDocument(**source) for source in result["sources"]
        ]
        return RAGResponse(
            answer=result["answer"],
            conversation_id=returned_conversation_id,
            sources=sources,
        )
    except ValueError as e:
        # Preserve conversation_id even on validation errors
        error_detail = str(e)
        if conversation_id:
            error_detail = f"{error_detail} (conversation_id: {conversation_id})"
        import logging
        logging.error(f"Validation error in query_rag: {error_detail}")
        raise HTTPException(status_code=400, detail=error_detail)
    except Exception as e:
        # Preserve conversation_id even on server errors
        import logging
        import traceback
        error_detail = f"Internal server error: {str(e)}"
        if conversation_id:
            error_detail = f"{error_detail} (conversation_id: {conversation_id})"
        # Log full traceback for debugging
        logging.error(f"Error in query_rag: {error_detail}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=error_detail)