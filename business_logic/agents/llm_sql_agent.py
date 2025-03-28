from business_logic.models import llm_models
from typing import Dict
from typing_extensions import TypedDict
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from data.data import db_info
from business_logic.models.llm_models import askMistral
from business_logic.database.db_connector import do_db_retrieve, do_db_insert
from data.prompt_templates import template_prompt, template_prompt_1, template_prompt_2, template_prompt_4, template_prompt_5

llm_model = llm_models.model

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


def print_result(state: State):
    if state["type"] == "RETRIEVE":
        print(f"You retrieval was successful. Her is the data for the prompt: {state['prompt']}:")
        print(state["sql_answer"])
    print("The insert operation was successful.")

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

graph = builder.compile()

#graph.get_graph().draw_mermaid_png(output_file_path="diagram.png")
