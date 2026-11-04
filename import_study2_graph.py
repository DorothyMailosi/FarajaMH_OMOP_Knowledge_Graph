"""
Build (or extend) the FarajaMH Study 2 knowledge graph from OMOP.

Creates Person, Visit, Measurement, Observation, ObservationCategory,
Condition and Concept nodes, links them into a longitudinal pathway
(HAS_VISIT, NEXT_VISIT, HAS_MEASUREMENT, HAS_OBSERVATION, HAS_CONDITION,
HAS_CONCEPT, HAS_CATEGORY) and stores real OMOP concept names on nodes.

Every write uses MERGE on the same pseudonymized graph_id as the
original pilot import, so re-running this script against the existing
25-participant pilot updates those nodes instead of duplicating them.

Usage:
    python import_study2_graph.py --dry-run              # counts only
    python import_study2_graph.py --cohort existing      # rebuild pilot
    python import_study2_graph.py --cohort all           # full Study 2
    python import_study2_graph.py --cohort all --limit 100
"""

import argparse
import re
from collections import Counter

import psycopg
from neo4j import GraphDatabase

from graph_common import (
    CDM_SCHEMA,
    NEO4J_DATABASE,
    NEO4J_URI,
    NEO4J_USER,
    PG_CONFIG,
    VOCAB_SCHEMA,
    ask_passwords,
    ask_secret,
    pseudonym,
    run_in_batches,
)


# Short categorical labels only. Anything else (free text, phone
# numbers, ID numbers) is never written to the graph. Names cannot be
# detected by pattern, so categories are also reviewed before APPROVE.
SAFE_LABEL = re.compile(r"[A-Za-z0-9 /(),.+\-–]{1,60}")
MAX_DIGITS = 4


def safe_label(value):
    if value is None:
        return None

    value = value.strip()

    if sum(ch.isdigit() for ch in value) > MAX_DIGITS:
        return None

    return value if SAFE_LABEL.fullmatch(value) else None


def format_value(value):
    if value is None:
        return None

    value = float(value)

    return str(int(value)) if value.is_integer() else f"{value:g}"


# ============================================================
# POSTGRESQL EXTRACTION
# ============================================================

