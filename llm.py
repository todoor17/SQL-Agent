from langchain_ollama import ChatOllama
import ollama

model = ChatOllama(model="llama3.2")

def askMistral(prompt: str) -> str:
    response = ollama.chat(model="mistral-nemo",
                           messages=[{"role": "user", "content": prompt}])
    print(response["message"]["content"])
    return response["message"]["content"]