import sys, os
sys.path.append(os.path.dirname(__file__))

from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)
print("Invoking...")
res = llm.invoke("Say hello")
print(res.content)
