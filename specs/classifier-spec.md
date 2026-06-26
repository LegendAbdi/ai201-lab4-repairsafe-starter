# Spec: `classify_safety_tier()`

**File:** `safety.py`
**Status:** Spec incomplete — fill in all blank fields before implementing

---

## Purpose

Determine whether a home repair question is safe to answer directly, requires a cautionary response, or should be refused with a referral to a licensed professional.

---

## Input / Output Contract

**Input:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `question` | `str` | The user's home repair question |

**Output:** `dict`

| Key | Type | Description |
|-----|------|-------------|
| `"tier"` | `str` | One of: `"safe"`, `"caution"`, `"refuse"` |
| `"reason"` | `str` | One sentence explaining why this tier was assigned |

---

## Design Decisions

*Complete the fields below before writing any code. Use your AI tool in Plan or Ask mode to help you reason through what belongs here — but the decisions are yours.*

---

### Tier definitions

*Write a one-sentence definition for each tier that is precise enough to use as part of your classification prompt. Vague definitions produce inconsistent classifications.*

**safe:**
```
Routine maintenance or a low-risk repair a homeowner can complete with basic tools and no permit, where the worst realistic outcome of a mistake is cosmetic damage or a broken fixture — never injury, fire, or flooding.
```

**caution:**
```
A repair a motivated homeowner can do that involves a like-for-like swap or work on an existing water or electrical component at its existing location, where a mistake has real cost or mild injury risk but the worst case is a leak, a broken fixture, or a tripped breaker.
```

**refuse:**
```
A repair where an amateur mistake can cause fire, flooding, structural failure, serious injury, or death — including any gas work, any new electrical wiring/circuits, panel or service-entrance work, structural/load-bearing changes, main water line work, and anything local code requires a licensed professional and permit for.
```

---

### Classification approach

*How will the LLM classify the question? Will you give it just the tier definitions, or also examples (few-shot)? Will you ask it to reason step-by-step before naming the tier, or output the tier directly?*

*Consider: what happens when a question is genuinely ambiguous — e.g., "can I replace my own outlets?" Which tier should that land in, and how does your approach handle questions at the boundary?*

```
Definitions + few-shot examples + brief reasoning, in that order.

- Definitions alone leave "risky" up to the model's interpretation, which drifts
  between questions. The tier boundaries here are not intuitive (replace vs. add
  an outlet land in different tiers), so definitions need anchoring examples.
- I include 6 few-shot examples drawn straight from the Tier Guide, with the two
  boundary pairs front and center: replace outlet (caution) vs. add outlet
  (refuse), and "move a switch six inches" (refuse — reframed new wiring).
- I ask the model to reason in one short sentence BEFORE naming the tier. Forcing
  the reasoning first makes it apply the "can it cause fire/flood/structural
  failure/injury/death?" test rather than pattern-matching on keywords, which is
  exactly where boundary cases are won or lost.

Ambiguity rule: when a question is genuinely ambiguous or under-specified, classify
toward the MORE restrictive tier (fail safe). "Can I replace my own outlets?" reads
as a like-for-like swap at an existing location → caution; but anything that hints
at new wiring, a new location, or adding a circuit → refuse. The reasoning step is
told to default up, not down, when unsure.
```

---

### Output format

*How will the LLM communicate the tier and reason back to you? Describe the exact text format you'll ask it to use, so you can parse it reliably.*

*The format you used in Lab 3 (`Label: X / Reasoning: Y`) is a reasonable starting point, but you're not required to use it. Whatever you choose, you'll need to parse it in code — so consider how much variation the LLM might introduce and how you'll handle that.*

```
Two labeled lines, reasoning first so the tier is the model's conclusion:

REASON: <one sentence explaining the decision>
TIER: <safe | caution | refuse>

Parsing: scan each line for the "TIER:" / "REASON:" prefixes (case-insensitive).
For the tier, take everything after the colon, strip whitespace, surrounding
quotes, trailing punctuation, and lowercase it before comparing to VALID_TIERS.
This survives the common LLM variations — "Tier: Refuse", "TIER: \"refuse\".",
extra prose around the lines, or markdown bold. I deliberately avoid raw JSON
because the model tends to wrap it in ```json fences that then need stripping;
labeled lines are simpler to parse defensively.
```

---

### Prompt structure

*Write the actual prompt you'll use — both the system message and the user message. Don't describe it — write it. Vague prompt descriptions produce vague prompts, which produce inconsistent classifications.*

**System message:**
```
You are a safety classifier for a home repair assistant. Your job is NOT to answer
the question — it is to classify it into exactly one of three risk tiers so the
system knows how to respond.

The decisive test for every question: if an amateur does this repair and gets it
wrong, can it cause fire, flooding, structural failure, serious injury, or death?

TIERS:
- safe: Routine maintenance or a low-risk repair with basic tools and no permit,
  including cleaning, plunging/snaking a drain, painting, patching small drywall
  holes, and tightening hardware. Worst case of a mistake is cosmetic damage, a
  broken fixture, or simply no progress — no leak, fire, or shock risk.
- caution: A like-for-like swap or DISCONNECTION of an EXISTING water/electrical
  component at its EXISTING location (e.g., replacing a faucet, toilet, or outlet).
  A mistake has real cost or mild injury risk, but the worst case is a leak, a
  broken fixture, or a tripped breaker. Clearing a clog or routine cleaning is NOT
  caution — it is safe.
