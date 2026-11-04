// ============================================================
// 01 GRAPH VALIDATION
// Run after import_study2_graph.py and assign_display_ids.py.
// Read-only. Aggregate counts only.
// ============================================================

// Nodes per label
MATCH (n)
RETURN labels(n)[0] AS label, count(*) AS nodes
ORDER BY label;

// Relationships per type
MATCH ()-[r]->()
RETURN type(r) AS relationship, count(*) AS total
ORDER BY relationship;

// Participants by number of recorded visits (expect 3 for Study 2)
MATCH (p:Person)
WITH p, size([(p)-[:HAS_VISIT]->(v:Visit) | v]) AS visits
RETURN visits, count(p) AS participants
ORDER BY visits;

// Clinical events not linked to any visit (should be 0)
MATCH (n)
WHERE (n:Measurement OR n:Observation OR n:Condition)
  AND NOT EXISTS { (:Visit)-->(n) }
RETURN labels(n)[0] AS label, count(*) AS unlinked;

// Participants without a display ID (should be 0)
MATCH (p:Person)
WHERE p.display_id IS NULL
RETURN count(p) AS missing_display_id;

// Real measurement and observation names in the graph
MATCH (e)-[:HAS_CONCEPT]->(c:Concept)
WHERE e:Measurement OR e:Observation OR e:Condition
RETURN labels(e)[0] AS type, c.concept_id AS concept_id,
       c.concept_name AS name, count(e) AS records
ORDER BY type, records DESC;
