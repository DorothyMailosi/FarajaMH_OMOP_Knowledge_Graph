// ============================================================
// 02 PARTICIPANT PATHWAY: one row per participant per wave
// Real OMOP concept names with recorded scores and values.
// Read-only. Output is participant-level: keep it inside the
// approved environment; do not publish real rows.
// ============================================================

MATCH (p:Person)-[:HAS_VISIT]->(v:Visit)
RETURN
    p.display_id AS participant,
    v.visit_sequence AS wave,
    v.days_since_first_visit AS days_since_wave_1,
    [(v)-[:HAS_MEASUREMENT]->(m:Measurement)-[:HAS_CONCEPT]->(c:Concept)
        | c.concept_name + ': ' + coalesce(toString(m.value_as_number), 'no value')
    ] AS measurements,
    [(v)-[:HAS_OBSERVATION]->(o:Observation)-[:HAS_CONCEPT]->(c:Concept)
        | c.concept_name + ': ' + coalesce(
            head([(o)-[:HAS_CATEGORY]->(cat:ObservationCategory) | cat.category_name]),
            toString(o.value_as_number),
            'no value')
    ] AS observations,
    [(v)-[:HAS_CONDITION]->(d:Condition)-[:HAS_CONCEPT]->(c:Concept)
        | c.concept_name
    ] AS conditions
ORDER BY participant, wave;

// Same pathway for a single participant
MATCH (p:Person {display_id: 'P001'})-[:HAS_VISIT]->(v:Visit)
      -[:HAS_MEASUREMENT]->(m:Measurement)-[:HAS_CONCEPT]->(c:Concept)
RETURN v.visit_sequence AS wave, c.concept_name AS measurement,
       m.value_as_number AS score
ORDER BY measurement, wave;
