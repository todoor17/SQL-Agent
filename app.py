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
    answer: str
    status: str
    correct: bool
    suggested_new_query: str
    sql_answer: str

template_prompt = """
This is the user's prompt: {initial_prompt}. 
This is the database structure: {db_info} 
Check the database structure. If it's a not a SQL question or a question not related to the tables there, just return *ERROR* and ignore the rest of the instructions.

Your response should follow this format: a single word indicating the type of request: *INSERT* or *RETRIEVE*. If it s not a SQL prompt related return *ERROR*.

Examples:  
- *INSERT*  
- *RETRIEVE*     
- *ERROR*
"""


def check_query_type(state: State):
    prompt = template_prompt.format(initial_prompt=state['prompt'], db_info=db_info)
    llm_response = llm_model.invoke(prompt).content
    print(llm_response)

    if "INSERT" in llm_response or "insert" in llm_response or "Insert" in llm_response:
        state["type"] = "INSERT"
    elif "RETRIEVE" in llm_response or "retrieve" in llm_response or "Retrieve" in llm_response:
        state["type"] = "RETRIEVE"
    else:
        state["type"] = "ERROR"

    return state


def do_type_route(state: State):
    if state["type"] == "RETRIEVE":
        print("goes to retrieve\n")
        return "RETRIEVE"
    elif state["type"] == "INSERT":
        print("goes to insert\n")
        return "INSERT"
    elif state["type"] == "ERROR":
        print("ERROR. GRAPH ENDS HERE")
        return "ERROR"


template_prompt_1 = """
You are a PostgreSQL prompts solver.
This is the user's prompt: {initial_prompt}
This is the database structure: {db_info}
If there is content in the suggested_new_query: {suggested_new_query}, it means that an attempt was already made. Check the content of that and take that into consideration.
Otherwise, if suggested_new_query is empty, just ignore it.

I want you to create a PostgreSQL query that solves the prompt. 

STEPS:
1. Read the database structure.
2. Check the user's prompt and the enhanced prompt and decide what to do.
2.1 (Optional Step, just if there is content in suggested_new_query). Take into consideration the content of suggested_new_query.
3. Be careful to use only tables and columns from {db_info}. Also, make sure there is a valid link between the tables and columns you use.
4. Make sure you use valid aliases in a valid way. Also, make sure you use only valid PostgreSQL keywords and functions.
5. Provide JUST THE POSTGRESQL QUERY. !Important! No markdowns, headers, or other explanations. I want only the SQL query.
"""


def do_retrieve(state: State):
    prompt = template_prompt_1.format(initial_prompt=state['prompt'], db_info=db_info, suggested_new_query=state['suggested_new_query'])
    llm_result = askMistral(prompt)
    print(llm_result)
    print("\n")

    try:
        db_result = do_db_retrieve(llm_result)
        state["sql_answer"] = db_result
        state["answer"] = llm_result
        state["status"] = "SUCCESS"
        return state
    except Exception as e:
        state["status"] = "ERROR"
        return state


def do_retrieve_route(state: State):
    if state["status"] == "SUCCESS":
        print("goes to check_correctness")
        return "SUCCESS"
    elif state["status"] == "ERROR":
        return "ERROR"


template_prompt_2 = """
This is the user's prompt: {initial_prompt}
This is the PostgreSQL query solution I have: {answer}
Will my query produce the expected output? 
Answer with yes / no on the first row. Please do not insert a space between the first and the second row.
On the second row, do an explanation about the thing that causes the error and suggest a fix.
"""


def check_correctness(state: State):
    print("entered check_correctness")
    check_prompt = template_prompt_2.format(initial_prompt = state["prompt"], answer=state["answer"], db_info=db_info)
    check_response = askMistral(check_prompt)
    print(check_response)

    if "yes" in check_response or "Yes" in check_response or "YES" in check_response:
        state["correct"] = True
    elif "no" in check_response or "No" in check_response or "NO" in check_response:
        state["correct"] = False
        suggested_fix = "\n".join(state["suggested_new_query"].split("\n")[1:])
        state["suggested_new_query"] = suggested_fix

    return state


def check_correctness_route(state: State):
    if state["correct"]:
        print("the program goes in print_result state\n")
        return "CORRECT"
    else:
        print("the program returns in do_retrieve\n")
        return "INCORRECT"


def do_insert(state: State):
    pass


template_prompt_3 = """
Congratulations, you executed the user's prompt correctly.
This was the initial user's prompt: {initial_prompt}.
In one line, compute a conclusion success message.
"""


def print_result(state: State):
    print("\nthe program entered the print_state\n")
    print_prompt = template_prompt_3.format(initial_prompt=state["prompt"])
    print_response = llm_model.invoke(print_prompt).content
    print(print_response)

    if state["type"] == "RETRIEVE":
        print(state["sql_answer"])

    return state


builder = StateGraph(State)
builder.add_node("check_query_type", check_query_type)
builder.add_node("do_retrieve", do_retrieve)
builder.add_node("check_correctness", check_correctness)
builder.add_node("do_insert", do_insert)
builder.add_node("print_result", print_result)

builder.add_edge(START, "check_query_type")
builder.add_conditional_edges("check_query_type", do_type_route, {
    "RETRIEVE": "do_retrieve",
    "INSERT": "do_insert",
    "ERROR": END
})

builder.add_conditional_edges("do_retrieve", do_retrieve_route, {
    "ERROR": "do_retrieve",
    "SUCCESS": "check_correctness"
})

# builder.add_edge("check_correctness", END)

builder.add_conditional_edges("check_correctness", check_correctness_route, {
    "CORRECT": "print_result",
    "INCORRECT": "do_retrieve"
})

builder.add_edge("print_result", END)

# keyboard_prompt = input("Enter your prompt: ")
keyboard_prompt = "what is the average order cost?"
keyboard_prompt1 = "whats the age of user with id 20?"
keyboard_prompt2 = "insert a user with age 20 and name Todor"
keyboard_prompt3 = "what is the color of the sky?"

initial_state = {"prompt": keyboard_prompt, "database_info": db_info, "type": "", "answer": "", "correct": "", "suggested_new_query": ""}

graph = builder.compile()

result = graph.invoke(initial_state)


@app.route('/')
def hello_world():
    return 'Hello World!'


if __name__ == '__main__':
    app.run()
