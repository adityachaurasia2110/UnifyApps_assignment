import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.graph import agent_app
from app.models.schemas import ChatRequest, ChatResponse

router = APIRouter()

# In-memory session storage for simplicity in this assignment.
# In production, use Redis or a database to persist thread state.
sessions = {}

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    thread_id = request.thread_id
    if thread_id not in sessions:
        sessions[thread_id] = []
    
    # Retrieve previous messages
    history = sessions[thread_id]
    
    # Prepare the input state
    inputs = {
        "messages": [HumanMessage(content=request.message)]
    }
    
    # Configure the thread config for langgraph (if using Checkpointer, otherwise we pass history)
    # We pass the full history plus the new message
    state = {"messages": history + [HumanMessage(content=request.message)]}
    
    try:
        result = agent_app.invoke(state)
        # The result messages contain the full updated list. The last one is the AIMessage.
        ai_message = result["messages"][-1]
        
        # We append both to our session
        sessions[thread_id].append(HumanMessage(content=request.message))
        sessions[thread_id].append(ai_message)
        
        try:
            parsed_content = json.loads(ai_message.content)
            return ChatResponse(
                sql=parsed_content.get("sql"),
                explanation=parsed_content.get("explanation"),
                results=parsed_content.get("results"),
                error=parsed_content.get("error")
            )
        except json.JSONDecodeError:
            return ChatResponse(error="Failed to parse agent response.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
