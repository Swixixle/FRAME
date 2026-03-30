# How coalition maps work

A coalition map answers one question: on this specific story, which outlets are aligned with which position, and how far apart are the two most opposed sides?

---

## The basic idea

When you analyze an article, PUBLIC EYE searches a range of global sources. Those sources don't all frame the story the same way. Some emphasize certain facts. Some bury others. Some treat the same event as a humanitarian crisis; others treat it as a manufactured scandal.

The coalition map:
1. Identifies the two most irreconcilable positions on the story
2. Assigns every other outlet to whichever position it most closely mirrors
3. Scores the distance between the two anchors (0–100)
4. Names the specific thing that cannot be simultaneously true across both positions

---

## The divergence score

The score is calculated from what each anchor cluster emphasizes vs. minimizes:

- **Emphasis overlap:** how many emphasis tags appear on both sides (lower overlap = higher divergence)
- **Minimization inversion:** does side A minimize what side B emphasizes? (full inversion = maximum divergence)
- **Confidence weight:** how certain each cluster is in its framing

Formula (simplified):
```
score = (emphasis_divergence × 0.4) + (minimization_inversion × 0.4) + (confidence_weight × 0.2)
```

The result is scaled to 0–100.

**What the buckets mean:**
- **0–25:** Most outlets agree on the basics. The story is not particularly contested.
- **26–60:** Same facts, different spin. Framing diverges but there's a shared factual foundation.
- **61–100:** Parallel realities. The two sides are not just spinning differently — they're treating the event as fundamentally different things.

---

## Outlet types

Every outlet in a chain carries a type:

- **PRIVATE** — privately owned, commercial news organization
- **STATE** — government-controlled or government-funded editorial line
- **PUBLIC** — public broadcaster with editorial independence (BBC, Deutsche Welle, etc.)

This matters because a cluster of state media outlets aligning on a position is a different signal than the same alignment from independent private outlets. The type doesn't determine credibility — it provides context.

---

## Alignment confidence

Each outlet in a chain has an alignment confidence:

- **High** — explicitly endorses the position in its coverage
- **Medium** — frames the story in ways consistent with the position
- **Low** — aligned by proximity or omission, not by explicit endorsement

---

## The irreconcilable gap

This is the sentence that names what cannot be simultaneously true. It's the actual disagreement — not "they have different perspectives" but "one of these things is true and the other is false, and they're not both covering the same event."

Example:
> "Position A views the FBI document release as legitimate institutional transparency requiring professional journalistic verification, while Position B sees it as a manufactured political scandal. These cannot both be true about the nature and purpose of official document disclosure."

---

## Running it

The coalition map runs async after article analysis. It takes a separate Claude call to build.

```bash
# After analyze-article returns a receipt_id:
curl -sS -X POST "https://frame-2yxu.onrender.com/v1/coalition-map" \
  -H "Content-Type: application/json" \
  -d '{"receipt_id":"your-receipt-id"}'
# Returns: {"status": "processing"}

# Poll after ~30 seconds:
curl "https://frame-2yxu.onrender.com/v1/coalition-map/your-receipt-id" \
  | python3 -m json.tool
```

---

## What coalition maps require

The receipt must have `global_perspectives` data. This is generated as part of `analyze-article` when the full pipeline runs. If a receipt was generated before global perspectives were added to the pipeline, it cannot get a coalition map — generate a new receipt.

---

## What coalition maps don't do

- They don't determine which side is correct
- They don't assign a political bias rating
- They don't claim the outlets listed actually covered this specific article — the alignment is based on documented editorial positions and historical coverage patterns, not per-article analysis
- They don't cover every outlet on earth — they work from the source clusters searched during the analysis

The coalition map is a navigational tool. It tells you the shape of the disagreement. Investigating the substance is still your job.
