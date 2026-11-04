// ============================================================
// 05 PATHWAY VIEW FOR NEO4J BROWSER (Graph tab)
// Shows one participant's three waves in order, with real names
// as node captions. If Browser still shows hash codes, click the
// node label in the results panel and set Caption to "name".
//
// Screenshots of real participants are participant-level data:
// do not publish them without data-governance approval.
// ============================================================

// Waves in order, with each wave's scores
MATCH visits = (p:Person {display_id: 'P001'})-[:HAS_VISIT]->(v:Visit)
OPTIONAL MATCH next = (v)-[:NEXT_VISIT]->(:Visit)
OPTIONAL MATCH scores = (v)-[:HAS_MEASUREMENT]->(:Measurement)
RETURN visits, next, scores;

// Waves in order, with observations and their recorded categories
MATCH visits = (p:Person {display_id: 'P001'})-[:HAS_VISIT]->(v:Visit)
OPTIONAL MATCH next = (v)-[:NEXT_VISIT]->(:Visit)
OPTIONAL MATCH obs = (v)-[:HAS_OBSERVATION]->(:Observation)
                     -[:HAS_CATEGORY]->(:ObservationCategory)
RETURN visits, next, obs;

// One measurement followed through all waves via NEXT_VISIT
// (replace the concept name with one listed by 01_graph_validation)
MATCH (p:Person {display_id: 'P001'})-[:HAS_VISIT]->(v:Visit)
MATCH (v)-[r:HAS_MEASUREMENT]->(m:Measurement)-[:HAS_CONCEPT]->(c:Concept)
WHERE c.concept_name CONTAINS 'Depression'
OPTIONAL MATCH next = (v)-[:NEXT_VISIT]->(:Visit)
RETURN p, v, r, m, next;
