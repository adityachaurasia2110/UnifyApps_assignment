from abc import ABC, abstractmethod
from typing import List, Type, TypeVar, Any
from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

T = TypeVar('T', bound=BaseModel)

class ILLMService(ABC):
    @abstractmethod
    def generate_structured_output(self, messages: List[BaseMessage], output_schema: Type[T]) -> T:
        pass

class GroqLLMService(ILLMService):
    def __init__(self, model_name: str = "openai/gpt-oss-120b", temperature: float = 0):
        if not os.environ.get("GROQ_API_KEY"):
            # Ensure safe fallback or warning in real applications
            pass
        self.llm = ChatGroq(model=model_name, temperature=temperature)

    def generate_structured_output(self, messages: List[BaseMessage], output_schema: Type[T]) -> T:
        import json
        from langchain_core.messages import SystemMessage
        
        structured_llm = self.llm.with_structured_output(output_schema, method="json_mode")
        schema_json = json.dumps(output_schema.model_json_schema())
        schema_instruction = SystemMessage(
            content=f"IMPORTANT: You must respond ONLY with valid JSON strictly adhering to this JSON Schema:\n{schema_json}"
        )
        return structured_llm.invoke([schema_instruction] + list(messages))

# Dependency Injection setup
def get_llm_service() -> ILLMService:
    return GroqLLMService()