def existing_tables(cursor):
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s
        """,
        (CDM_SCHEMA,)
    )

    return {name for (name,) in cursor.fetchall()}


def extract_person_ids(cursor):
    cursor.execute(
        f"SELECT person_id FROM {CDM_SCHEMA}.person ORDER BY person_id"
    )

    return [person_id for (person_id,) in cursor.fetchall()]


def extract_visits(cursor, person_ids):
    # Wave = order of the participant's visits by date.
    # Only the interval since the first visit is kept, not real dates.
    cursor.execute(
        f"""
        SELECT
            person_id,
            visit_occurrence_id,
            ROW_NUMBER() OVER (
                PARTITION BY person_id
                ORDER BY visit_start_date, visit_occurrence_id
            ) AS visit_sequence,
            visit_start_date - MIN(visit_start_date) OVER (
                PARTITION BY person_id
            ) AS days_since_first_visit
        FROM {CDM_SCHEMA}.visit_occurrence
        WHERE person_id = ANY(%s)
        ORDER BY person_id, visit_sequence
        """,
        (person_ids,)
    )

    return cursor.fetchall()


def extract_measurements(cursor, person_ids):
    cursor.execute(
        f"""
        SELECT
            measurement_id,
            person_id,
            visit_occurrence_id,
            measurement_concept_id,
            value_as_number,
            measurement_source_value
        FROM {CDM_SCHEMA}.measurement
        WHERE person_id = ANY(%s)
        ORDER BY measurement_id
        """,
        (person_ids,)
    )

    return cursor.fetchall()


def extract_observations(cursor, person_ids):
    cursor.execute(
        f"""
        SELECT
            observation_id,
            person_id,
            visit_occurrence_id,
            observation_concept_id,
            value_as_number,
            value_as_string,
            value_as_concept_id
        FROM {CDM_SCHEMA}.observation
        WHERE person_id = ANY(%s)
        ORDER BY observation_id
        """,
        (person_ids,)
    )

    return cursor.fetchall()


def extract_conditions(cursor, person_ids):
    cursor.execute(
        f"""
        SELECT
            condition_occurrence_id,
            person_id,
            visit_occurrence_id,
            condition_concept_id
        FROM {CDM_SCHEMA}.condition_occurrence
        WHERE person_id = ANY(%s)
        ORDER BY condition_occurrence_id
        """,
        (person_ids,)
    )

    return cursor.fetchall()


def extract_concepts(cursor, concept_ids):
    cursor.execute(
        f"""
        SELECT
            concept_id,
            concept_name,
            domain_id,
            vocabulary_id,
            concept_code
        FROM {VOCAB_SCHEMA}.concept
        WHERE concept_id = ANY(%s)
        """,
        (list(concept_ids),)
    )

    return {row[0]: row for row in cursor.fetchall()}


# ============================================================
# PREPARE GRAPH ROWS
# ============================================================

def concept_name(concepts, concept_id):
    if concept_id in concepts:
        return concepts[concept_id][1]

    return f"Concept {concept_id} (not in vocabulary)"


def prepare_concepts(concepts, concept_ids):
    rows = []

    for concept_id in sorted(concept_ids):
        _, name, domain, vocabulary, code = concepts.get(
            concept_id, (concept_id, None, None, None, None)
        )

        rows.append({
            "concept_id": concept_id,
            "concept_name": name or concept_name(concepts, concept_id),
            "domain_id": domain,
            "vocabulary_id": vocabulary,
            "concept_code": code,
        })

    return rows


def prepare_visits(records, secret):
    return [
        {
            "graph_id": pseudonym(secret, "visit", visit_id),
            "person_graph_id": pseudonym(secret, "person", person_id),
            "visit_sequence": sequence,
            "days_since_first_visit": days,
        }
        for person_id, visit_id, sequence, days in records
    ]


def visit_graph_id(secret, visit_id):
    return (
        pseudonym(secret, "visit", visit_id)
        if visit_id is not None
        else None
    )


def prepare_measurements(records, concepts, secret):
    rows = []

    for (
        measurement_id, person_id, visit_id,
        concept_id, value, source_value
    ) in records:

        name = concept_name(concepts, concept_id)

        # Unmapped measurements (concept 0) fall back to the source
        # variable name so the graph still shows what was measured.
        if concept_id == 0 and safe_label(source_value):
            name = safe_label(source_value)

        shown = format_value(value)

        rows.append({
            "graph_id": pseudonym(secret, "Measurement", measurement_id),
            "person_graph_id": pseudonym(secret, "person", person_id),
            "visit_graph_id": visit_graph_id(secret, visit_id),
            "concept_id": concept_id,
            "measurement_name": name,
            "value_as_number": float(value) if value is not None else None,
            "name": f"{name}: {shown}" if shown is not None else name,
        })

    return rows


def prepare_observations(records, concepts, secret):
    rows = []
    rejected_strings = 0

    for (
        observation_id, person_id, visit_id, concept_id,
        number, string, value_concept_id
    ) in records:

        category = safe_label(string)

        if string and string.strip() and category is None:
            rejected_strings += 1

        value_concept_id = (
            int(value_concept_id)
            if value_concept_id not in (None, 0)
            else None
        )

        shown = (
            category
            or format_value(number)
            or (
                concept_name(concepts, value_concept_id)
                if value_concept_id else None
            )
        )

        name = concept_name(concepts, concept_id)

        rows.append({
            "graph_id": pseudonym(secret, "Observation", observation_id),
            "person_graph_id": pseudonym(secret, "person", person_id),
            "visit_graph_id": visit_graph_id(secret, visit_id),
            "concept_id": concept_id,
            "observation_name": name,
            "value_as_number": float(number) if number is not None else None,
            "value_as_concept_id": value_concept_id,
            # Same category_id format as enrich_observation_categories.py
            "category_id": f"{concept_id}:{category}" if category else None,
            "category_name": category,
            "name": f"{name}: {shown}" if shown else name,
        })

    return rows, rejected_strings


def prepare_conditions(records, concepts, secret):
    return [
        {
            "graph_id": pseudonym(secret, "Condition", condition_id),
            "person_graph_id": pseudonym(secret, "person", person_id),
            "visit_graph_id": visit_graph_id(secret, visit_id),
            "concept_id": concept_id,
            "name": concept_name(concepts, concept_id),
        }
        for condition_id, person_id, visit_id, concept_id in records
    ]


# ============================================================
# NEO4J QUERIES
# ============================================================

CONSTRAINTS = [
    "CREATE CONSTRAINT person_graph_id IF NOT EXISTS "
    "FOR (n:Person) REQUIRE n.graph_id IS UNIQUE",
    "CREATE CONSTRAINT visit_graph_id IF NOT EXISTS "
    "FOR (n:Visit) REQUIRE n.graph_id IS UNIQUE",
    "CREATE CONSTRAINT measurement_graph_id IF NOT EXISTS "
    "FOR (n:Measurement) REQUIRE n.graph_id IS UNIQUE",
    "CREATE CONSTRAINT observation_graph_id IF NOT EXISTS "
    "FOR (n:Observation) REQUIRE n.graph_id IS UNIQUE",
    "CREATE CONSTRAINT condition_graph_id IF NOT EXISTS "
    "FOR (n:Condition) REQUIRE n.graph_id IS UNIQUE",
    "CREATE CONSTRAINT concept_id IF NOT EXISTS "
    "FOR (n:Concept) REQUIRE n.concept_id IS UNIQUE",
    "CREATE CONSTRAINT category_id IF NOT EXISTS "
    "FOR (n:ObservationCategory) REQUIRE n.category_id IS UNIQUE",
]

CONCEPT_QUERY = """
    UNWIND $rows AS row
    MERGE (c:Concept {concept_id: row.concept_id})
    SET
        c.concept_name = row.concept_name,
        c.name = row.concept_name,
        c.domain_id = row.domain_id,
        c.vocabulary_id = row.vocabulary_id,
        c.concept_code = row.concept_code
