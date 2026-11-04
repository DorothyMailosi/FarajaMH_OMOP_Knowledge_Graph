# Example patient journey in the knowledge graph

> **Illustrative example:** The wave-by-wave scores and interpretations below are placeholders to explain the intended analysis. They are not verified results for a real participant and must not be reported as study findings without checking the approved source data.

## Storyline

This example shows how the same person can be tracked across the full study timeline and represented as a care pathway rather than a set of disconnected rows.

---

## Person identity

Each patient is assigned a stable graph identity that is consistent across all visits, while preserving privacy through pseudonymization.

Example:
- Display ID: P000 (fictional example; real participants are numbered from P001)
- Internal graph_id: a pseudonym; the source OMOP person_id is never stored in the graph
- Visits: Wave 1, Wave 2, Wave 3

---

## Wave 1

### Patient context
- Person attends first study wave.
- Baseline observations are recorded.
- Initial measurements are collected.

### Example observation values
- Marital status: Married
- Number in household: Member of small family
- Birth outcome: Live Birth
- Delivery method: Spontaneous vaginal delivery

### Example measurement values
- DASS depression score: 18
- DASS anxiety score: 15
- PCL-5 score: 8

### Clinical interpretation
The patient shows elevated mental health distress at baseline, with elevated depression and anxiety scores.

---

## Wave 2

### Patient context
- Follow-up visit occurs after a treatment or support interval.
- The same person is matched to their prior visit history through the graph.

### Example observation values
- Marital status: Married
- Number in household: Member of small family
- Birth outcome: Live Birth

### Example measurement values
- DASS depression score: 12
- DASS anxiety score: 10
- PCL-5 score: 5

### Clinical interpretation
Symptoms have improved, but the patient remains above the lower-risk threshold. The graph captures the change over time instead of treating Wave 1 and Wave 2 as separate records.

---

## Wave 3

### Patient context
- Patient is seen again at a later follow-up visit.
- The graph shows whether the patient remained in care or disengaged.

### Example observation values
- Marital status: Married
- Number in household: Member of small family
- Delivery method: Spontaneous vaginal delivery

### Example measurement values
- DASS depression score: 21
- DASS anxiety score: 16
- PCL-5 score: 8

### Clinical interpretation
There is a worsening of symptoms between wave 2 and wave 3, suggesting a possible decline in wellbeing or missed support opportunities. This is a care pathway signal.

---

## Why the graph is important here

In a table-based database, these appear as separate rows and may be difficult to interpret as a continuum.

In the graph, the same patient is clearly linked across visits:

- P000 -> HAS_VISIT -> Wave 1
- P000 -> HAS_VISIT -> Wave 2
- P000 -> HAS_VISIT -> Wave 3

And each visit contains:
- specific observations
- measurement values
- associated conditions and future note-derived symptoms

This supports:
- longitudinal trend analysis
- point-of-care interpretation
- care disengagement detection
- patient pathway mapping

---

## Care pathway insight

This patient story demonstrates how a graph can help identify:

- whether symptoms improve or worsen over time,
- whether the patient remains engaged in care,
- whether social or reproductive context is associated with clinical status,
- where a care gap or drop-off may have occurred.

That is a substantially stronger clinical story than showing raw rows in pgAdmin.

## Reading the current Neo4j diagram

The current Browser visualization for `P014` shows a person node connected to visit nodes and many observation and measurement nodes. Visible observation concepts include marital status, parity, gravida, birth outcome, delivery method, and household size. This demonstrates that the graph brings records together around a consistent pseudonymized person identity.

The screenshot does not yet communicate the complete care pathway clearly. The force-directed layout is crowded, labels are truncated, and category values and measurement scores are not organized visibly by wave. In particular, viewers need to be able to follow a path such as:

`Person -> Visit (wave/date) -> Observation -> ObservationCategory`

and:

`Person -> Visit (wave/date) -> Measurement (real name and score)`

The next visualization should show the visit sequence clearly, attach category nodes such as `Married` or `Parity 1` to their corresponding observation, and show each real measurement name with its value for that visit. Only then can viewers readily see improvement, worsening, or a gap in follow-up. A missing later visit can indicate no recorded follow-up in the available data; it should not by itself be interpreted as proof that a person dropped out of care.
