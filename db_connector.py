from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

url = URL.create(drivername="postgresql",
    username="postgres",
    host="localhost",
    password="Norocel17",
    database="testLangGraph"
)

engine = create_engine(url)


def do_db_retrieve(received_text):
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            query = text(received_text)
            result = connection.execute(query)
            transaction.commit()

            return result.fetchall()
    except Exception as e:
        raise e


def do_db_insert(received_text):
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            query = text(received_text)
            connection.execute(query)
            transaction.commit()

            return "Inserted Successfully"
    except Exception as e:
        raise e


