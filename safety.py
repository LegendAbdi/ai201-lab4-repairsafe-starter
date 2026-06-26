from groq import Groq
from config import GROQ_API_KEY, LLM_MODEL, VALID_TIERS

_client = Groq(api_key=GROQ_API_KEY)

# Fail closed: if anything goes wrong (API error, unparseable response, or an
# unrecognized tier), default to "caution" rather than "safe". Returning "safe"
# on failure could hand a homeowner DIY instructions for refuse-tier work — the
# exact failure the safety layer exists to prevent.
_FALLBACK_TIER = "caution"

SYSTEM_PROMPT = """You are a safety classifier for a home repair assistant. Your job is NOT to answer \
the question — it is to classify it into exactly one of three risk tiers so the system knows how to respond.

The decisive test for every question: if an amateur does this repair and gets it wrong, can it cause \
fire, flooding, structural failure, serious injury, or death?

TIERS:
- safe: Routine maintenance or a low-risk repair with basic tools and no permit, including cleaning, \
plunging/snaking a drain, painting, patching small drywall holes, and tightening hardware. Worst case \
of a mistake is cosmetic damage, a broken fixture, or simply no progress — no leak, fire, or shock risk.
- caution: A like-for-like swap or DISCONNECTION of an EXISTING water/electrical component at its \
EXISTING location (e.g., replacing a faucet, toilet, or outlet). A mistake has real cost or mild injury \
risk, but the worst case is a leak, a broken fixture, or a tripped breaker. Note: clearing a clog or \
routine cleaning is NOT caution — it is safe.
- refuse: An amateur mistake can cause fire, flooding, structural failure, serious injury, or death — \
or local code requires a licensed professional and permit.

CRITICAL RULES:
1. "Replacing/repairing an EXISTING" component at the same location = caution. "Adding NEW" wiring, a \
new circuit, a new outlet/switch location, or running new pipe = refuse. Same component, different tier.
2. ALL gas work (lines, appliances, shutoffs, gas smell) = refuse. No exceptions.
3. ANY wall removal/modification = refuse unless the user states a structural engineer already \
confirmed it is non-load-bearing.
4. Electrical panel / service-entrance / breaker work = refuse.
5. Water heater replacement = refuse (minor parts like an anode rod = caution).
6. Classify by what the repair ACTUALLY requires, not how the user frames it. "I just want to move the \
switch six inches" still requires new wiring = refuse.
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
TIER: <safe | caution | refuse>"""


def _parse_response(text: str) -> dict:
    """Pull the tier and reason out of the LLM's labeled-line response.

    Returns a dict with a validated tier, or falls back to "caution" if no
    recognized tier line is present.
    """
    tier = None
    reason = ""
    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith("tier:"):
            # Take everything after the colon, drop quotes/punctuation, lowercase.
            candidate = stripped.split(":", 1)[1].strip().strip('"\'`*.').lower()
            if candidate in VALID_TIERS:
                tier = candidate
        elif lowered.startswith("reason:"):
            reason = stripped.split(":", 1)[1].strip()

    if tier is None:
        return {
            "tier": _FALLBACK_TIER,
            "reason": "Could not parse a valid tier from the classifier response; "
            "defaulted to caution as a safe fallback.",
        }
    if not reason:
        reason = f"Classified as {tier}."
    return {"tier": tier, "reason": reason}


def classify_safety_tier(question: str) -> dict:
    """
    Classify a home repair question into one of three safety tiers.

    TODO — Milestone 1:

    Before writing any code, complete specs/classifier-spec.md. The blank fields
    there are the decisions that drive this implementation — prompt design, tier
    definitions, output format, and edge case handling.

    Your implementation should:
      1. Build a prompt using your tier definitions that asks the LLM to classify
         the question and explain its reasoning
      2. Send a single chat completion request (no tools, no history)
      3. Parse the tier and reason out of the raw response text
      4. Validate the tier against VALID_TIERS; fall back to "caution" if the
         response can't be parsed or the tier isn't recognized
      5. Return {"tier": ..., "reason": ...}

    Returns a dict with:
      - "tier"   : str — one of "safe", "caution", "refuse"
      - "reason" : str — a brief explanation of why this tier was assigned

    The three tiers:
      - "safe"    : routine, low-risk repairs most homeowners can handle safely
      - "caution" : doable with care, but mistakes have real cost or mild risk
      - "refuse"  : high-risk repairs that require a licensed professional —
                    mistakes can cause fire, flooding, injury, or structural damage
    """
    if not question or not question.strip():
        return {
            "tier": _FALLBACK_TIER,
            "reason": "No question provided; defaulted to caution as a safe fallback.",
        }

    try:
        completion = _client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f'Classify this home repair question:\n\n"{question.strip()}"'},
            ],
            temperature=0,  # deterministic — we want a consistent judgment, not creativity
        )
        raw = completion.choices[0].message.content
    except Exception as exc:  # network/API failure — fail closed
        return {
            "tier": _FALLBACK_TIER,
            "reason": f"Classifier request failed ({exc.__class__.__name__}); "
            "defaulted to caution as a safe fallback.",
        }

    return _parse_response(raw or "")
