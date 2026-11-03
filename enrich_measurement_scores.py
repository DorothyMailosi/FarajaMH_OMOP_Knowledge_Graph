import getpass
import hashlib
import hmac

import psycopg
from neo4j import GraphDatabase


# PostgreSQL connection
PG_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "postgres",
    "user": "postgres",
}

# Neo4j connection
NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_DATABASE = "neo4j"


def pseudonym(secret, record_type, original_id):
    message = f"{record_type}:{original_id}".encode("utf-8")

    return hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256
    ).hexdigest()


def extract_measurements(conn):
    query = """
        SELECT
            measurement_id,
            person_id,
            visit_occurrence_id,
            measurement_concept_id,
            value_as_number
        FROM study_2_cdm_r.measurement
        WHERE value_as_number IS NOT NULL
        ORDER BY measurement_id
    """

    with conn.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()


def prepare_rows(records, secret):
    rows = []

    for measurement_id, person_id, visit_id, concept_id, value in records:
        rows.append({
            "graph_id": pseudonym(
                secret, "Measurement", measurement_id
            ),
            "person_graph_id": pseudonym(
                secret, "person", person_id
            ),
            "visit_graph_id": (
                pseudonym(secret, "visit", visit_id)
                if visit_id is not None else None
            ),
            "concept_id": concept_id,
            "value_as_number": float(value),
        })

    return rows


def main():
    print("=" * 55)
    print("FARAJAMH STUDY 2 - MEASUREMENT ENRICHMENT")
    print("=" * 55)

    pg_password = getpass.getpass("PostgreSQL password: ")
    neo4j_password = getpass.getpass("Neo4j password: ")

    secret = getpass.getpass(
        "Enter the SAME pseudonymization secret used during import: "
    )

    if len(secret) < 24:
        raise ValueError(
            "The pseudonymization secret must contain at least 24 characters."
        )

    print("\nExtracting measurements from PostgreSQL...")

    with psycopg.connect(
        **PG_CONFIG,
        password=pg_password,
        options="-c default_transaction_read_only=on"
    ) as conn:
        records = extract_measurements(conn)

    rows = prepare_rows(records, secret)

    print("Source measurements with numeric values:", len(rows))

    with GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, neo4j_password)
    ) as driver:

        driver.verify_connectivity()

        print("\nChecking existing Neo4j measurements...")

        result, _, _ = driver.execute_query(
            """
            MATCH (m:Measurement)
            RETURN count(m) AS total
            """,
            database_=NEO4J_DATABASE
        )

        existing_count = result[0]["total"]

        print("Existing measurement nodes:", existing_count)

        # Verify that the generated IDs match existing nodes.
        # This query does not write anything.
        result, _, _ = driver.execute_query(
            """
            UNWIND $rows AS row
            MATCH (m:Measurement {graph_id: row.graph_id})
            MATCH (p:Person {graph_id: row.person_graph_id})
                  -[:HAS_MEASUREMENT]->(m)
            MATCH (v:Visit {graph_id: row.visit_graph_id})
                  -[:HAS_MEASUREMENT]->(m)
            MATCH (p)-[:HAS_VISIT]->(v)
            MATCH (m)-[:HAS_CONCEPT]->
                  (c:Concept {concept_id: row.concept_id})
            RETURN count(DISTINCT m) AS matched
            """,
            rows=rows,
            database_=NEO4J_DATABASE
        )

        matched_count = result[0]["matched"]

        print("Validated measurement matches:", matched_count)

        if existing_count != 300 or matched_count != existing_count:
            raise RuntimeError(
                "Validation failed. No measurements were updated. "
                "Check the pseudonymization secret, source data "
                "and existing graph relationships."
            )

        print("\nValidation successful. Updating scores...")

        # Update only existing, validated measurement nodes.
        driver.execute_query(
            """
            UNWIND $rows AS row
            MATCH (m:Measurement {graph_id: row.graph_id})
            SET m.value_as_number = row.value_as_number
            """,
            rows=rows,
            database_=NEO4J_DATABASE
        )

        result, _, _ = driver.execute_query(
            """
            MATCH (m:Measurement)
            RETURN
                count(m) AS total_measurements,
                count(m.value_as_number) AS measurements_with_scores
            """,
            database_=NEO4J_DATABASE
        )

        total = result[0]["total_measurements"]
        with_scores = result[0]["measurements_with_scores"]

        print("\nFINAL VALIDATION")
        print("Total measurements:", total)
        print("Measurements with scores:", with_scores)

        if total != 300 or with_scores != 300:
            raise RuntimeError(
                "Unexpected final counts. Review the enrichment."
            )

    print("\nMeasurement enrichment completed successfully!")


if __name__ == "__main__":
    main()
