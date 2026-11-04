"""
Give every Person a short, stable display ID (P001, P002, ...).

- Existing display IDs are never changed, so P014 stays P014 when
  more participants are imported later.
- New participants are numbered after the highest existing ID,
  in graph_id order (a pseudonym, so the order reveals nothing).
- Display IDs live only in Neo4j and cannot be traced back to the
  OMOP person_id without the pseudonymization secret.

Usage:
    python import_study2_graph.py ...   # first
    python assign_display_ids.py
"""

from neo4j import GraphDatabase

from graph_common import (
    NEO4J_DATABASE,
    NEO4J_URI,
    NEO4J_USER,
    ask_passwords,
)


ASSIGN_QUERY = """
    MATCH (p:Person)
    WHERE p.display_id IS NULL
    WITH p
    ORDER BY p.graph_id
    WITH collect(p) AS people
    UNWIND range(0, size(people) - 1) AS i
    WITH people[i] AS p, $start + i AS number
    SET
        p.display_id = 'P' + right($padding + toString(number), $width),
        p.name = 'P' + right($padding + toString(number), $width)
    RETURN count(p) AS assigned
"""


def main():

    print("=" * 60)
    print("FARAJAMH STUDY 2 - DISPLAY IDS")
    print("=" * 60)

    _, neo4j_password = ask_passwords(need_postgres=False)

    with GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, neo4j_password),
        telemetry_disabled=True
    ) as driver:

        driver.verify_connectivity()

        result, _, _ = driver.execute_query(
            """
            MATCH (p:Person)
            RETURN
                count(p) AS total,
                count(p.display_id) AS with_id,
                max(toInteger(substring(p.display_id, 1))) AS last_number,
                max(size(p.display_id)) - 1 AS existing_width
            """,
            database_=NEO4J_DATABASE
        )

        stats = result[0]
        total = stats["total"]
        last_number = stats["last_number"] or 0

        # Keep the existing width (P014 -> 3 digits) unless the cohort
        # outgrows it.
        width = max(3, stats["existing_width"] or 0, len(str(total)))

        print("Participants in graph:", total)
        print("Already have a display ID:", stats["with_id"])

        driver.execute_query(
            "CREATE CONSTRAINT person_display_id IF NOT EXISTS "
            "FOR (p:Person) REQUIRE p.display_id IS UNIQUE",
            database_=NEO4J_DATABASE
        )

        # Captions in Neo4j Browser use the `name` property. This also
        # covers IDs assigned earlier by hand in Neo4j Browser.
        driver.execute_query(
            """
            MATCH (p:Person)
            WHERE p.display_id IS NOT NULL
            SET p.name = p.display_id
            """,
            database_=NEO4J_DATABASE
        )

        if stats["with_id"] < total:
            result, _, _ = driver.execute_query(
                ASSIGN_QUERY,
                start=last_number + 1,
                padding="0" * width,
                width=width,
                database_=NEO4J_DATABASE
            )

            print("Newly assigned:", result[0]["assigned"])

        result, _, _ = driver.execute_query(
            """
            MATCH (p:Person)
            RETURN
                count(p) AS total,
                count(p.display_id) AS with_id,
                min(p.display_id) AS first_id,
                max(p.display_id) AS last_id
            """,
            database_=NEO4J_DATABASE
        )

        final = result[0]

        print("\nFINAL VALIDATION")
        print("Participants:", final["total"])
        print("With display ID:", final["with_id"])
        print("Range:", final["first_id"], "to", final["last_id"])

        if final["with_id"] != final["total"]:
            raise RuntimeError("Some participants have no display ID.")

    print("\nSUCCESS: Display IDs assigned.")


if __name__ == "__main__":
    main()
