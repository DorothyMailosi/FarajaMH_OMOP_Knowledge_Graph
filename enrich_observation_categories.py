import getpass
import hashlib
import hmac
import re
from collections import Counter

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

EXPECTED_OBSERVATIONS = 450

# The six observation concepts identified in the pilot.
ALLOWED_CONCEPT_IDS = {
    4075500,    # Household size
    4053609,    # Marital status
    4060186,    # Gravida
    4264419,    # Parity
    4264823,    # Birth outcome
    43054892,   # Delivery method
}

# Exact source labels confirmed for these observations.
KNOWN_CATEGORIES = {
    4053609: {
        "Married",
        "Single/divorced/widowed",
    },
    4264823: {
        "Live Birth",
        "Stillbirth/Fetal anomaly/IUFD",
    },
    43054892: {
        "Cesarean delivery",
        "Spontaneous vaginal delivery",
    },
}


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
# POSTGRESQL EXTRACTION
# ============================================================

def extract_observations(conn):

    query = """
        SELECT
            observation_id,
            person_id,
            visit_occurrence_id,
            observation_concept_id,
            TRIM(value_as_string) AS category
        FROM study_2_cdm_r.observation
        WHERE observation_concept_id = ANY(%s)
        ORDER BY observation_id
    """

    with conn.cursor() as cursor:
        cursor.execute(query, (list(ALLOWED_CONCEPT_IDS),))
        return cursor.fetchall()


# ============================================================
# PREPARE ROWS
# ============================================================

def prepare_rows(records, secret):

    rows = []

    for observation_id, person_id, visit_id, concept_id, category in records:

        if concept_id not in ALLOWED_CONCEPT_IDS:
            raise ValueError("Unexpected observation concept.")

        if not category:
            raise ValueError(
                "Missing category for an observation. "
                "No graph updates will be made."
            )

        if len(category) > 100:
            raise ValueError("Category exceeds the approved length.")

        # Reject control characters and unexpected punctuation.
        if not re.fullmatch(
            r"[A-Za-z0-9 /(),.+\-–]+",
            category
        ):
            raise ValueError(
                "Unexpected category characters. "
                "Review the source values locally."
            )

        if concept_id in KNOWN_CATEGORIES:
            if category not in KNOWN_CATEGORIES[concept_id]:
                raise ValueError(
                    "An unexpected category was found for "
                    f"concept {concept_id}."
                )

        category_id = f"{concept_id}:{category}"

        rows.append({
            "graph_id": pseudonym(
                secret,
                "Observation",
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
            "category_id": category_id,
            "category_name": category,
        })

    return rows


# ============================================================
# NEO4J QUERIES
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


UPDATE_QUERY = """
    UNWIND $rows AS row

    MATCH (o:Observation {graph_id: row.graph_id})

    MERGE (cat:ObservationCategory {
        category_id: row.category_id
    })

    SET
        cat.category_name = row.category_name,
        cat.observation_concept_id = row.concept_id

    MERGE (o)-[:HAS_CATEGORY]->(cat)
"""


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("FARAJAMH STUDY 2 - CATEGORY ENRICHMENT")
    print("=" * 60)

    pg_password = getpass.getpass("PostgreSQL password: ")
    neo4j_password = getpass.getpass("Neo4j password: ")

    secret = getpass.getpass(
        "Enter the SAME pseudonymization secret: "
    )

    if len(secret) < 24:
        raise ValueError("Secret must contain at least 24 characters.")

    # --------------------------------------------------------
    # EXTRACT SOURCE DATA
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
    # REVIEW DISTINCT CATEGORIES
    # --------------------------------------------------------

    category_counts = Counter(
        (row["concept_id"], row["category_name"])
        for row in rows
    )

    print("\nDISTINCT SOURCE CATEGORIES")
    print("-" * 60)

    for (concept_id, category), frequency in sorted(
        category_counts.items()
    ):
        # Only show category labels with adequate aggregate frequency.
        display_category = (
            category if frequency >= 5 else "[rare category]"
        )
        print(concept_id, "|", display_category, "|", frequency)

    print("\nDistinct categories:", len(category_counts))

    # --------------------------------------------------------
    # CONNECT TO NEO4J
    # --------------------------------------------------------

    with GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, neo4j_password),
        telemetry_disabled=True
    ) as driver:

        driver.verify_connectivity()

        with driver.session(database=NEO4J_DATABASE) as session:

            existing_count = session.run(
                """
                MATCH (o:Observation)
                RETURN count(o) AS total
                """
            ).single()["total"]

            print("\nExisting Neo4j observations:", existing_count)

            if existing_count != EXPECTED_OBSERVATIONS:
                raise RuntimeError(
                    "Unexpected observation count. "
                    "No changes made."
                )

            # ------------------------------------------------
            # VALIDATE SOURCE-TO-GRAPH MATCHES
            # ------------------------------------------------

            print("\nValidating observation relationships...")

            matched_count = session.run(
                VALIDATION_QUERY,
                rows=rows
            ).single()["matched"]

            print("Validated observation matches:", matched_count)

            if matched_count != existing_count:
                raise RuntimeError(
                    "Validation failed. No graph changes made. "
                    "Check source IDs, pseudonymization and relationships."
                )

            # ------------------------------------------------
            # CHECK EXISTING CATEGORY RELATIONSHIPS
            # ------------------------------------------------

            existing_links = session.run(
                """
                MATCH (:Observation)-[r:HAS_CATEGORY]->()
                RETURN count(r) AS total
                """
            ).single()["total"]

            if existing_links != 0:
                raise RuntimeError(
                    "Category relationships already exist. "
                    "Review the graph before rerunning this import."
                )

            # ------------------------------------------------
            # MANUAL APPROVAL
            # ------------------------------------------------

            print("\nReview the categories above.")
            print("Proceed only if they are approved for this graph.")

            confirmation = input(
                "Type APPROVE to create category relationships: "
            ).strip()

            if confirmation != "APPROVE":
                print("Cancelled. No graph changes made.")
                return

            # ------------------------------------------------
            # TRANSACTIONAL UPDATE
            # ------------------------------------------------

            print("\nCreating category nodes and relationships...")

            with session.begin_transaction() as tx:

                tx.run(
                    UPDATE_QUERY,
                    rows=rows
                ).consume()

                result = tx.run(
                    """
                    MATCH (o:Observation)

                    OPTIONAL MATCH
                        (o)-[:HAS_CATEGORY]->(cat:ObservationCategory)

                    RETURN
                        count(DISTINCT o) AS observations,
                        count(cat) AS category_links,
                        count(DISTINCT cat) AS category_nodes
                    """
                ).single()

                observations = result["observations"]
                links = result["category_links"]
                categories = result["category_nodes"]

                print("\nFINAL VALIDATION")
                print("Observations:", observations)
                print("Category relationships:", links)
                print("Distinct category nodes:", categories)

                if (
                    observations != EXPECTED_OBSERVATIONS
                    or links != EXPECTED_OBSERVATIONS
                ):
                    raise RuntimeError(
                        "Validation failed. Transaction rolled back."
                    )

                tx.commit()

    print("\nSUCCESS: Category enrichment completed!")


if __name__ == "__main__":
    main()