from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

uri      = os.getenv("NEO4J_URI")
user     = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

print(f"URI:             {uri}")
print(f"User:            {user}")
print(f"Password length: {len(password) if password else 'NONE'}")

driver = GraphDatabase.driver(uri, auth=(user, password))
with driver.session() as session:
    result = session.run("RETURN 1 AS test")
    print("Connected:", result.single()["test"])
driver.close()