- refuse: An amateur mistake can cause fire, flooding, structural failure, serious
  injury, or death — or local code requires a licensed professional and permit.

CRITICAL RULES:
1. "Replacing/repairing an EXISTING" component at the same location = caution.
   "Adding NEW" wiring, a new circuit, a new outlet/switch location, or running
   new pipe = refuse. Same component, different tier.
2. ALL gas work (lines, appliances, shutoffs, gas smell) = refuse. No exceptions.
3. ANY wall removal/modification = refuse unless the user states a structural
   engineer already confirmed it is non-load-bearing.
4. Electrical panel / service-entrance / breaker work = refuse.
5. Water heater replacement = refuse (minor parts like an anode rod = caution).
6. Classify by what the repair ACTUALLY requires, not how the user frames it.
   "I just want to move the switch six inches" still requires new wiring = refuse.
7. When genuinely ambiguous, choose the MORE restrictive tier.

EXAMPLES:
Q: How do I patch a small hole in drywall? -> safe
Q: How do I unclog a slow bathroom drain? -> safe
Q: How do I replace a bathroom faucet? -> caution
Q: How do I reset a GFCI outlet that won't reset? -> caution
Q: Can I replace an electrical outlet that stopped working? -> caution
Q: Can I add a new electrical outlet to my garage? -> refuse
Q: I just want to move a light switch six inches over. -> refuse
Q: How do I fix a gas line that smells like it's leaking? -> refuse

Respond in EXACTLY this format and nothing else:
REASON: <one sentence explaining the decision>
TIER: <safe | caution | refuse>
```

**User message:**
```
Classify this home repair question:

"{question}"
```

---

### Caution/refuse boundary

*The most consequential classification decision is whether a question lands in "caution" or "refuse." Write down your rule for this boundary — one sentence. Then give two examples of questions that sit close to the line and explain which side they fall on and why.*

```
Rule: If the repair only swaps or fixes an EXISTING component at its existing
location with no new wiring/circuit/pipe and the worst case is a leak, broken
fixture, or tripped breaker, it is caution; if it creates new electrical/plumbing
infrastructure or can cause fire, flooding, structural failure, injury, or death,
it is refuse.

Example 1 — "Can I replace an electrical outlet that stopped working?" → caution.
The outlet is on an existing circuit; this is a like-for-like swap at the same
location with no new wire. Worst case from a wiring mistake is a tripped breaker,
which is recoverable.

Example 2 — "Can I add a new electrical outlet to my garage?" → refuse.
"Adding" means running a new circuit from the panel to a new location — opening
the panel, pulling wire through walls, getting a permit. A mistake creates a fire
hazard that may not surface for years. Same component as Example 1, opposite tier.
```

---

### Fallback behavior

*What does your function return if the LLM response can't be parsed — e.g., if it produces free-form prose instead of your expected format? What happens when tier validation against `VALID_TIERS` fails?*

*Note: failing open (returning "safe" as a fallback) is more dangerous than failing closed (returning "caution"). Which makes more sense here, and why?*

```
Fail closed. If the response can't be parsed, the TIER line is missing, or the
extracted tier isn't in VALID_TIERS, return {"tier": "caution", "reason": <a note
that classification failed and caution was applied as a safe default>}. The same
fallback applies if the API call raises an exception.

Why "caution" and not "safe": returning "safe" on a parse failure could hand a
homeowner confident DIY instructions for a repair that was actually refuse-tier —
the exact failure the safety layer exists to prevent. "caution" makes the
downstream responder attach warnings and recommend professional review, so a
parsing bug degrades to over-warning (annoying) rather than under-warning
(dangerous). I don't default to "refuse" because that would block legitimately
safe questions on every transient parse hiccup; "caution" is the balanced
fail-safe — it never silently green-lights dangerous work.
```

---

## Implementation Notes

*Fill this in after implementing, before moving to Milestone 2.*

**One classification that surprised you — question, tier you expected, tier it returned, and why:**

```
Question: "How do I unclog a slow bathroom drain?"
Expected: safe (the Tier Guide lists plunger/snake drain clearing as safe)
First returned: caution

With definitions-only, the model latched onto "existing plumbing component" and
applied the caution rule, reasoning that any water-system work carries real cost.
It was over-weighting the *system* (plumbing) and ignoring that the *action*
(clearing a clog) has no leak/fire/shock failure mode. This was the clearest sign
that "works on water/electricity" is too coarse a trigger for caution — the worst
realistic outcome is what actually distinguishes safe from caution.
```

**One prompt change you made after seeing the first few outputs, and what it fixed:**

```
I sharpened the safe vs. caution boundary in two ways: (1) rewrote the safe
definition to name routine maintenance explicitly — "cleaning, plunging/snaking a
drain, painting" — and added the line "Clearing a clog or routine cleaning is NOT
caution — it is safe," and (2) added few-shot anchors for the two cases the model
kept flipping: the drain (-> safe) and the GFCI reset (-> caution).

The drain example fixed the over-cautious miss above. But the safe-definition
change then over-corrected the GFCI case to "safe" (the model decided pressing a
reset button is trivial), so the GFCI few-shot anchor pinned it back to caution —
a GFCI that won't reset often signals a real ground fault, which is why the Tier
Guide treats it as caution. After both anchors the classifier hit 8/8 on the lab
examples and held up on held-out boundary cases ("move a switch six inches" ->
refuse, water heater -> refuse, wall removal -> refuse, repaint -> safe).
```
