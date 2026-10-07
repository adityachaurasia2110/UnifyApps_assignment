from abc import ABC, abstractmethod
from typing import List, Type, TypeVar, Any
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
import os

T = TypeVar('T', bound=BaseModel)

class ILLMService(ABC):
    @abstractmethod
    def generate_structured_output(self, messages: List[BaseMessage], output_schema: Type[T]) -> T:
        pass

class GeminiLLMService(ILLMService):
    def __init__(self, model_name: str = "gemini-3.5-flash", temperature: float = 0):
        if not os.environ.get("GOOGLE_API_KEY"):
            # Ensure safe fallback or warning in real applications
            pass
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)

    def generate_structured_output(self, messages: List[BaseMessage], output_schema: Type[T]) -> T:
        import json
        from langchain_core.messages import SystemMessage
        
        # Append instructions for JSON format
        schema_json = output_schema.schema_json()
        instruction = f"You MUST return ONLY valid JSON matching this schema: {schema_json}. Do NOT include markdown code blocks (like ```json), just the raw JSON string."
        
        # We append a SystemMessage, or add to the last message
        new_messages = list(messages)
        new_messages.append(SystemMessage(content=instruction))
        
        response = self.llm.invoke(new_messages)
        text = response.content.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            parsed = json.loads(text)
            return output_schema(**parsed)
        except Exception as e:
            raise ValueError(f"Failed to parse LLM output as JSON: {text}. Error: {e}")

# Dependency Injection setup
def get_llm_service() -> ILLMService:
    return GeminiLLMService()
