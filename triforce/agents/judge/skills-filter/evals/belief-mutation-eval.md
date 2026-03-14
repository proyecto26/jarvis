# Eval: belief-mutation

Test cases for the belief-mutation skill (SSGM protocol).

---

## Test Case 1: No Conflict — New Belief

### Input
```
Existing beliefs: [
  {"belief": "Code reviews improve quality", "strength": 0.8},
  {"belief": "Short functions are easier to test", "strength": 0.6}
]
New belief: "Pair programming reduces bug count by 30%"
```

### Expected Behavior
- Conflict check passes (no similar existing belief)
- Mutation proceeds directly
- mutation_type: "new"
- strength: 0.3-0.5 (new belief, not yet confirmed)

### Pass Criteria
- No conflict reported
- Required fields all present (belief, strength, reason, source_event, mutation_type)
- Strength NOT above 0.5 for a new belief

---

## Test Case 2: Conflict — Merge (Refinement)

### Input
```
Existing beliefs: [
  {"belief": "Code reviews improve quality", "strength": 0.8}
]
New belief: "Code reviews improve quality most when the reviewer has context
about the change's purpose"
```

### Expected Behavior
- Conflict detected (high similarity with existing belief)
- Decision tree: new is MORE specific → MERGE
- Both beliefs persist, new references old

### Pass Criteria
- Conflict report: has_conflict=true
- Recommendation: "merge"
- Original belief NOT removed
- New belief stored with reference to original

---

## Test Case 3: Conflict — Supersede

### Input
```
Existing beliefs: [
  {"belief": "Always use mocked tests for database interactions", "strength": 0.8}
]
New belief: "Integration tests with real databases catch bugs mocks miss"
Source evidence: "3 regression bugs escaped mocked tests in 2 weeks"
```

### Expected Behavior
- Conflict detected (contradictory testing approach)
- Strong evidence supports new belief
- Decision tree: E contradicted by strong evidence → SUPERSEDE
- Old belief marked with valid_until=now

### Pass Criteria
- Conflict report: has_conflict=true
- Recommendation: "supersede"
- Old belief superseded (not deleted)
- New belief includes source_event reference

---

## Test Case 4: Conflict — Coexist (Context-Dependent)

### Input
```
Existing beliefs: [
  {"belief": "Short messages are better for communication", "strength": 0.7}
]
New belief: "Detailed explanations are better for communication"
Context: "Short messages for WhatsApp, detailed for documentation"
```

### Expected Behavior
- Conflict detected (seemingly contradictory)
- But they apply to different contexts
- Decision tree: different contexts → COEXIST
- Both persist with context tags

### Pass Criteria
- Conflict report: has_conflict=true
- Recommendation: "coexist"
- Both beliefs persist with context differentiation

---

## Test Case 5: Stability Monitor — Drift Warning

### Input
```
Recent mutations (last 7 days): 6 mutations
```

### Expected Behavior
- Stability monitor detects >5 mutations in 7 days
- Emits drift warning

### Pass Criteria
- drift_warning: true
- Warning logged in journal

---

## Test Case 6: Required Fields Validation

### Input
```
New belief mutation with missing fields:
  {"belief": "Testing matters", "strength": 0.95}
  (missing: reason, source_event, mutation_type)
```

### Expected Behavior
- Skill rejects the mutation for missing required fields
- belief is not falsifiable ("Testing matters" is too vague)
- strength 0.95 is too high for a new belief

### Pass Criteria
- Mutation rejected or flagged
- Specific error: missing reason, source_event, mutation_type
- Specific error: belief not falsifiable
- Specific error: strength too high for new belief

---

## Scoring Criteria

| Criterion | Weight | Description |
|---|---|---|
| Conflict detection | 25% | Correctly identifies conflicts using similarity check |
| Decision tree routing | 25% | Correct recommendation (merge/supersede/coexist/review) |
| Required fields | 20% | All fields present and valid |
| Stability monitoring | 15% | Drift and oscillation correctly detected |
| Evidence linkage | 15% | source_event properly traces to evidence |
