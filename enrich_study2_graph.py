import getpass
import hashlib
import hmac

import psycopg
from neo4j import GraphDatabase


PG_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "postgres",
    "user": "postgres",
}

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


def extract_visit_sequences(conn):
    query = """
        SELECT
            person_id,
            visit_occurrence_id,
            ROW_NUMBER() OVER (
                PARTITION BY person_id
                ORDER BY visit_start_date, visit_occurrence_id
            ) AS visit_sequence
        FROM study_2_cdm_r.visit_occurrence
        ORDER BY person_id, visit_sequence
    """

    with conn.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()


def prepare_graph_rows(records, secret):
    rows = []

    for person_id, visit_id, sequence in records:
        rows.append({
            "person_graph_id": pseudonym(
                secret, "person", person_id
            ),
            "visit_graph_id": pseudonym(
                secret, "visit", visit_id
            ),
            "visit_sequence": sequence
        })

    return rows


def main():
    print("=" * 55)
    print("FARAJAMH STUDY 2 - VISIT SEQUENCING")
    print("=" * 55)

    pg_password = getpass.getpass(
        "PostgreSQL password: "
    )

    neo4j_password = getpass.getpass(
        "Neo4j password: "
    )

    secret = getpass.getpass(
        "Enter the SAME pseudonymization secret used for import: "
    )

    if not secret:
        raise ValueError("Pseudonymization secret is required.")

    print("\nExtracting visit sequences from PostgreSQL...")

    with psycopg.connect(
        **PG_CONFIG,
        password=pg_password,
        options="-c default_transaction_read_only=on"
    ) as conn:
        records = extract_visit_sequences(conn)

    rows = prepare_graph_rows(records, secret)

    print("PostgreSQL visits:", len(rows))

    print("\nConnecting to Neo4j...")

    with GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, neo4j_password),
        telemetry_disabled=True
    ) as driver:

        driver.verify_connectivity()

        # Only update visits already present in the pilot graph.
        matched, _, _ = driver.execute_query(
            """
            UNWIND $rows AS row
            MATCH (p:Person {graph_id: row.person_graph_id})
                  -[:HAS_VISIT]->
                  (v:Visit {graph_id: row.visit_graph_id})
            RETURN count(v) AS matched
            """,
            rows=rows,
            database_=NEO4J_DATABASE
        )

        matched_count = matched[0]["matched"]

        existing, _, _ = driver.execute_query(
            """
            MATCH (v:Visit)
            RETURN count(v) AS total
            """,
            database_=NEO4J_DATABASE
        )

        existing_count = existing[0]["total"]

        print("Existing Neo4j visits:", existing_count)
        print("Matched visits:", matched_count)

        # Stop if the secret does not match the original import.
        if matched_count != existing_count:
            raise RuntimeError(
                "Visit matching failed. Check that you used "
                "the same pseudonymization secret and that "
                "the graph contains only the expected pilot visits."
            )

        # Add sequence numbers.
        driver.execute_query(
            """
            UNWIND $rows AS row
            MATCH (p:Person {graph_id: row.person_graph_id})
                  -[:HAS_VISIT]->
                  (v:Visit {graph_id: row.visit_graph_id})
            SET v.visit_sequence = row.visit_sequence
            """,
            rows=rows,
            database_=NEO4J_DATABASE
        )

        print("Visit sequence numbers added.")

        # Create consecutive visit relationships.
        driver.execute_query(
            """
            MATCH (p:Person)-[:HAS_VISIT]->(v1:Visit)
            MATCH (p)-[:HAS_VISIT]->(v2:Visit)
            WHERE v2.visit_sequence = v1.visit_sequence + 1
            MERGE (v1)-[:NEXT_VISIT]->(v2)
            """,
            database_=NEO4J_DATABASE
        )

        print("NEXT_VISIT relationships created.")

        # Validate results.
        result, _, _ = driver.execute_query(
            """
            MATCH (v:Visit)
            RETURN
                count(v) AS total_visits,
                count(v.visit_sequence) AS sequenced_visits
            """,
            database_=NEO4J_DATABASE
        )

        relationship_result, _, _ = driver.execute_query(
            """
            MATCH (:Visit)-[r:NEXT_VISIT]->(:Visit)
            RETURN count(r) AS relationships
            """,
            database_=NEO4J_DATABASE
        )

        print("\nVALIDATION")
        print("Total visits:", result[0]["total_visits"])
        print(
            "Sequenced visits:",
            result[0]["sequenced_visits"]
        )
        print(
            "NEXT_VISIT relationships:",
            relationship_result[0]["relationships"]
        )

    print("\nVisit sequencing completed!")


if __name__ == "__main__":
    main()