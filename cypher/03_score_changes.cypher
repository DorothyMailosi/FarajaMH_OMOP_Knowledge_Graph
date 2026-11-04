// ============================================================
// 03 SCORE CHANGES ACROSS WAVES
// "Increased" / "decreased" describe the recorded score only.
// For symptom scales (e.g. DASS-21, PHQ-9) a higher score means
// more symptoms; check each instrument's direction before calling
// a change "worse" or "better". Read-only.
// ============================================================

// Cohort summary: mean score per measurement per wave (aggregate)
MATCH (v:Visit)-[:HAS_MEASUREMENT]->(m:Measurement)-[:HAS_CONCEPT]->(c:Concept)
WHERE m.value_as_number IS NOT NULL
RETURN
    c.concept_name AS measurement,
    v.visit_sequence AS wave,
    count(DISTINCT v) AS participants_assessed,
    round(avg(m.value_as_number), 1) AS mean_score,
    min(m.value_as_number) AS min_score,
    max(m.value_as_number) AS max_score
ORDER BY measurement, wave;

// Each participant's trajectory per measurement, first to last wave
MATCH (p:Person)-[:HAS_VISIT]->(v:Visit)
      -[:HAS_MEASUREMENT]->(m:Measurement)-[:HAS_CONCEPT]->(c:Concept)
WHERE m.value_as_number IS NOT NULL
WITH p, c.concept_name AS measurement, v.visit_sequence AS wave,
     m.value_as_number AS score
ORDER BY wave
WITH p, measurement, collect(wave) AS waves, collect(score) AS scores
WHERE size(scores) >= 2
RETURN
    p.display_id AS participant,
    measurement,
    waves,
    scores,
    scores[-1] - scores[0] AS change_first_to_last,
    CASE
        WHEN scores[-1] > scores[0] THEN 'Increased'
        WHEN scores[-1] < scores[0] THEN 'Decreased'
        ELSE 'No change'
    END AS direction
ORDER BY participant, measurement;

// Wave-to-wave increases: follows NEXT_VISIT, so it compares each
// visit with the participant's very next visit. This is the query
// that needs window functions and self-joins in SQL.
MATCH (p:Person)-[:HAS_VISIT]->(v1:Visit)-[:NEXT_VISIT]->(v2:Visit),
      (v1)-[:HAS_MEASUREMENT]->(m1:Measurement)-[:HAS_CONCEPT]->(c:Concept),
      (v2)-[:HAS_MEASUREMENT]->(m2:Measurement)-[:HAS_CONCEPT]->(c)
WHERE m2.value_as_number > m1.value_as_number
RETURN
    p.display_id AS participant,
    c.concept_name AS measurement,
    v1.visit_sequence AS from_wave,
    v2.visit_sequence AS to_wave,
    m1.value_as_number AS before,
    m2.value_as_number AS after
ORDER BY participant, measurement, from_wave;

// How many participants had a score increase at each transition
MATCH (p:Person)-[:HAS_VISIT]->(v1:Visit)-[:NEXT_VISIT]->(v2:Visit),
      (v1)-[:HAS_MEASUREMENT]->(m1:Measurement)-[:HAS_CONCEPT]->(c:Concept),
      (v2)-[:HAS_MEASUREMENT]->(m2:Measurement)-[:HAS_CONCEPT]->(c)
WITH c.concept_name AS measurement,
     'Wave ' + toString(v1.visit_sequence) + ' -> ' + toString(v2.visit_sequence) AS transition,
     m2.value_as_number - m1.value_as_number AS delta
RETURN
    measurement,
    transition,
    sum(CASE WHEN delta > 0 THEN 1 ELSE 0 END) AS increased,
    sum(CASE WHEN delta < 0 THEN 1 ELSE 0 END) AS decreased,
    sum(CASE WHEN delta = 0 THEN 1 ELSE 0 END) AS unchanged
ORDER BY measurement, transition;
