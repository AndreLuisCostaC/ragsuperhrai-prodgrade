"""Manager for persistent conversation history storage."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class ConversationHistoryManager:
    """Manages persistent storage of conversation history."""

    def __init__(
        self,
        storage_dir: str = "./persistent_conversation_history",
        use_s3: Optional[bool] = None,
        s3_bucket: Optional[str] = None,
    ):
        """
        Initialize the conversation history manager.

        Args:
            storage_dir: Directory to store conversation history files (for local storage)
            use_s3: Whether to use S3 storage (defaults to USE_S3 env var)
            s3_bucket: S3 bucket name (defaults to S3_BUCKET_NAME env var)
        """
        # Determine storage backend from environment or parameters
        self.use_s3 = use_s3 if use_s3 is not None else os.getenv("USE_S3", "false").lower() == "true"
        self.s3_bucket = s3_bucket or os.getenv("S3_BUCKET_NAME", "")
        
        if self.use_s3:
            if not BOTO3_AVAILABLE:
                raise ImportError("boto3 is required for S3 storage. Install it with: pip install boto3")
            if not self.s3_bucket:
                raise ValueError("S3_BUCKET_NAME environment variable is required when USE_S3 is true")
            self.s3_client = boto3.client("s3")
        else:
            self.s3_client = None
            self.storage_dir = Path(storage_dir)
            self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_conversation_file(self, conversation_id: str) -> Path:
        """Get the file path for a conversation (local storage only)."""
        return self.storage_dir / f"{conversation_id}.json"
    
    def _get_s3_key(self, conversation_id: str) -> str:
        """Get the S3 key for a conversation."""
        return f"{conversation_id}.json"
    
    def _load_from_storage(self, conversation_id: str) -> dict:
        """Load conversation data from storage (S3 or local)."""
        if self.use_s3:
            s3_key = self._get_s3_key(conversation_id)
            try:
                response = self.s3_client.get_object(Bucket=self.s3_bucket, Key=s3_key)
                return json.loads(response["Body"].read().decode("utf-8"))
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "NoSuchKey":
                    # Conversation doesn't exist, return empty structure
                    return {
                        "conversation_id": conversation_id,
                        "created_at": datetime.utcnow().isoformat(),
                        "messages": [],
                    }
                else:
                    raise Exception(f"Error loading conversation from S3: {str(e)}")
        else:
            conversation_file = self._get_conversation_file(conversation_id)
            if conversation_file.exists():
                with open(conversation_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                return {
                    "conversation_id": conversation_id,
                    "created_at": datetime.utcnow().isoformat(),
                    "messages": [],
                }
    
    def _save_to_storage(self, conversation_id: str, conversation_data: dict) -> None:
        """Save conversation data to storage (S3 or local)."""
        if self.use_s3:
            s3_key = self._get_s3_key(conversation_id)
            json_str = json.dumps(conversation_data, indent=2, ensure_ascii=False)
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=json_str.encode("utf-8"),
                ContentType="application/json",
            )
        else:
            conversation_file = self._get_conversation_file(conversation_id)
            with open(conversation_file, "w", encoding="utf-8") as f:
                json.dump(conversation_data, f, indent=2, ensure_ascii=False)

    def save_interaction(
        self,
        conversation_id: str,
        question: str,
        answer: str,
        conversation_history: list = None,
    ) -> None:
        """
        Save an interaction (question and answer) to persistent storage.

        Args:
            conversation_id: UUID string identifying the conversation
            question: The user's question
            answer: The assistant's answer
            conversation_history: Previous conversation messages (optional)
        """
        # Load existing conversation from storage (S3 or local)
        conversation_data = self._load_from_storage(conversation_id)

        # Build prompt template format
        messages = conversation_data.get("messages", [])

        # Add conversation history if provided (to maintain full context)
        if conversation_history:
            for msg in conversation_history:
                role = msg.get("role", "") if isinstance(msg, dict) else msg.role
                content = msg.get("content", "") if isinstance(msg, dict) else msg.content
                # Only add if not already in messages (avoid duplicates)
                if not any(
                    m.get("role") == role and m.get("content") == content
                    for m in messages
                ):
                    messages.append(
                        {
                            "role": role,
                            "content": content,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

        # Add current question
        messages.append(
            {
                "role": "user",
                "content": question,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # Add current answer
        messages.append(
            {
                "role": "assistant",
                "content": answer,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # Update conversation data
        conversation_data["messages"] = messages
        conversation_data["updated_at"] = datetime.utcnow().isoformat()

        # Save to storage (S3 or local)
        self._save_to_storage(conversation_id, conversation_data)

    def format_as_prompt_template(self, conversation_id: str) -> str:
        """
        Format conversation history as a prompt template.

        Args:
            conversation_id: UUID string identifying the conversation

        Returns:
            Formatted prompt template string
        """
        conversation_data = self._load_from_storage(conversation_id)
        
        if not conversation_data.get("messages"):
            return ""

        messages = conversation_data.get("messages", [])
        formatted_lines = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role.lower() == "user":
                formatted_lines.append(f"Human: {content}")
            elif role.lower() == "assistant":
                formatted_lines.append(f"Assistant: {content}")

        return "\n".join(formatted_lines)

    def get_conversation_history(self, conversation_id: str) -> list:
        """
        Get conversation history for a conversation ID.

        Args:
            conversation_id: UUID string identifying the conversation

        Returns:
            List of conversation messages
        """
        conversation_data = self._load_from_storage(conversation_id)
        return conversation_data.get("messages", [])

    def generate_conversation_id(self) -> str:
        """Generate a new UUID for a conversation."""
        return str(uuid4())


# Global conversation history manager instance
_conversation_manager: ConversationHistoryManager | None = None


def get_conversation_manager(storage_dir: Optional[str] = None) -> ConversationHistoryManager:
    """
    Get or create the global conversation history manager instance.
    
    Args:
        storage_dir: Optional storage directory (defaults to MEMORY_DIR env var or ./persistent_conversation_history)
    
    Returns:
        ConversationHistoryManager instance configured for S3 or local storage
    """
    global _conversation_manager
    
    # Get storage directory from env or parameter
    if storage_dir is None:
        storage_dir = os.getenv("MEMORY_DIR", "./persistent_conversation_history")
    
    # Check if we need to recreate the manager (if config changed)
    use_s3 = os.getenv("USE_S3", "false").lower() == "true"
    s3_bucket = os.getenv("S3_BUCKET_NAME", "")
    
    if _conversation_manager is None:
        _conversation_manager = ConversationHistoryManager(
            storage_dir=storage_dir,
            use_s3=use_s3,
            s3_bucket=s3_bucket,
        )
    else:
        # Update if configuration changed
        if _conversation_manager.use_s3 != use_s3 or _conversation_manager.s3_bucket != s3_bucket:
            _conversation_manager = ConversationHistoryManager(
                storage_dir=storage_dir,
                use_s3=use_s3,
                s3_bucket=s3_bucket,
            )
    
    return _conversation_manager