"""

PERSON_QUERY = """
    UNWIND $rows AS row
    MERGE (p:Person {graph_id: row.graph_id})
    SET p.study = $study
"""

VISIT_QUERY = """
    UNWIND $rows AS row
    MATCH (p:Person {graph_id: row.person_graph_id})
    MERGE (v:Visit {graph_id: row.graph_id})
    SET
        v.visit_sequence = row.visit_sequence,
        v.wave = row.visit_sequence,
        v.days_since_first_visit = row.days_since_first_visit,
        v.name = 'Wave ' + toString(row.visit_sequence)
    MERGE (p)-[:HAS_VISIT]->(v)
"""

NEXT_VISIT_QUERY = """
    UNWIND $rows AS row
    MATCH (p:Person {graph_id: row.graph_id})-[:HAS_VISIT]->(v1:Visit)
    MATCH (p)-[:HAS_VISIT]->(v2:Visit)
    WHERE v2.visit_sequence = v1.visit_sequence + 1
    MERGE (v1)-[:NEXT_VISIT]->(v2)
"""

MEASUREMENT_QUERY = """
    UNWIND $rows AS row
    MATCH (p:Person {graph_id: row.person_graph_id})
    MATCH (c:Concept {concept_id: row.concept_id})
    MERGE (m:Measurement {graph_id: row.graph_id})
    SET
        m.concept_id = row.concept_id,
        m.measurement_name = row.measurement_name,
        m.value_as_number = row.value_as_number,
        m.name = row.name
    MERGE (p)-[:HAS_MEASUREMENT]->(m)
    MERGE (m)-[:HAS_CONCEPT]->(c)
    WITH m, row
    WHERE row.visit_graph_id IS NOT NULL
    MATCH (v:Visit {graph_id: row.visit_graph_id})
    MERGE (v)-[:HAS_MEASUREMENT]->(m)
"""

OBSERVATION_QUERY = """
    UNWIND $rows AS row
    MATCH (p:Person {graph_id: row.person_graph_id})
    MATCH (c:Concept {concept_id: row.concept_id})
    MERGE (o:Observation {graph_id: row.graph_id})
    SET
        o.concept_id = row.concept_id,
        o.observation_name = row.observation_name,
        o.value_as_number = row.value_as_number,
        o.value_as_concept_id = row.value_as_concept_id,
        o.name = row.name
    MERGE (p)-[:HAS_OBSERVATION]->(o)
    MERGE (o)-[:HAS_CONCEPT]->(c)
    WITH o, row
    WHERE row.visit_graph_id IS NOT NULL
    MATCH (v:Visit {graph_id: row.visit_graph_id})
    MERGE (v)-[:HAS_OBSERVATION]->(o)
"""

CATEGORY_QUERY = """
    UNWIND $rows AS row
    MATCH (o:Observation {graph_id: row.graph_id})
    MERGE (cat:ObservationCategory {category_id: row.category_id})
    SET
        cat.category_name = row.category_name,
        cat.name = row.category_name,
        cat.observation_concept_id = row.concept_id
    MERGE (o)-[:HAS_CATEGORY]->(cat)
