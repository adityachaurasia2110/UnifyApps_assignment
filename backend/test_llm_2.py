import sys, os
sys.path.append(os.path.dirname(__file__))

from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
print("Invoking 2.5-flash...")
try:
    res = llm.invoke("Say hello")
    print("Success:", res.content)
except Exception as e:
    print("Failed:", e)
