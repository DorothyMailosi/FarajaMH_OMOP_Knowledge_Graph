// ============================================================
// 06 FIGURES FOR THE README
// Aggregate results only. Copy the Table output into
// figures/make_figures.py and run it to redraw the charts.
// Get data-governance approval before publishing new numbers.
// ============================================================

// Chart 1: mean score per measurement per wave
MATCH (v:Visit)-[:HAS_MEASUREMENT]->(m:Measurement)-[:HAS_CONCEPT]->(c:Concept)
WHERE m.value_as_number IS NOT NULL
WITH
    CASE
        WHEN c.concept_name CONTAINS 'depression score' THEN 'DASS Depression'
        WHEN c.concept_name CONTAINS 'anxiety score'    THEN 'DASS Anxiety'
        WHEN c.concept_name CONTAINS 'stress score'     THEN 'DASS Stress'
        WHEN c.concept_name STARTS WITH 'PCL-5'         THEN 'PCL-5'
        ELSE c.concept_name
    END AS measure,
    v.visit_sequence AS wave,
    v, m
RETURN
    measure,
    wave,
    count(DISTINCT v) AS participants,
    round(avg(m.value_as_number), 1) AS mean_score,
    round(stDev(m.value_as_number), 1) AS sd
ORDER BY measure, wave;

// Chart 2: participants whose score decreased between consecutive waves.
// Only the "decreased" count is published: when increased, decreased and
// unchanged are all shown, a suppressed cell can be recovered by
// subtracting the others from the total.
MATCH (p:Person)-[:HAS_VISIT]->(v1:Visit)-[:NEXT_VISIT]->(v2:Visit),
      (v1)-[:HAS_MEASUREMENT]->(m1:Measurement)-[:HAS_CONCEPT]->(c:Concept),
      (v2)-[:HAS_MEASUREMENT]->(m2:Measurement)-[:HAS_CONCEPT]->(c)
WHERE m1.value_as_number IS NOT NULL AND m2.value_as_number IS NOT NULL
WITH
    CASE
        WHEN c.concept_name CONTAINS 'depression score' THEN 'DASS Depression'
        WHEN c.concept_name CONTAINS 'anxiety score'    THEN 'DASS Anxiety'
        WHEN c.concept_name CONTAINS 'stress score'     THEN 'DASS Stress'
        WHEN c.concept_name STARTS WITH 'PCL-5'         THEN 'PCL-5'
        ELSE c.concept_name
    END AS measure,
    'Wave ' + toString(v1.visit_sequence) + ' to ' + toString(v2.visit_sequence) AS transition,
    m2.value_as_number < m1.value_as_number AS decreased
WITH measure, transition, sum(CASE WHEN decreased THEN 1 ELSE 0 END) AS n
RETURN
    measure,
    transition,
    CASE WHEN 0 < n < 5 THEN '<5' ELSE toString(n) END AS participants_decreased
ORDER BY measure, transition;

// Chart 3: fictional participant for a public screenshot.
// Uses separate Demo labels so it never mixes with real participants.
// Run a), b) and c) in order; d) removes it again.

// a) Fictional person, waves and scores (values are invented)
MERGE (p:DemoPerson {name: 'P000 (fictional)'})
WITH p
UNWIND [
    {wave: 1, dep: 18, anx: 14, str: 20, pcl: 34},
    {wave: 2, dep: 12, anx: 10, str: 14, pcl: 26},
    {wave: 3, dep: 20, anx: 16, str: 22, pcl: 38}
] AS w
MERGE (v:DemoVisit {demo_key: 'P000-W' + toString(w.wave)})
SET v.name = 'Wave ' + toString(w.wave), v.wave = w.wave
MERGE (p)-[:HAS_VISIT]->(v)
WITH v, w
UNWIND [
    ['DASS Depression', w.dep], ['DASS Anxiety', w.anx],
    ['DASS Stress', w.str],     ['PCL-5', w.pcl]
] AS s
MERGE (m:DemoMeasurement {demo_key: v.demo_key + '-' + s[0]})
SET m.name = s[0] + ': ' + toString(s[1]), m.value_as_number = s[1]
MERGE (v)-[:HAS_MEASUREMENT]->(m);

// b) Visit order and one observation with its category
MATCH (v1:DemoVisit), (v2:DemoVisit)
WHERE v2.wave = v1.wave + 1
MERGE (v1)-[:NEXT_VISIT]->(v2)
WITH count(*) AS linked
MATCH (v:DemoVisit {wave: 1})
MERGE (o:DemoObservation {demo_key: 'P000-W1-marital'})
SET o.name = 'Marital status'
MERGE (c:DemoCategory {name: 'Married'})
MERGE (v)-[:HAS_OBSERVATION]->(o)
MERGE (o)-[:HAS_CATEGORY]->(c);

// c) Show it (Graph tab)
MATCH path = (:DemoPerson)-[*1..3]->()
RETURN path;

// d) Remove the fictional participant
MATCH (n)
WHERE any(l IN labels(n) WHERE l STARTS WITH 'Demo')
DETACH DELETE n;

// Chart 4 (after the full cohort is imported): engagement funnel
MATCH (v:Visit)
WHERE size([(v)-[:HAS_MEASUREMENT]->(m:Measurement)
            WHERE m.value_as_number IS NOT NULL | m]) > 0
RETURN v.visit_sequence AS wave, count(v) AS participants_assessed
ORDER BY wave;