"""

CONDITION_QUERY = """
    UNWIND $rows AS row
    MATCH (p:Person {graph_id: row.person_graph_id})
    MATCH (c:Concept {concept_id: row.concept_id})
    MERGE (d:Condition {graph_id: row.graph_id})
    SET
        d.concept_id = row.concept_id,
        d.name = row.name
    MERGE (p)-[:HAS_CONDITION]->(d)
    MERGE (d)-[:HAS_CONCEPT]->(c)
    WITH d, row
    WHERE row.visit_graph_id IS NOT NULL
    MATCH (v:Visit {graph_id: row.visit_graph_id})
    MERGE (v)-[:HAS_CONDITION]->(d)
"""

GRAPH_COUNTS_QUERY = """
    UNWIND $ids AS gid
    MATCH (p:Person {graph_id: gid})
    RETURN
        count(p) AS persons,
        sum(size([(p)-[:HAS_VISIT]->(v:Visit) | v])) AS visits,
        sum(size([(p)-[:HAS_MEASUREMENT]->(m:Measurement) | m]))
            AS measurements,
        sum(size([(p)-[:HAS_OBSERVATION]->(o:Observation) | o]))
            AS observations,
        sum(size([(p)-[:HAS_CONDITION]->(d:Condition) | d]))
            AS conditions
