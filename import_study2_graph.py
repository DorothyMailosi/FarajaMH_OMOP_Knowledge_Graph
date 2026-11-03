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

EXPECTED_PILOT_MEASUREMENTS = 300
BATCH_SIZE = 500


# ============================================================
# PSEUDONYMIZATION
# IMPORTANT: MATCHES THE ORIGINAL IMPORT SCRIPT
# ============================================================

def pseudonym(secret, record_type, original_id):

    message = f"{record_type}:{original_id}".encode("utf-8")

    return hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256
    ).hexdigest()


# ============================================================
# EXTRACT MEASUREMENTS FROM POSTGRESQL
# ============================================================

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


# ============================================================
# PREPARE NEO4J ROWS
# ============================================================

def prepare_rows(records, secret):

    rows = []

    for measurement_id, person_id, visit_id, concept_id, value in records:

        rows.append({

            # CORRECTED: Capital M matches original import.
            "graph_id": pseudonym(
                secret,
                "Measurement",
                measurement_id
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

            "value_as_number": float(value)

        })

    return rows


# ============================================================
# BATCHED VALIDATION
# ============================================================

def validate_measurement_matches(driver, rows):

    query = """
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
    """

    matched_total = 0

    for start in range(0, len(rows), BATCH_SIZE):

        batch = rows[start:start + BATCH_SIZE]

        result, _, _ = driver.execute_query(
            query,
            rows=batch,
            database_=NEO4J_DATABASE
        )

        matched_total += result[0]["matched"]

    return matched_total


# ============================================================
# UPDATE EXISTING MEASUREMENT NODES
# ============================================================

def update_measurements(driver, rows):

    query = """
        UNWIND $rows AS row

        MATCH (m:Measurement {graph_id: row.graph_id})

        SET m.value_as_number = row.value_as_number
    """

    for start in range(0, len(rows), BATCH_SIZE):

        batch = rows[start:start + BATCH_SIZE]

        driver.execute_query(
            query,
            rows=batch,
            database_=NEO4J_DATABASE
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("FARAJAMH STUDY 2 - MEASUREMENT ENRICHMENT")
    print("=" * 60)

    pg_password = getpass.getpass(
        "PostgreSQL password: "
    )

    neo4j_password = getpass.getpass(
        "Neo4j password: "
    )

    secret = getpass.getpass(
        "Enter the SAME pseudonymization secret used during import: "
    )

    if len(secret) < 24:
        raise ValueError(
            "The pseudonymization secret must contain at least 24 characters."
        )

    # --------------------------------------------------------
    # CONNECT TO POSTGRESQL
    # --------------------------------------------------------

    print("\nConnecting to PostgreSQL...")

    with psycopg.connect(
        **PG_CONFIG,
        password=pg_password,
        options="-c default_transaction_read_only=on"
    ) as conn:

        records = extract_measurements(conn)

    rows = prepare_rows(records, secret)

    print("Source measurements with numeric values:", len(rows))

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

        # ----------------------------------------------------
        # CHECK EXISTING MEASUREMENTS
        # ----------------------------------------------------

        result, _, _ = driver.execute_query(
            """
            MATCH (m:Measurement)
            RETURN count(m) AS total
            """,
            database_=NEO4J_DATABASE
        )

        existing_count = result[0]["total"]

        print("Existing measurement nodes:", existing_count)

        if existing_count != EXPECTED_PILOT_MEASUREMENTS:
            raise RuntimeError(
                f"Expected {EXPECTED_PILOT_MEASUREMENTS} pilot "
                f"measurements, but found {existing_count}. "
                "No changes were made."
            )

        # ----------------------------------------------------
        # VALIDATE GRAPH MATCHES
        # ----------------------------------------------------

        print("\nValidating measurement relationships...")

        matched_count = validate_measurement_matches(
            driver,
            rows
        )

        print("Validated measurement matches:", matched_count)

        if matched_count != existing_count:
            raise RuntimeError(
                "Validation failed. No measurements were updated. "
                "Check the pseudonymization secret, source data, "
                "and existing graph relationships."
            )

        # ----------------------------------------------------
        # UPDATE SCORES
        # ----------------------------------------------------

        print("\nValidation successful!")
        print("Updating measurement scores...")

        update_measurements(driver, rows)

        # ----------------------------------------------------
        # FINAL VALIDATION
        # ----------------------------------------------------

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

        print("\n" + "=" * 60)
        print("FINAL VALIDATION")
        print("=" * 60)

        print("Total measurements:", total)
        print("Measurements with scores:", with_scores)

        if (
            total != EXPECTED_PILOT_MEASUREMENTS
            or with_scores != EXPECTED_PILOT_MEASUREMENTS
        ):
            raise RuntimeError(
                "Unexpected final measurement counts. "
                "Review the enrichment results."
            )

    print("\nSUCCESS: Measurement enrichment completed!")
    print("Existing graph structure preserved.")


if __name__ == "__main__":
    main()