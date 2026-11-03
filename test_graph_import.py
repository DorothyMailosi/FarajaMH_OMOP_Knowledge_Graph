import getpass
from neo4j import GraphDatabase

URI = "bolt://127.0.0.1:7687"
USER = "neo4j"

password = getpass.getpass("Neo4j password: ")

# Entirely synthetic example: no Study 2 records.
query = """
MERGE (p:TestPerson {test_id: 'PYTHON_TEST_PERSON'})
SET p.label = 'Synthetic Participant'

MERGE (v:TestVisit {test_id: 'PYTHON_TEST_VISIT'})
SET v.label = 'Synthetic Visit'

MERGE (m:TestMeasurement {test_id: 'PYTHON_TEST_MEASUREMENT'})
SET m.label = 'Synthetic Assessment',
    m.value_as_number = 12

MERGE (c:TestConcept {test_id: 'PYTHON_TEST_CONCEPT'})
SET c.concept_name = 'Synthetic Mental Health Assessment'

MERGE (p)-[:HAS_VISIT]->(v)
MERGE (v)-[:HAS_MEASUREMENT]->(m)
MERGE (m)-[:HAS_CONCEPT]->(c)

RETURN p.test_id AS participant, c.concept_name AS concept
"""

with GraphDatabase.driver(URI, auth=(USER, password)) as driver:
    driver.verify_connectivity()

    records, summary, keys = driver.execute_query(
        query,
        database_="neo4j"
    )

    print("\nSUCCESS: Python created a synthetic graph in Neo4j!")

    for record in records:
        print("Participant:", record["participant"])
        print("Concept:", record["concept"])

    print("Nodes created:", summary.counters.nodes_created)
    print("Relationships created:", summary.counters.relationships_created)