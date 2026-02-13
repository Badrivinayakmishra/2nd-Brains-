"""
AI Service for OpenAI / Azure OpenAI integration.
Handles embeddings, completions, and classifications.
"""
from typing import List, Optional, Dict, Any, AsyncGenerator
import asyncio

from openai import AsyncOpenAI, AsyncAzureOpenAI

from core.config import get_settings

settings = get_settings()


class AIService:
    """Service for AI operations using OpenAI or Azure OpenAI."""

    def __init__(self):
        self._client = None
        self._embedding_model = "text-embedding-3-small"
        self._chat_model = "gpt-4o-mini"

    @property
    def client(self) -> AsyncOpenAI:
        """Lazy load OpenAI client."""
        if self._client is None:
            if settings.AZURE_OPENAI_API_KEY and settings.AZURE_OPENAI_ENDPOINT:
                self._client = AsyncAzureOpenAI(
                    api_key=settings.AZURE_OPENAI_API_KEY,
                    api_version=settings.AZURE_OPENAI_API_VERSION,
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
                )
                self._chat_model = settings.AZURE_OPENAI_DEPLOYMENT
            else:
                self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    # ============== Embeddings ==============

    async def create_embedding(self, text: str) -> List[float]:
        """Create embedding for a single text."""
        response = await self.client.embeddings.create(
            model=self._embedding_model,
            input=text
        )
        return response.data[0].embedding

    async def create_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Create embeddings for multiple texts efficiently.
        Processes in batches to avoid rate limits.
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await self.client.embeddings.create(
                model=self._embedding_model,
                input=batch
            )
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

            # Small delay between batches to avoid rate limits
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)

        return all_embeddings

    # ============== Chat Completions ==============

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Generate a chat response."""
        formatted_messages = []

        # Add system prompt
        if system_prompt:
            system_content = system_prompt
            if context:
                system_content += f"\n\nRelevant context from user's documents:\n{context}"
            formatted_messages.append({"role": "system", "content": system_content})

        # Add conversation history
        formatted_messages.extend(messages)

        response = await self.client.chat.completions.create(
            model=self._chat_model,
            messages=formatted_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        return response.choices[0].message.content

    async def generate_response_stream(
        self,
        messages: List[Dict[str, str]],
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming chat response."""
        formatted_messages = []

        if system_prompt:
            system_content = system_prompt
            if context:
                system_content += f"\n\nRelevant context from user's documents:\n{context}"
            formatted_messages.append({"role": "system", "content": system_content})

        formatted_messages.extend(messages)

        stream = await self.client.chat.completions.create(
            model=self._chat_model,
            messages=formatted_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    # ============== Classification ==============

    async def classify_document(
        self,
        content: str,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Classify a document as work or personal.
        Returns classification and confidence.
        """
        prompt = f"""Classify the following document as either "work" or "personal".

Title: {title or "Untitled"}
Content: {content[:2000]}

Respond with a JSON object containing:
- classification: "work" or "personal"
- confidence: a number between 0 and 1
- reason: brief explanation

JSON:"""

        response = await self.client.chat.completions.create(
            model=self._chat_model,
            messages=[
                {"role": "system", "content": "You are a document classifier. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=200
        )

        try:
            import json
            result = json.loads(response.choices[0].message.content)
            return result
        except:
            return {
                "classification": "work",
                "confidence": 0.5,
                "reason": "Unable to parse classification"
            }

    async def detect_knowledge_gaps(
        self,
        documents: List[Dict[str, str]],
        existing_gaps: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze documents to detect knowledge gaps.
        Returns list of questions that represent gaps.
        """
        doc_summaries = []
        for doc in documents[:10]:  # Limit to avoid token limits
            title = doc.get("title", "Untitled")
            content = doc.get("content", "")[:500]
            doc_summaries.append(f"- {title}: {content}")

        prompt = f"""Analyze these documents and identify knowledge gaps - questions that should be answered but aren't addressed in the documents.

Documents:
{chr(10).join(doc_summaries)}

{"Existing gaps (don't repeat): " + ", ".join(existing_gaps) if existing_gaps else ""}

Identify 3-5 knowledge gaps. For each gap, provide:
- question: The specific question
- category: Topic category
- priority: 1-5 (5 being most important)

Respond with a JSON array of gap objects.

JSON:"""

        response = await self.client.chat.completions.create(
            model=self._chat_model,
            messages=[
                {"role": "system", "content": "You are a knowledge gap analyst. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )

        try:
            import json
            result = json.loads(response.choices[0].message.content)
            return result if isinstance(result, list) else []
        except:
            return []

    async def generate_document_summary(self, content: str, max_length: int = 200) -> str:
        """Generate a summary of a document."""
        response = await self.client.chat.completions.create(
            model=self._chat_model,
            messages=[
                {"role": "system", "content": f"Summarize the following content in {max_length} characters or less."},
                {"role": "user", "content": content[:3000]}
            ],
            temperature=0.3,
            max_tokens=100
        )

        return response.choices[0].message.content
