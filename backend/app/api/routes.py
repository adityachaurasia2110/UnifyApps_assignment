import asyncio
import json
import threading
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.graph import agent_app
from app.models.schemas import ChatRequest, ChatResponse

router = APIRouter()

# In-memory session storage for simplicity in this assignment.
# In production, use Redis or a database to persist thread state.
sessions = {}

NODE_META = {
    "detect_intent": {
        "title": "Intent Classification",
        "description": "Analyzing request intent and multi-turn context...",
        "icon": "🎯"
    },
    "reject_out_of_scope": {
        "title": "Out of Scope",
        "description": "Query is outside database domain. Formulating rejection...",
        "icon": "🚫"
    },
    "retrieve_schema": {
        "title": "Schema Discovery",
        "description": "Inspecting tables (Employees, Departments, Customers)...",
        "icon": "📋"
    },
    "generate_sql": {
        "title": "SQL Generation",
        "description": "Synthesizing SQLite query via LLM reasoning...",
        "icon": "🧠"
    },
    "ask_clarification": {
        "title": "Clarification Required",
        "description": "Subjective or ambiguous request detected. Asking user...",
        "icon": "❓"
    },
    "validate_sql": {
        "title": "AST & Safety Validation",
        "description": "Verifying SQLGlot AST, read-only permissions, and table existence...",
        "icon": "🛡️"
    },
    "optimize_sql": {
        "title": "Query Optimization",
        "description": "Transpiling and formatting query for SQLite...",
        "icon": "⚡"
    },
    "execute_query": {
        "title": "Database Execution",
        "description": "Executing verified query against SQLite database...",
        "icon": "💾"
    },
    "generate_explanation": {
        "title": "Explanation Synthesis",
        "description": "Generating plain-English explanation of query logic...",
        "icon": "✍️"
    },
    "format_response": {
        "title": "Response Finalization",
        "description": "Assembling complete structured response payload...",
        "icon": "📦"
    }
}

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    thread_id = request.thread_id
    if thread_id not in sessions:
        sessions[thread_id] = []
    
    # Retrieve previous messages
    history = sessions[thread_id]
    
    # Configure the thread config for langgraph
    state = {"messages": history + [HumanMessage(content=request.message)]}
    
    try:
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
                clarification=parsed_content.get("clarification"),
                execution_time_ms=parsed_content.get("execution_time_ms")
            )
        except json.JSONDecodeError:
            return ChatResponse(error="Failed to parse agent response.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    thread_id = request.thread_id
    if thread_id not in sessions:
        sessions[thread_id] = []
    
    history = sessions[thread_id]
    state = {"messages": history + [HumanMessage(content=request.message)]}

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def run_agent():
            try:
                for step in agent_app.stream(state):
                    loop.call_soon_threadsafe(queue.put_nowait, ("step", step))
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", e))

        thread = threading.Thread(target=run_agent, daemon=True)
        thread.start()

        final_response_data: Optional[Dict[str, Any]] = None
        last_ai_message: Optional[AIMessage] = None

        while True:
            event_type, payload = await queue.get()

            if event_type == "error":
                err_msg = str(payload)
                yield f"data: {json.dumps({'event': 'error', 'error': err_msg})}\n\n"
                break

            elif event_type == "done":
                if final_response_data:
                    yield f"data: {json.dumps({'event': 'result', 'data': final_response_data})}\n\n"
                yield f"data: {json.dumps({'event': 'done'})}\n\n"
                break

            elif event_type == "step":
                for node_name, node_state in payload.items():
                    meta = NODE_META.get(node_name, {
                        "title": node_name.replace("_", " ").title(),
                        "description": f"Executing {node_name}...",
                        "icon": "⚡"
                    })
                    
                    step_data: Dict[str, Any] = {
                        "event": "step",
                        "node": node_name,
                        "title": meta["title"],
                        "description": meta["description"],
                        "icon": meta["icon"]
                    }

                    if "sql_query" in node_state and node_state["sql_query"]:
                        step_data["sql"] = node_state["sql_query"]
                    if "optimized_sql" in node_state and node_state["optimized_sql"]:
                        step_data["sql"] = node_state["optimized_sql"]
                    if "is_valid_sql" in node_state:
                        step_data["is_valid"] = node_state["is_valid_sql"]
                    if "sql_errors" in node_state and node_state["sql_errors"]:
                        step_data["error"] = node_state["sql_errors"]
                    if "execution_time_ms" in node_state:
                        step_data["execution_time_ms"] = node_state["execution_time_ms"]

                    yield f"data: {json.dumps(step_data)}\n\n"

                    # Handle explanation token streaming
                    if "explanation" in node_state and node_state["explanation"]:
                        explanation_text = node_state["explanation"]
                        words = explanation_text.split(" ")
                        for idx, w in enumerate(words):
                            chunk = w + (" " if idx < len(words) - 1 else "")
                            yield f"data: {json.dumps({'event': 'token', 'delta': chunk})}\n\n"
                            await asyncio.sleep(0.015)

                    # Extract final AIMessage if present
                    if "messages" in node_state and node_state["messages"]:
                        last_ai_message = node_state["messages"][-1]
                        try:
                            parsed = json.loads(last_ai_message.content)
                            final_response_data = {
                                "sql": parsed.get("sql"),
                                "explanation": parsed.get("explanation"),
                                "results": parsed.get("results"),
                                "error": parsed.get("error"),
                                "clarification": parsed.get("clarification"),
                                "execution_time_ms": parsed.get("execution_time_ms")
                            }

                            # Stream clarification or standalone error text if not streamed yet
                            if parsed.get("clarification"):
                                c_text = parsed["clarification"]
                                words = c_text.split(" ")
                                for idx, w in enumerate(words):
                                    chunk = w + (" " if idx < len(words) - 1 else "")
                                    yield f"data: {json.dumps({'event': 'token', 'delta': chunk})}\n\n"
                                    await asyncio.sleep(0.015)
                            elif parsed.get("error") and not parsed.get("sql"):
                                e_text = parsed["error"]
                                words = e_text.split(" ")
                                for idx, w in enumerate(words):
                                    chunk = w + (" " if idx < len(words) - 1 else "")
                                    yield f"data: {json.dumps({'event': 'token', 'delta': chunk})}\n\n"
                                    await asyncio.sleep(0.015)

                        except json.JSONDecodeError:
                            final_response_data = {"error": "Failed to parse agent response."}

        if last_ai_message:
            sessions[thread_id].append(HumanMessage(content=request.message))
            sessions[thread_id].append(last_ai_message)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

