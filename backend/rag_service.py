import os

import boto3
import chromadb
from langchain_aws import BedrockEmbeddings, ChatBedrock
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser

from conversation_history_manager import get_conversation_manager
from dotenv import load_dotenv

load_dotenv()


class RAGService:
    """Service for handling RAG operations with ChromaDB and Amazon Bedrock."""

    def __init__(self, collection_name: str = "collection_bedrock"):
        """
        Initialize the RAG service with vector store and LLM.

        Args:
            collection_name: Name of the ChromaDB collection to use (default: "main_collection")
        """
        # Get AWS region and Bedrock model ID from environment
        aws_region = os.getenv("DEFAULT_AWS_REGION", "ca-central-1")
        bedrock_aws_region = os.getenv("BEDROCK_AWS_REGION", aws_region)

        # For Nova models, use inference profile ID format
        # US regions (us-east-1, us-west-2, ca-central-1, etc.): us.amazon.nova-lite-v1:0
        # EU regions (eu-west-1, eu-central-1, etc.): eu.amazon.nova-lite-v1:0
        # If BEDROCK_MODEL_ID is provided, use it; otherwise determine based on region
        provided_model_id = os.getenv("BEDROCK_MODEL_ID")
        if provided_model_id:
            bedrock_model_id = provided_model_id
        else:
            # Determine region prefix based on AWS region
            if bedrock_aws_region.startswith("eu"):
                region_prefix = "eu"
            else:
                # Default to "us" for US regions (including ca-central-1)
                region_prefix = "us"
            bedrock_model_id = f"{region_prefix}.amazon.nova-lite-v1:0"

        # Initialize embeddings using Amazon Bedrock Titan embeddings
        # Using amazon.titan-embed-text-v1 for embeddings
        self.embeddings = BedrockEmbeddings(
            model_id="amazon.titan-embed-text-v1",
            region_name=bedrock_aws_region
        )

        # Initialize ChromaDB Cloud client
        self.chroma_api_key = os.getenv("CHROMA_API_KEY")
        if not self.chroma_api_key:
            raise ValueError("CHROMA_API_KEY environment variable is not set")

        # Get tenant and database from environment variables or use defaults
        chroma_tenant = os.getenv("CHROMA_TENANT")
        chroma_database = os.getenv("CHROMA_DATABASE")

        self.chroma_client = chromadb.CloudClient(
            api_key=self.chroma_api_key,
            tenant=chroma_tenant,
            database=chroma_database
        )

        # Initialize vector store using langchain_chroma with ChromaDB Cloud
        self.vector_store = Chroma(
            client=self.chroma_client,
            collection_name=collection_name,
            embedding_function=self.embeddings,
        )        

        # Initialize LLM using Amazon Bedrock
        # Use bedrock_aws_region for consistency with embeddings
        self.llm = ChatBedrock(
            model_id=bedrock_model_id,
            temperature=0,
            region_name=bedrock_aws_region
        )

        # Create retriever with top-k=5
        self.retriever = self.vector_store.as_retriever(
            search_kwargs={"k": 5}
        )

        # System prompt template (will be built dynamically to include conversation history)
        self.base_system_prompt = """You are a helpful HR assistant for SuperHRAI. 
Your role is to answer questions based ONLY on the provided company documents.

Context from company documents:
{context}

Instructions:
- Answer the question using ONLY the information provided in the context above
- If the context does not contain relevant information, respond with: "I don't have information about that in our company documents"
- Be concise and accurate
- Cite the source documents when referencing specific information
- Use conversation history to provide context-aware responses when relevant"""

        # Note: We'll build the chain dynamically in the query method
        # to include conversation history in the prompt
        # Initialize conversation manager with environment-based configuration
        memory_dir = os.getenv("MEMORY_DIR", "./persistent_conversation_history")
        self.conversation_manager = get_conversation_manager(storage_dir=memory_dir)

    def query(
        self,
        question: str,
        conversation_id: str = None,
        conversation_history: list = None,
    ) -> dict:
        """
        Query the RAG system with a question and optional conversation history.

        Args:
            question: The user's current question
            conversation_id: UUID string identifying the conversation session
            conversation_history: List of previous conversation messages (optional)

        Returns:
            Dictionary containing answer, conversation_id, and source documents
        """
        if len(question.strip()) < 10:
            return {
                "answer": "Please provide a question with at least 10 characters.",
                "sources": [],
            }

        # If conversation_id is provided but no history passed, load from storage
        if conversation_id and not conversation_history:
            stored_history = self.conversation_manager.get_conversation_history(conversation_id)
            if stored_history:
                conversation_history = [
                    {"role": msg.get("role"), "content": msg.get("content")}
                    for msg in stored_history
                ]

        # Build combined query from conversation history and current question for retrieval
        # This helps retrieve more relevant documents based on the full conversation context
        query_parts = []
        if conversation_history:
            for msg in conversation_history:
                role = msg.get("role", "") if isinstance(msg, dict) else msg.role
                content = msg.get("content", "") if isinstance(msg, dict) else msg.content
                if role.lower() == "user":
                    query_parts.append(content)
        query_parts.append(question)
        combined_query = " ".join(query_parts)

        # Build prompt template with conversation history
        messages = [("system", self.base_system_prompt)]
        
        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                role = msg.get("role", "") if isinstance(msg, dict) else msg.role
                content = msg.get("content", "") if isinstance(msg, dict) else msg.content
                
                if role.lower() == "user":
                    messages.append(("human", content))
                elif role.lower() == "assistant":
                    messages.append(("ai", content))
        
        # Add current question
        messages.append(("human", "{question}"))
        
        # Create prompt template with conversation history
        prompt_template = ChatPromptTemplate.from_messages(messages)
        
        # Helper function to retrieve and format context
        def format_docs(docs):
            """Format documents for the prompt - using full content."""
            return "\n\n".join(doc.page_content for doc in docs)
        
        def retrieve_context(input_dict):
            """Retrieve documents using combined query from conversation history and current question."""
            # Use combined_query which includes conversation history
            docs = self.retriever.invoke(combined_query)
            return format_docs(docs)
        
        def extract_question(input_dict):
            """Extract question from input dict."""
            return input_dict["question"]
        
        # Build the chain dynamically with conversation history
        qa_chain = (
            {
                "context": RunnableLambda(retrieve_context),
                "question": RunnableLambda(extract_question),
            }
            | prompt_template
            | self.llm
            | StrOutputParser()
        )
        
        # Execute query using the RAG chain
        answer = qa_chain.invoke({"question": question})

        # Retrieve documents separately for source citations using combined query
        context_docs = self.retriever.invoke(combined_query)

        # Ensure context_docs is a list
        if not isinstance(context_docs, list):
            # Fallback: retrieve documents separately if needed
            source_documents = self.retriever.get_relevant_documents(combined_query)
        else:
            source_documents = context_docs

        # Format sources - using full content (not truncated)
        sources = []
        for doc in source_documents[:5]:  # Limit to top 5
            if hasattr(doc, "page_content"):
                sources.append(
                    {
                        "content": doc.page_content,  # Full content, not truncated
                        "metadata": getattr(doc, "metadata", {}),
                    }
                )

        # Generate conversation ID if not provided
        if not conversation_id:
            conversation_id = self.conversation_manager.generate_conversation_id()

        # Save interaction to persistent storage
        self.conversation_manager.save_interaction(
            conversation_id=conversation_id,
            question=question,
            answer=answer,
            conversation_history=conversation_history,
        )

        return {
            "answer": answer,
            "conversation_id": conversation_id,
            "sources": sources,
        }


# Global RAG service instance
_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    """Get or create the global RAG service instance."""
    global _rag_service
    if _rag_service is None:
        # Get collection name from environment or use default
        collection_name = os.getenv("CHROMA_COLLECTION_NAME", "main_collection")
        _rag_service = RAGService(collection_name=collection_name)
    return _rag_service
