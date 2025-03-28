import ollama
from langchain_ollama import ChatOllama

model = ChatOllama(model="llama3.2")

def askMistral(prompt: str) -> str:
    response = ollama.chat(model="mistral-nemo",
                           messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]