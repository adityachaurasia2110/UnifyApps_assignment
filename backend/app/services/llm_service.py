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
    def __init__(self, model_names: List[str] = None, temperature: float = 0):
        if not model_names:
            self.model_names = [
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b",
                "qwen/qwen3.8-27b"
            ]
        elif isinstance(model_names, str):
            self.model_names = [model_names]
        else:
            self.model_names = list(model_names)
        self.temperature = temperature

    def generate_structured_output(self, messages: List[BaseMessage], output_schema: Type[T]) -> T:
        import json
        from langchain_core.messages import SystemMessage
        
        schema_json = json.dumps(output_schema.model_json_schema())
        schema_instruction = SystemMessage(
            content=f"IMPORTANT: You must respond ONLY with valid JSON strictly adhering to this JSON Schema:\n{schema_json}"
        )
        full_messages = [schema_instruction] + list(messages)

        last_error = None
        for model in self.model_names:
            try:
                llm = ChatGroq(model=model, temperature=self.temperature)
                structured_llm = llm.with_structured_output(output_schema, method="json_mode")
                return structured_llm.invoke(full_messages)
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                print(f"[LLM Service Notice]: Model {model} unavailable ({e}). Trying fallback...")
                continue
        
        if last_error:
            raise last_error

# Dependency Injection setup
def get_llm_service() -> ILLMService:
    return GroqLLMService()
