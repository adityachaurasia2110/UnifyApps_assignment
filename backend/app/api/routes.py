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
        # Use stream instead of invoke to print intermediate steps
        final_state = state
        print(f"\n--- Starting LangGraph Workflow for Thread: {thread_id} ---")
        for step in agent_app.stream(state):
            for node_name, node_state in step.items():
                print(f"\n[Node Executed]: {node_name}")
                if "sql_query" in node_state:
                    print(f"  -> SQL Query: {node_state['sql_query']}")
                if "is_valid_sql" in node_state:
                    print(f"  -> Is Valid: {node_state['is_valid_sql']}")
            final_state.update(step[node_name])
            
        print("--- Workflow Complete ---\n")
        
        # The result messages contain the full updated list. The last one is the AIMessage.
        ai_message = final_state["messages"][-1]
        
        # We append both to our session
        sessions[thread_id].append(HumanMessage(content=request.message))
        sessions[thread_id].append(ai_message)
        
        try:
            parsed_content = json.loads(ai_message.content)
            return ChatResponse(
                sql=parsed_content.get("sql"),
                explanation=parsed_content.get("explanation"),
                results=parsed_content.get("results"),
                error=parsed_content.get("error"),
                execution_time_ms=parsed_content.get("execution_time_ms")
            )
        except json.JSONDecodeError:
            return ChatResponse(error="Failed to parse agent response.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
