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
    insert_status: str
    missing_fields: bool

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


def get_query(state: State):
    if not state["missing_fields"]:
        state["prompt"] = input("Enter your prompt: ")
        return state
    else:
        state["prompt"] = input("Enter your prompt. Your previous insert prompt had missing fields:\n")
        return state


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
# PostgreSQL Query Generation Prompt

"I need a PostgreSQL query that fulfills this request: {initial_prompt}

## Database Context
Available tables:
- users (user_id, first_name, last_name, age, registration_date)
- products (product_id, product_name, product_desc, price)
- orders (order_id, user_id, date)
- orders_content (orders_content_id, order_id, product_id, units)

Relationships:
- orders.user_id → users.user_id
- orders_content.order_id → orders.order_id
- orders_content.product_id → products.product_id

## Goal
- Create a valid PostgreSQL query matching the user's request
- Use only the specified tables/columns with proper joins
- Validate all foreign key relationships
- Return ONLY the raw SQL query (no explanations)

## Return Format
A single PostgreSQL query in plain text format

## Warnings
- Reject any tables/columns not in the provided schema
- Ensure proper joins using the documented relationships
- Validate date constraints (orders only cover 2025)
- Check age non-negativity requirements
- Handle decimal precision for price calculations

## Context Dump
User seeks data about: {initial_prompt}
Special considerations: 
- Order dates strictly within 2025
- Age must be non-negative
- Price calculations need proper decimal handling
"""

def do_retrieve(state: State):
    retrieve_prompt = template_prompt_1.format(initial_prompt=state['prompt'], db_info=db_info, suggested_new_query=state['suggested_new_query'])
    llm_result = askMistral(retrieve_prompt)
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
# Query Validation Prompt

"I need to verify if this PostgreSQL query: {answer}
accurately solves: {initial_prompt}

## Database Context
Available tables:
- users (user_id, first_name, last_name, age, registration_date)
- products (product_id, product_name, product_desc, price)
- orders (order_id, user_id, date)
- orders_content (orders_content_id, order_id, product_id, units)

## Goal
- Confirm query matches all user requirements
- Identify schema mismatches or logic errors
- Validate all joins and constraints
- Check for proper date filtering (2025 only)

## Return Format
First line: 'yes' or 'no' 
Second line: Error explanation (if 'no') + fix suggestion

## Warnings
- Flag incorrect table/column references
- Catch invalid joins missing relationship paths
- Verify date constraints (orders.date must be in 2025)
- Check age non-negativity enforcement
- Validate decimal handling for price calculations

## Context Dump
Query purpose: {initial_prompt}
Critical constraints:
- All order dates must be in 2025
- User ages cannot be negative
- Price calculations require precision
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
    try:
        do_db_insert(state["sql_answer"])
        state["insert_status"] = "SUCCESS"
    except Exception as e:
        state["insert_status"] = "ERROR"



template_prompt_3 = """
Congratulations, you executed the user's prompt correctly.
This was the initial user's prompt: {initial_prompt}.
In one line, compute a conclusion success message.
"""


def print_result(state: State):
    print("\nthe program entered the print_state\n")
    print_prompt = template_prompt_3.format(initial_prompt=state["prompt"], db_info=db_info)
    print_response = llm_model.invoke(print_prompt).content
    print(print_response)

    if state["type"] == "RETRIEVE":
        print(state["sql_answer"])

    return state


builder = StateGraph(State)
builder.add_node("get_query", get_query)
builder.add_node("check_query_type", check_query_type)
builder.add_node("do_retrieve", do_retrieve)
builder.add_node("check_correctness", check_correctness)
builder.add_node("do_insert", do_insert)
builder.add_node("print_result", print_result)

builder.add_edge(START, "get_query")
builder.add_edge("get_query", "check_query_type")
builder.add_conditional_edges("check_query_type", do_type_route, {
    "RETRIEVE": "do_retrieve",
    "INSERT": "do_insert",
    "ERROR": END
})

builder.add_conditional_edges("do_retrieve", do_retrieve_route, {
    "ERROR": "do_retrieve",
    "SUCCESS": "check_correctness"
})

builder.add_conditional_edges("check_correctness", check_correctness_route, {
    "CORRECT": "print_result",
    "INCORRECT": "do_retrieve"
})

builder.add_edge("print_result", END)

keyboard_prompt = input("Enter your prompt: ")

initial_state = {"database_info": db_info, "type": "", "answer": "", "correct": "", "suggested_new_query": "", "missing_fields": False}

graph = builder.compile()

result = graph.invoke(initial_state)


@app.route('/')
def hello_world():
    return 'Hello World!'


if __name__ == '__main__':
    app.run()
