import os
import sys
sys.path.append(os.path.dirname(__file__))

from langchain_core.messages import HumanMessage
from app.agent.graph import agent_app
import traceback

state = {"messages": [HumanMessage(content="Show all employees.")]}
try:
    result = agent_app.invoke(state)
    print("Success:", result)
except Exception as e:
    traceback.print_exc()
