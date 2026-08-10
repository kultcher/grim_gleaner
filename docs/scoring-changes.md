# Scoring Revision Notes

This supplements the main project plan with a proposed revision to Grim Gleaner’s relevance grading.

## Goal

The current scoring model is too additive: items with many moderately relevant stat categories can accumulate enough points to outrank smaller, highly focused packages.

The revised model should better answer:

> How strongly and how densely does this affix or item correspond to the build profile?

It should still measure **relevance, not item power**.

Do not add resistance-cap logic, current-character stat optimization, or other attempts to calculate marginal power.

---

## 1. Keep weighted stat priorities

Continue using the user’s 0–4 star weighting system.

Consider applying a nonlinear curve so higher priorities matter substantially more than lower priorities:

```python
value = (weight / 4.0) ** 2
```

Approximate values:

```text
1★ = 0.06
2★ = 0.25
3★ = 0.56
4★ = 1.00
```

This prevents many low-priority matches from easily equaling a few core matches.

Do not completely exclude 1-star stats from grading. They should simply contribute very little.

---

## 2. Add diminishing returns for additional matches

Replace the plain sum of matching stat values with sorted geometric decay.

Sort matching values from highest to lowest, then:

```python
score = sum(
    value * gamma**index
    for index, value in enumerate(sorted_values)
)
```

Start experimentation around:

```python
gamma = 0.90
```

Interpretation:

```text
1st match = 100%
2nd match = 90%
3rd match = 81%
4th match = 73%
5th match = 66%
```

This does not penalize thematic specialization. Additional useful stats remain valuable; they simply provide diminishing evidence that an item is relevant.

Avoid aggressive decay initially. Test roughly `0.88–0.92`.

---

## 3. Make relevance density weight-aware

The current coverage calculation should not count a 1-star match the same as a 4-star match.

Use weighted relevance mass:

```python
matched_mass = sum(weight / 4.0 for matched stats)
density = matched_mass / total_semantic_stat_count
```

Keep the simple `matched / total` value available for display if useful, but use weighted density when applying any dilution multiplier.

Items with many irrelevant properties should therefore score somewhat lower than tightly focused items.

Keep this penalty moderate. Gleaner should not treat extra off-theme properties as actively harmful; it should simply recognize that less of the item maps to the build.


---

## Proposed scoring pipeline

```text
Profile stars
    ↓
nonlinear stat value
    ↓
sorted geometric diminishing returns
    ↓
weight-aware relevance density multiplier
    ↓
profile + item-bucket normalization
    ↓
letter grade
```

