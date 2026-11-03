import getpass
import hashlib
import hmac

import psycopg
from neo4j import GraphDatabase


# ============================================================
# CONFIGURATION
# ============================================================

PG_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "postgres",
    "user": "postgres",
}

NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_DATABASE = "neo4j"

EXPECTED_PILOT_OBSERVATIONS = 450


# ============================================================
# PSEUDONYMIZATION
# ============================================================

def pseudonym(secret, record_type, original_id):

    message = f"{record_type}:{original_id}".encode("utf-8")

    return hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256
    ).hexdigest()


# ============================================================
# EXTRACT OBSERVATIONS
# ============================================================

def extract_observations(conn):

    query = """
        SELECT
            observation_id,
            person_id,
            visit_occurrence_id,
            observation_concept_id,
            value_as_number,
            value_as_concept_id
        FROM study_2_cdm_r.observation
        ORDER BY observation_id
    """

    with conn.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()


# ============================================================
# PREPARE GRAPH ROWS
# ============================================================

def prepare_rows(records, secret):

    rows = []

    for (
        observation_id,
        person_id,
        visit_id,
        concept_id,
        numeric_value,
        categorical_value
    ) in records:

        rows.append({
            "graph_id": pseudonym(
                secret,
                "Observation",  # Capital O: original import convention
                observation_id
            ),

            "person_graph_id": pseudonym(
                secret,
                "person",
                person_id
            ),

            "visit_graph_id": (
                pseudonym(secret, "visit", visit_id)
                if visit_id is not None
                else None
            ),

            "concept_id": concept_id,

            "value_as_number": (
                float(numeric_value)
                if numeric_value is not None
                else None
            ),

            "value_as_concept_id": (
                int(categorical_value)
                if categorical_value not in (None, 0)
                else None
            )
        })

    return rows


# ============================================================
# VALIDATE EXISTING GRAPH
# ============================================================

VALIDATION_QUERY = """
    UNWIND $rows AS row

    MATCH (o:Observation {graph_id: row.graph_id})

    MATCH (p:Person {graph_id: row.person_graph_id})
          -[:HAS_OBSERVATION]->(o)

    MATCH (p)-[:HAS_VISIT]->
          (v:Visit {graph_id: row.visit_graph_id})

    MATCH (v)-[:HAS_OBSERVATION]->(o)

    MATCH (o)-[:HAS_CONCEPT]->
          (c:Concept {concept_id: row.concept_id})

    RETURN count(DISTINCT o) AS matched
"""


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("FARAJAMH STUDY 2 - OBSERVATION ENRICHMENT")
    print("=" * 60)

    pg_password = getpass.getpass("PostgreSQL password: ")
    neo4j_password = getpass.getpass("Neo4j password: ")

    secret = getpass.getpass(
        "Enter the SAME pseudonymization secret used during import: "
    )

    if len(secret) < 24:
        raise ValueError(
            "Pseudonymization secret must contain at least 24 characters."
        )

    # --------------------------------------------------------
    # EXTRACT POSTGRESQL DATA
    # --------------------------------------------------------

    print("\nConnecting to PostgreSQL...")

    with psycopg.connect(
        **PG_CONFIG,
        password=pg_password,
        options="-c default_transaction_read_only=on"
    ) as conn:

        records = extract_observations(conn)

    rows = prepare_rows(records, secret)

    print("Source observations:", len(rows))

    # --------------------------------------------------------
    # CONNECT TO NEO4J
    # --------------------------------------------------------

    print("\nConnecting to Neo4j...")

    with GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, neo4j_password),
        telemetry_disabled=True
    ) as driver:

        driver.verify_connectivity()

        with driver.session(database=NEO4J_DATABASE) as session:

            # ------------------------------------------------
            # CHECK EXISTING NODES
            # ------------------------------------------------

            existing_count = session.run(
                """
                MATCH (o:Observation)
                RETURN count(o) AS total
                """
            ).single()["total"]

            print("Existing observation nodes:", existing_count)

            if existing_count != EXPECTED_PILOT_OBSERVATIONS:
                raise RuntimeError(
                    "Unexpected observation count. "
                    "No changes were made."
                )

            # ------------------------------------------------
            # VALIDATE ALL EXISTING LINKS
            # ------------------------------------------------

            print("\nValidating observation relationships...")

            result = session.run(
                VALIDATION_QUERY,
                rows=rows
            ).single()

            matched_count = result["matched"]

            print("Validated observation matches:", matched_count)

            if matched_count != existing_count:
                raise RuntimeError(
                    "Validation failed. No observations were updated. "
                    "Check pseudonymization, IDs and graph relationships."
                )

            # ------------------------------------------------
            # UPDATE OBSERVATION VALUES
            # ------------------------------------------------

            print("\nValidation successful!")
            print("Updating observation values...")

            update_query = """
                UNWIND $rows AS row

                MATCH (o:Observation {graph_id: row.graph_id})

                SET
                    o.value_as_number = row.value_as_number,
                    o.value_as_concept_id = row.value_as_concept_id
            """

            # All 450 updates in one transaction.
            # If an error occurs, the transaction rolls back.
            with session.begin_transaction() as tx:

                tx.run(update_query, rows=rows).consume()

                result = tx.run(
                    """
                    MATCH (o:Observation)

                    RETURN
                        count(o) AS total,
                        count(o.value_as_number) AS numeric_values,
                        count(o.value_as_concept_id) AS categorical_values
                    """
                ).single()

                total = result["total"]
                numeric = result["numeric_values"]
                categorical = result["categorical_values"]

                print("\nFINAL VALIDATION")
                print("Total observations:", total)
                print("Numeric values:", numeric)
                print("Categorical values:", categorical)

                if total != EXPECTED_PILOT_OBSERVATIONS:
                    raise RuntimeError(
                        "Unexpected observation count. "
                        "Transaction will be rolled back."
                    )

                tx.commit()

    print("\nSUCCESS: Observation enrichment completed!")


if __name__ == "__main__":
    main()