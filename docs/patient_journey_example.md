# Example patient journey in the knowledge graph

## Storyline

This example shows how the same person can be tracked across the full study timeline and represented as a care pathway rather than a set of disconnected rows.

---

## Person identity

Each patient is assigned a stable graph identity that is consistent across all visits, while preserving privacy through pseudonymization.

Example:
- Internal graph identity: Person-ARQ123
- Study person_id: 45821
- Visits: Wave 1, Wave 2, Wave 3

---

## Wave 1

### Patient context
- Person attends first study wave.
- Baseline observations are recorded.
- Initial measurements are collected.

### Example observation values
- Marital status: Married
- Household size: 4
- Birth outcome: Live Birth
- Delivery method: Spontaneous vaginal delivery

### Example measurement values
- PHQ-9 score: 18
- GAD-7 score: 15
- Sleep quality score: 8

### Clinical interpretation
The patient shows elevated mental health distress at baseline, with moderate-to-severe symptoms and poor sleep.

---

## Wave 2

### Patient context
- Follow-up visit occurs after a treatment or support interval.
- The same person is matched to their prior visit history through the graph.

### Example observation values
- Marital status: Married
- Household size: 4
- Birth outcome: Live Birth

### Example measurement values
- PHQ-9 score: 12
- GAD-7 score: 10
- Sleep quality score: 5

### Clinical interpretation
Symptoms have improved, but the patient remains above the lower-risk threshold. The graph captures the change over time instead of treating Wave 1 and Wave 2 as separate records.

---

## Wave 3

### Patient context
- Patient is seen again at a later follow-up visit.
- The graph shows whether the patient remained in care or disengaged.

### Example observation values
- Marital status: Married
- Household size: 4
- Delivery method: Spontaneous vaginal delivery

### Example measurement values
- PHQ-9 score: 21
- GAD-7 score: 16
- Sleep quality score: 8

### Clinical interpretation
There is a worsening of symptoms between wave 2 and wave 3, suggesting a possible decline in wellbeing or missed support opportunities. This is a care pathway signal.

---

## Why the graph is important here

In a table-based database, these appear as separate rows and may be difficult to interpret as a continuum.

In the graph, the same patient is clearly linked across visits:

- Person-ARQ123 -> HAS_VISIT -> Wave 1
- Person-ARQ123 -> HAS_VISIT -> Wave 2
- Person-ARQ123 -> HAS_VISIT -> Wave 3

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
