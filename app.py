from typing import Dict
from flask import Flask
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from typing_extensions import TypedDict
from data import db_info
import llm
from data import db_info
from langchain_ollama import ChatOllama
import ollama
from llm import askMistral, model
from db_connector import do_db_retrieve, do_db_insert
app = Flask(__name__)

llm_model = llm.model

class State(TypedDict):
    prompt: str
    database_info: Dict[str, str]
    type: str
    suggestion: str
    answer: str


template_prompt = """
This is the user's prompt: {initial_prompt}. 
This is the database structure: {db_info} 
Check the database structure. If it's a question not related to the tables there, just return *ERROR* and ignore the rest of the instructions.
Else, rephrase the prompt to make it clearer and more structured for an LLM. 

Your response should follow this format:  
1. One the first row, the initial enhanced prompt, underlining the important data.
2. No empty line between the first and the second row.
3. One the second row, a single word indicating the type of request: *INSERT* or *RETRIEVE*. If it s not a SQL prompt related return *ERROR*.

Examples:  
- Rephrased prompt. *INSERT*  
- Rephrased prompt. *RETRIEVE*     
- *ERROR*
"""


def get_refined_query(state: State):
    prompt = template_prompt.format(initial_prompt=state['prompt'], db_info=db_info)
    llm_response = llm_model.invoke(prompt).content
    print(llm_response)

    parts = llm_response.split('\n')
    suggestion = parts[0]
    state["suggestion"] = suggestion

    query_type = ""
    if "INSERT" in llm_response or "insert" in llm_response:
        state["type"] = "INSERT"
    elif "RETRIEVE" in llm_response or "retrieve" in llm_response:
        state["type"] = "RETRIEVE"
    else:
        state["type"] = "ERROR"

    return state


def check_next_node(state: State):
    if state["type"] == "RETRIEVE":
        print("goes to retrieve")
        return "RETRIEVE"
    elif state["type"] == "INSERT":
        print("goes to insert")
        return "INSERT"
    elif state["type"] == "ERROR":
        print("ERROR. GRAPH ENDS HERE")
        return "ERROR"


def do_retrieve(state: State):
    pass


def do_insert(state: State):
    pass


builder = StateGraph(State)
builder.add_node("get_refined_query", get_refined_query)
builder.add_node("do_retrieve", do_retrieve)
builder.add_node("do_insert", do_insert)

builder.add_edge(START, "get_refined_query")
builder.add_conditional_edges("get_refined_query", check_next_node, {
    "RETRIEVE": "do_retrieve",
    "INSERT": "do_insert",
    "ERROR": END,
})

builder.add_edge("get_refined_query", END)

# keyboard_prompt = input("Enter your prompt: ")
keyboard_prompt1 = "whats the age of user with id 20?"
keyboard_prompt2 = "insert a user with age 20 and name Todor"
keyboard_prompt3 = "what s the weather like tomorrow?"
initial_state = {"prompt": keyboard_prompt3, "database_info": {}, "type": "", "suggestion": "", "answer": ""}

graph = builder.compile()

result = graph.invoke(initial_state)

# print(askMistral("Do an sql query for finding the max"))


@app.route('/')
def hello_world():
    return 'Hello World!'


if __name__ == '__main__':
    app.run()