"""


# ============================================================
# COHORT SELECTION
# ============================================================

def select_cohort(driver, person_ids, secret, cohort, limit):
    if cohort == "existing":
        # Hash every source person and keep those already in the graph.
        # This recovers the pilot cohort without storing person_id.
        by_graph_id = {
            pseudonym(secret, "person", pid): pid for pid in person_ids
        }

        records, _, _ = driver.execute_query(
            "MATCH (p:Person) RETURN p.graph_id AS graph_id",
            database_=NEO4J_DATABASE
        )

        in_graph = {r["graph_id"] for r in records}
        person_ids = sorted(
            pid for gid, pid in by_graph_id.items() if gid in in_graph
        )

        if len(person_ids) != len(in_graph):
            raise RuntimeError(
                f"{len(in_graph)} Person nodes in Neo4j but only "
                f"{len(person_ids)} match source participants. Check the "
                "pseudonymization secret. No changes made."
            )

    if limit:
        person_ids = person_ids[:limit]

    return person_ids


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument(
        "--cohort", choices=["existing", "all"], default="existing",
        help="existing = participants already in Neo4j (the pilot); "
             "all = every participant in the OMOP schema"
    )
    parser.add_argument(
        "--limit", type=int,
        help="Only import the first N participants (by person_id)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Extract and report counts without writing to Neo4j"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("FARAJAMH STUDY 2 - KNOWLEDGE GRAPH IMPORT")
    print("=" * 60)

    pg_password, neo4j_password = ask_passwords()
    secret = ask_secret()

    with GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, neo4j_password),
        telemetry_disabled=True
    ) as driver:

        driver.verify_connectivity()

        # ----------------------------------------------------
        # EXTRACT SOURCE DATA (read-only)
        # ----------------------------------------------------

        print("\nConnecting to PostgreSQL...")

        with psycopg.connect(
            **PG_CONFIG,
            password=pg_password,
            options="-c default_transaction_read_only=on"
        ) as conn, conn.cursor() as cursor:

            tables = existing_tables(cursor)

            person_ids = select_cohort(
                driver, extract_person_ids(cursor),
                secret, args.cohort, args.limit
            )

            if not person_ids:
                raise RuntimeError("No participants selected.")

            visits = extract_visits(cursor, person_ids)
            measurements = extract_measurements(cursor, person_ids)
            observations = extract_observations(cursor, person_ids)

            if "condition_occurrence" in tables:
                conditions = extract_conditions(cursor, person_ids)
            else:
                print("No condition_occurrence table - skipping conditions.")
                conditions = []

            concept_ids = (
                {r[3] for r in measurements}
                | {r[3] for r in observations}
                | {r[6] for r in observations if r[6] not in (None, 0)}
                | {r[3] for r in conditions}
            )
            concepts = extract_concepts(cursor, concept_ids)

        # ----------------------------------------------------
        # PREPARE ROWS
        # ----------------------------------------------------

        person_rows = [
            {"graph_id": pseudonym(secret, "person", pid)}
            for pid in person_ids
        ]
        concept_rows = prepare_concepts(concepts, concept_ids)
        visit_rows = prepare_visits(visits, secret)
        measurement_rows = prepare_measurements(measurements, concepts, secret)
        observation_rows, rejected = prepare_observations(
            observations, concepts, secret
        )
        category_rows = [r for r in observation_rows if r["category_id"]]
        condition_rows = prepare_conditions(conditions, concepts, secret)

        expected = {
            "persons": len(person_rows),
            "visits": len(visit_rows),
            "measurements": len(measurement_rows),
            "observations": len(observation_rows),
            "conditions": len(condition_rows),
        }

        print("\nSOURCE COUNTS (selected cohort)")
        print("-" * 60)
        for label, total in expected.items():
            print(f"{label:<14}{total:>8,}")
        print(f"{'concepts':<14}{len(concept_rows):>8,}")

        waves = Counter(r["visit_sequence"] for r in visit_rows)
        print("\nParticipants with a recorded visit at each wave:")
        for wave in sorted(waves):
            print(f"  Wave {wave}: {waves[wave]:,}")

        print("\nMeasurement names that will appear in the graph:")
        for name, total in Counter(
            r["measurement_name"] for r in measurement_rows
        ).most_common():
            print(f"  {total:>6,}  {name}")

        print("\nObservation names that will appear in the graph:")
        for name, total in Counter(
            r["observation_name"] for r in observation_rows
        ).most_common():
            print(f"  {total:>6,}  {name}")

        print("\nObservation categories (review before approving):")
        for (name, category), total in sorted(Counter(
            (r["observation_name"], r["category_name"])
            for r in category_rows
        ).items()):
            # Only show labels with adequate aggregate frequency.
            shown = category if total >= 5 else "[rare category]"
            print(f"  {total:>6,}  {name} | {shown}")

        if rejected:
            print(
                f"\n{rejected:,} observation text values were not short "
                "categorical labels and will NOT be written to the graph."
            )

        unmapped = concept_ids - set(concepts)
        if unmapped:
            print(f"\n{len(unmapped)} concept IDs not found in "
                  f"{VOCAB_SCHEMA}.concept: {sorted(unmapped)}")

        if args.dry_run:
            print("\nDry run complete. No changes made.")
            return

        confirmation = input(
            "\nType APPROVE to write this cohort to Neo4j: "
        ).strip()

        if confirmation != "APPROVE":
            print("Cancelled. No graph changes made.")
            return

        # ----------------------------------------------------
        # WRITE GRAPH
        # ----------------------------------------------------

        print("\nCreating constraints...")
        for statement in CONSTRAINTS:
            driver.execute_query(statement, database_=NEO4J_DATABASE)

        steps = [
            ("concepts", CONCEPT_QUERY, concept_rows),
            ("persons", PERSON_QUERY, person_rows),
            ("visits", VISIT_QUERY, visit_rows),
            ("visit order", NEXT_VISIT_QUERY, person_rows),
            ("measurements", MEASUREMENT_QUERY, measurement_rows),
            ("observations", OBSERVATION_QUERY, observation_rows),
            ("categories", CATEGORY_QUERY, category_rows),
            ("conditions", CONDITION_QUERY, condition_rows),
        ]

        for label, query, rows in steps:
            print(f"Writing {label}: {len(rows):,}")
            run_in_batches(driver, query, rows, study="Study 2")

        # ----------------------------------------------------
        # FINAL VALIDATION
        # ----------------------------------------------------

        result, _, _ = driver.execute_query(
            GRAPH_COUNTS_QUERY,
            ids=[r["graph_id"] for r in person_rows],
            database_=NEO4J_DATABASE
        )

        actual = dict(result[0])

        print("\n" + "=" * 60)
        print("FINAL VALIDATION (source vs graph)")
        print("=" * 60)

        mismatches = []
        for label, total in expected.items():
            ok = actual[label] == total
            print(f"{label:<14}{total:>8,}{actual[label]:>8,}  "
                  f"{'OK' if ok else 'MISMATCH'}")
            if not ok:
                mismatches.append(label)

        if mismatches:
            raise RuntimeError(
                "Graph counts do not match the source for: "
                + ", ".join(mismatches)
            )

    print("\nSUCCESS: Graph import completed.")
    print("Next: python assign_display_ids.py")


if __name__ == "__main__":
    main()
