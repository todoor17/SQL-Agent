from flask import Flask
from business_logic.agents.llm_sql_agent import graph
from data.data import db_info
app = Flask(__name__)

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

result = graph.invoke(initial_state)
print(result)

@app.route('/')
def hello_world():
    return 'Hello World!'


if __name__ == '__main__':
    app.run()
