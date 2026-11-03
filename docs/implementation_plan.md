# Implementation roadmap

## Phase 1: Graph foundation

- Confirm stable person and visit pseudonymization.
- Reuse the same secret across all scripts.
- Validate existing graph IDs before writing updates.
- Preserve the original OMOP relationships required for patient tracing.

## Phase 2: Longitudinal patient view

- Add visit sequencing.
- Create NEXT_VISIT edges.
- Link each measurement and observation to its visit.
- Ensure a single person can be followed across wave 1, wave 2, and wave 3.

## Phase 3: Clinical enrichment

- Add measurement score nodes and values.
- Add observation category nodes.
- Include condition nodes for mental health and related context.
- Display real observation and measurement names for clinical readability.

## Phase 4: Care-path analysis

- Identify wave-to-wave change in measurement scores.
- Detect worsening trends or improvement trends.
- Flag drop-off between consecutive visits.
- Distinguish active engagement from disengagement.

## Phase 5: Clinical notes integration

- Import note data.
- Extract symptoms, risk flags, and adherence issues.
- Link extracted findings to the correct patient and visit.
- Build a richer mental health care-path model.

## Phase 6: GitHub and public-facing documentation

- Prepare a clear README.
- Add architecture diagrams and workflow descriptions.
- Document the longitudinal patient story.
- Include example outputs and screenshot evidence.
- Make the repository funder-ready and understandable to non-technical stakeholders.

---

## Target outcome

The final system should be able to answer:

- Who is the same patient across multiple visits?
- What observations were recorded at each wave?
- Which measurements changed over time?
- Where did the patient stop attending care?
- What symptoms or care concerns appear over the timeline?

This is the practical value of the OMOP-to-knowledge-graph pipeline for mental health research and care pathway analysis.
