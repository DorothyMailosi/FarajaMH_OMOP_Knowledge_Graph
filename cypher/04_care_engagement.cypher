// ============================================================
// 04 ENGAGEMENT AND FOLLOW-UP GAPS
// A participant counts as "assessed" at a wave when that visit has
// at least one recorded score. Study 2 has 3 waves.
//
// Caution: "no recorded scores after wave N" means no follow-up
// data in this dataset. It is NOT proof that someone left care.
// Confirming care drop-off needs appointment, referral, treatment
// or attendance records. Read-only.
// ============================================================

// Engagement funnel: participants assessed at each wave (aggregate)
MATCH (v:Visit)
WHERE size([(v)-[:HAS_MEASUREMENT]->(m:Measurement)
            WHERE m.value_as_number IS NOT NULL | m]) > 0
RETURN v.visit_sequence AS wave, count(v) AS participants_assessed
ORDER BY wave;

// Each participant's engagement status
MATCH (p:Person)-[:HAS_VISIT]->(v:Visit)
WITH p, v, size([(v)-[:HAS_MEASUREMENT]->(m:Measurement)
                 WHERE m.value_as_number IS NOT NULL | m]) AS scores
ORDER BY v.visit_sequence
WITH p, collect({wave: v.visit_sequence, scores: scores}) AS visits
WITH p, visits, [x IN visits WHERE x.scores > 0 | x.wave] AS assessed
RETURN
    p.display_id AS participant,
    [x IN visits | x.wave] AS waves_with_visit,
    assessed AS waves_with_scores,
    CASE
        WHEN size(assessed) = 0 THEN 'No scores recorded'
        WHEN assessed[-1] < 3
            THEN 'No recorded scores after wave ' + toString(assessed[-1])
        WHEN size(assessed) < 3 THEN 'Missed a wave, then returned'
        ELSE 'Assessed at all 3 waves'
    END AS engagement
ORDER BY participant;

// Where follow-up stops: participants grouped by last assessed wave
MATCH (p:Person)-[:HAS_VISIT]->(v:Visit)
WHERE size([(v)-[:HAS_MEASUREMENT]->(m:Measurement)
            WHERE m.value_as_number IS NOT NULL | m]) > 0
WITH p, max(v.visit_sequence) AS last_assessed_wave
RETURN last_assessed_wave, count(p) AS participants
ORDER BY last_assessed_wave;

// Visits that exist but have fewer scores than the participant's
// other visits: an incomplete assessment rather than a missed visit
MATCH (p:Person)-[:HAS_VISIT]->(v:Visit)
WITH p, v, size([(v)-[:HAS_MEASUREMENT]->(m:Measurement) | m]) AS scores
WITH p, collect({wave: v.visit_sequence, scores: scores}) AS visits,
     max(scores) AS most
UNWIND visits AS x
WITH p, x, most
WHERE x.scores < most
RETURN p.display_id AS participant, x.wave AS wave,
       x.scores AS scores_recorded, most AS scores_expected
ORDER BY participant, wave;
