import getpass
import hashlib
import hmac
import os


# ============================================================
# CONFIGURATION
# Defaults match the original pilot scripts. Override with
# environment variables when running at another site.
# ============================================================

PG_CONFIG = {
    "host": os.environ.get("FARAJAMH_PG_HOST", "localhost"),
    "port": int(os.environ.get("FARAJAMH_PG_PORT", "5433")),
    "dbname": os.environ.get("FARAJAMH_PG_DB", "postgres"),
    "user": os.environ.get("FARAJAMH_PG_USER", "postgres"),
}

CDM_SCHEMA = os.environ.get("FARAJAMH_CDM_SCHEMA", "study_2_cdm_r")
VOCAB_SCHEMA = os.environ.get("FARAJAMH_VOCAB_SCHEMA", "omop_5_4")

NEO4J_URI = os.environ.get("FARAJAMH_NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.environ.get("FARAJAMH_NEO4J_USER", "neo4j")
NEO4J_DATABASE = os.environ.get("FARAJAMH_NEO4J_DATABASE", "neo4j")

BATCH_SIZE = 500


# ============================================================
# PSEUDONYMIZATION
# IMPORTANT: record_type spelling must match the original import
# ("person", "visit", "Measurement", "Observation"), otherwise the
# same participant receives a different graph_id.
# ============================================================

def pseudonym(secret, record_type, original_id):
    message = f"{record_type}:{original_id}".encode("utf-8")

    return hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256
    ).hexdigest()


# ============================================================
# CREDENTIAL PROMPTS
# ============================================================

def ask_passwords(need_postgres=True):
    pg_password = (
        getpass.getpass("PostgreSQL password: ")
        if need_postgres else None
    )
    neo4j_password = getpass.getpass("Neo4j password: ")

    return pg_password, neo4j_password


def ask_secret():
    secret = getpass.getpass(
        "Enter the SAME pseudonymization secret used during import: "
    )

    if len(secret) < 24:
        raise ValueError(
            "The pseudonymization secret must contain at least 24 characters."
        )

    return secret


# ============================================================
# BATCHED WRITES
# ============================================================

def run_in_batches(driver, query, rows, **params):
    for start in range(0, len(rows), BATCH_SIZE):
        driver.execute_query(
            query,
            rows=rows[start:start + BATCH_SIZE],
            database_=NEO4J_DATABASE,
            **params
        )
