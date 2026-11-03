# FarajaMH OMOP Knowledge Graph

## Overview

This project builds a longitudinal mental health knowledge graph from OMOP-based study data. The system links the same person across multiple visits and time points, connecting their observations, measurements, conditions, and future clinical note-derived findings into a continuous care pathway.

The goal is to move beyond static database tables and support a more clinically meaningful representation of patient journeys in mental health care.

---

## Why this matters

Most clinical datasets are stored in tables, but treatment is not experienced as a table. It is experienced as a personal journey over time.

A patient may:
- begin care at wave 1,
- show changes in symptoms at wave 2,
- disengage, worsen, or return for follow-up at wave 3.

In a traditional relational database, these may appear as disconnected records. In a knowledge graph, the same person remains connected across visits and events, making the care pathway visible.

This is particularly important for mental health, where symptoms, functioning, risk indicators, and treatment engagement often evolve over time.

---

## The problem we are addressing

Healthcare and research teams often have rich clinical data, but it is difficult to see:
- which observations belong to the same patient over time,
- how symptoms change across visits,
- where a patient dropped out of care,
- which measurements and conditions are associated with a care episode,
- how longitudinal trajectories differ across patients.

The knowledge graph approach addresses this by representing relationships explicitly rather than only storing rows of data.

---

## Our approach

We connect OMOP-derived clinical data to a Neo4j graph using a consistent pseudonymized identifier strategy. This means the same person can be traced across multiple records while preserving privacy.

The graph captures:
- Person identity
- Visit timeline
- Observation values and categories
- Measurement scores
- Conditions
- Care continuity and visit sequencing
- Future clinical note extraction and symptom linkage

This creates a foundation for longitudinal analysis of mental health care, patient retention, and care pathway identification.

---

## Example patient journey

A single participant can be followed as a longitudinal case:

- Wave 1: baseline assessment, observations recorded, initial measurement scores captured
- Wave 2: patient returns for follow-up, symptoms and metrics are re-evaluated
- Wave 3: graph shows whether the patient remained engaged, improved, worsened, or dropped out of care

Example observation labels:
- Marital status
- Household size
- Gravida
- Parity
- Birth outcome
- Delivery method

Example measurement labels:
- PHQ-9 score
- GAD-7 score
- Depression score
- Anxiety score
- Sleep quality score
- Functional wellbeing score

The graph can therefore show not only what happened, but how the patient’s condition changed over time.

---

## Why this is stronger than pgAdmin alone

PostgreSQL and pgAdmin are excellent for structured storage and reporting, but they are weaker at representing patient trajectories and relationships across time.

A graph enables questions such as:
- Which patient followed the same care path from wave 1 to wave 2 to wave 3?
- Which symptom scores increased or decreased over time?
- Which observations are associated with a given patient episode?
- Where did a patient disengage from follow-up?
- Which clinical events are connected to the same person and visit flow?

This makes the graph particularly valuable for mental health and care continuum analysis.

---

## Project structure

The repository currently contains the core scripts needed to validate, enrich, and connect OMOP-derived data to Neo4j:

- import_study2_graph.py
  - imports and validates the study graph structure
- enrich_measurement_scores.py
  - enriches measurement information already present in the graph
- enrich_observation_values.py
  - attaches numeric and categorical observation values
- enrich_observation_categories.py
  - links observation categories to the correct study records
- enrich_study2_graph.py
  - assigns visit order and creates NEXT_VISIT relationships
- test_connections.py
  - validates PostgreSQL and Neo4j connectivity
- test_graph_import.py
  - confirms a synthetic graph can be created successfully

---

## Technical direction

The project is designed around a repeatable pipeline:

1. Read source data from PostgreSQL
2. Pseudonymize stable person and visit IDs
3. Validate relationships before updating the graph
4. Enrich nodes with measurements, observations, categories, and visit sequencing
5. Maintain the same person identity across waves and visits
6. Preserve a clinically interpretable view of the final graph

This ensures that the graph remains faithful to the OMOP source while also exposing longitudinal relationships in a clinically useful form.

---

## Future development

The next phase of the project is to extend the graph beyond structured OMOP fields to include:
- clinical notes
- extracted symptoms and risk markers
- treatment engagement tracking
- care gap and drop-off analysis
- refinement of mental health-specific care pathways

This will support the transition from a structured graph pipeline to a more complete mental health intelligence platform.

---

## Funders and stakeholders

This project demonstrates how OMOP data can be transformed into a clinically meaningful and interpretable knowledge graph. It is not only a data integration exercise; it is designed to support real-world questions about patient progression, symptom trajectories, continuity of care, and service disengagement.

The project offers a clear pathway toward a more actionable mental health information system that can reveal where patients are lost to follow-up and where more tailored care support may be needed.

---

## Summary

This repository provides the foundation for a longitudinal, person-centered knowledge graph that connects OMOP data to clinically relevant relationships in Neo4j. By tracking the same people across waves and linking observations, measurements, and visits, the project captures the real story of care rather than isolated data points.

This work is an important step toward a healthcare intelligence approach that is more useful for mental health programs, patient pathway analysis, and future clinical-note-informed decision support.
