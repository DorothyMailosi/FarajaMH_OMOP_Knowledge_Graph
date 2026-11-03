import os
import getpass

import psycopg
from neo4j import GraphDatabase


# ============================================================
# 1. DATABASE CONFIGURATION
# ============================================================

POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "postgres",
    "user": "postgres",
}

NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_DATABASE = "neo4j"


# ============================================================
# 2. CONNECT TO POSTGRESQL
# ============================================================

def test_postgresql_connection(password):

    print("\nConnecting to PostgreSQL...")

    try:
        with psycopg.connect(
            **POSTGRES_CONFIG,
            password=password,
            connect_timeout=10,
            options="-c default_transaction_read_only=on"
        ) as conn:

            print("SUCCESS: Connected to PostgreSQL!")

            with conn.cursor() as cursor:

                # Check Study 2 participants
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM study_2_cdm_r.person;
                """)

                person_count = cursor.fetchone()[0]

                print(
                    f"Study 2 participants: {person_count:,}"
                )

                # Check Study 2 visits
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM study_2_cdm_r.visit_occurrence;
                """)

                visit_count = cursor.fetchone()[0]

                print(
                    f"Study 2 visits: {visit_count:,}"
                )

                # Check vocabulary
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM omop_5_4.concept;
                """)

                concept_count = cursor.fetchone()[0]

                print(
                    f"OMOP vocabulary concepts: {concept_count:,}"
                )

        return True

    except Exception as error:

        print("PostgreSQL connection failed.")
        print(f"Error: {error}")

        return False


# ============================================================
# 3. CONNECT TO NEO4J
# ============================================================

def test_neo4j_connection(password):

    print("\nConnecting to Neo4j...")

    try:
        with GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, password)
        ) as driver:

            driver.verify_connectivity()

            print("SUCCESS: Connected to Neo4j!")

            with driver.session(
                database=NEO4J_DATABASE
            ) as session:

                result = session.run("""
                    RETURN
                        'FarajaMH Study 2' AS project,
                        'Connected successfully' AS status
                """)

                record = result.single()

                print("Project:", record["project"])
                print("Status:", record["status"])

        return True

    except Exception as error:

        print("Neo4j connection failed.")
        print(f"Error: {error}")

        return False


# ============================================================
# 4. MAIN
# ============================================================

if __name__ == "__main__":

    print("=" * 55)
    print("FARAJAMH STUDY 2 - DATABASE CONNECTION TEST")
    print("=" * 55)

    postgres_password = getpass.getpass(
        "Enter PostgreSQL password: "
    )

    neo4j_password = getpass.getpass(
        "Enter Neo4j password: "
    )

    postgres_ok = test_postgresql_connection(
        postgres_password
    )

    neo4j_ok = test_neo4j_connection(
        neo4j_password
    )

    print("\n" + "=" * 55)
    print("FINAL CONNECTION STATUS")
    print("=" * 55)

    print(
        "PostgreSQL:",
        "CONNECTED" if postgres_ok else "FAILED"
    )

    print(
        "Neo4j:",
        "CONNECTED" if neo4j_ok else "FAILED"
    )