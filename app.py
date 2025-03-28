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
    all_fields_present: bool
    missing_fields: str


template_prompt = """
This is the user's prompt: '{initial_prompt}'.
This is the database structure: {db_info}

Analyze the prompt and strictly respond with one of these:
- *INSERT* if the prompt contains any of: insert, add, create, new, register, introduce, enter, store, save, append, put, establish, initialize, generate, make, load, populate, enroll, submit, post
- *RETRIEVE* if the prompt contains any of: get, find, show, list, return, select, fetch, query, search, lookup, extract, obtain, view, display, print, read, check, verify, examine, scan
- *ERROR* if not database-related or tables don't exist

Respond with exactly one of: *INSERT* *RETRIEVE* *ERROR* and no other word. The output will mandatory be one of these 3.
"""


def get_query(state: State):
    if state["prompt"] == "":
        state["prompt"] = input("Enter your prompt: \n")
    elif state["prompt"] != "" and state["type"] == "ERROR":
        state["prompt"] = input("You introduced an INCORRECT PROMPT. Please retry: \n")
    elif state["prompt"] != "" and state["type"] != "ERROR" and state["missing_fields"] != "":
        state["prompt"] = input(f"You must introduce {state["missing_fields"]} too. Retry: \n")

    state["all_fields_present"] = True
    state["missing_fields"] = ""
    return state


def check_query_type(state: State):
    prompt = template_prompt.format(initial_prompt=state['prompt'], db_info=db_info)
    llm_response = askMistral(prompt).upper()
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


template_prompt_4 = """
Database: {db_info}
Prompt: "{initial_prompt}"

Instructions:
1. Identify which table the command is targeting. The possible tables are:
   - users
   - products
   - orders
   - orders_content

2. For the identified table, verify that the following required columns are provided:
   - For **users**: first_name, last_name, age, registration_date
   - For **products**: product_name, product_desc, price
   - For **orders**: user_id, date
   - For **orders_content**: order_id, product_id, units

3. Ignore any SERIAL primary key fields.

4. Produce EXACTLY one output:
   - If one or more required columns are missing, return their names as a comma-separated list (e.g., "last_name, age, registration_date").
   - If all required columns are present, return the exact string "all matched".

Examples:
- "register user John Smith 30 2023-05-15" → "all matched"
- "add product 'Laptop' 'Gaming laptop'" → "price"
- "create order for user 5" → "date"
- "add order item 101 205 3" → "all matched"   *(interpreted as orders_content)*
- "insert user named Alice" → "last_name, age, registration_date"
- "add user Bob Johnson" → "age, registration_date"
- "new product 'Monitor' 299.99" → "product_desc"
- "log order user7 2024-02-20" → "all matched"
- "record purchase 102 304" → "units"   *(interpreted as orders_content)*
- "enter user 'Charlie' 'Brown' 28" → "registration_date"

Note:
- For instance, if the command is "insert a user Todor Ioan, aged 20, registered on 01 01 2001", the system must ensure that all required fields for the users table are provided. If any are missing (for example, if it only detects first_name but not last_name, age, and registration_date), the output should list the missing fields (e.g., "last_name, age, registration_date").
- The keyword "*INSERT*" indicates that the command is for an insertion.

Output exactly one of:
- A comma-separated list of missing columns (if any are absent)
- The string "all matched" (if every required column is included)
"""


def check_for_all_fields(state: State):
    print("entered check_for_all_fields")
    check_prompt = template_prompt_4.format(initial_prompt=state["prompt"], db_info=db_info)
    check_response = askMistral(check_prompt).lower()
    print(check_response)

    if "all matched" in check_response:
        state["all_fields_present"] = True
        state["missing_fields"] = ""
    else:
        state["all_fields_present"] = False
        state["missing_fields"] = check_response

    return state


def check_for_all_fields_route(state: State):
    return str(state["all_fields_present"])


template_prompt_5 = """
# PostgreSQL INSERT Query Generation Prompt
I need a PostgreSQL INSERT query that fulfills this request: {initial_prompt}

## Database Context
Database structure is available here: {db_info}.

## Goal
- Construct a valid PostgreSQL `INSERT` query that resolves the user's request
- Use only the specified tables/columns while maintaining foreign key integrity
- Ensure all required fields are included for a successful insertion
- Return ONLY the raw SQL query (no explanations)

## Return Format
A single PostgreSQL `INSERT` query in plain text format

## Warnings
- Reject any tables/columns not listed in the schema
- Ensure all required fields are provided
- Validate date constraints (orders only cover 2025)
- Ensure proper handling of numeric values (e.g., age non-negative, price as decimal)
- Maintain relational integrity when inserting related records

## Context Dump
User's request: {initial_prompt}
Database Structure: {db_info}
"""


def do_insert(state: State):
    insert_prompt = template_prompt_5.format(initial_prompt=state["prompt"], db_info=db_info)
    insert_response = askMistral(insert_prompt)
    print(insert_response)

    try:
        do_db_insert(insert_response)
        state["insert_status"] = "SUCCESS"
        return state
    except Exception as e:
        state["insert_status"] = "ERROR"
        return state


def do_insert_route(state: State):
    return state["insert_status"]


template_prompt_3 = """
User's prompt: {initial_prompt}
The query was executed correctly. It was a {type} query.
Provide a one line conclusion about the prompt and say it was a successful operation.
"""


def print_result(state: State):
    print("\nthe program entered the print_state\n")
    print_prompt = template_prompt_3.format(initial_prompt=state["prompt"], type={state["type"]})
    print_response = llm_model.invoke(print_prompt).content
    print(print_response)

    if state["type"] == "RETRIEVE":
        print(state["sql_answer"])

    return state


builder = StateGraph(State)
builder.add_node("get_query", get_query)
builder.add_node("check_query_type", check_query_type)
builder.add_node("do_retrieve", do_retrieve)
builder.add_node("check_for_all_fields", check_for_all_fields)
builder.add_node("check_correctness", check_correctness)
builder.add_node("do_insert", do_insert)
builder.add_node("print_result", print_result)

builder.add_edge(START, "get_query")
builder.add_edge("get_query", "check_query_type")
builder.add_conditional_edges("check_query_type", do_type_route, {
    "RETRIEVE": "do_retrieve",
    "INSERT": "check_for_all_fields",
    "ERROR": "get_query"
})

builder.add_conditional_edges("check_for_all_fields", check_for_all_fields_route, {
    "True": "do_insert",
    "False": "get_query"
})

builder.add_conditional_edges("do_insert", do_insert_route, {
    "SUCCESS": "print_result",
    "ERROR": "do_insert"
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

initial_state = {
    "database_info": db_info,
    "type": "",
    "answer": "",
    "status": "",
    "correct": False,
    "suggested_new_query": "",
    "all_fields_present": True,
    "missing_fields": "",
    "prompt": "",
    "sql_answer": "",
    "insert_status": ""
}

graph = builder.compile()

result = graph.invoke(initial_state)


@app.route('/')
def hello_world():
    return 'Hello World!'


if __name__ == '__main__':
    app.run()
