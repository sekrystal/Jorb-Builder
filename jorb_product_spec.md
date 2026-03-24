# JORB Product Spec (v1)

## Core Definition

JORB is an autonomous opportunity intelligence system that helps users identify, prioritize, and act on the highest-probability job opportunities in real time.

It is not a job board, resume writer, or generic AI coach.

---

## Product Goal

Maximize:
- probability of interview
- speed to high-quality opportunity
- decision quality around where and when to apply

---

## System Architecture

### 1. User Input Layer (Structured Onboarding)

Users provide:
- resume
- prior experience
- skills / competencies
- optional LinkedIn data
- preferences (role type, location, etc.)

Output:
- structured candidate profile
- search parameters for discovery

This is NOT a coaching system.
This is parameter generation for the engine.

---

### 2. Opportunity Discovery Engine

Sources:
- Greenhouse
- Ashby
- Web discovery
- User-submitted job links

Output:
- normalized opportunities
- companies
- source metadata

---

### 3. Opportunity Intelligence Engine (CORE)

Each opportunity is evaluated for:

- freshness (new vs stale vs evergreen)
- hiring signal (active vs passive hiring)
- probability of response
- role relevance to user
- competition level (inferred)
- required strategy (referral, timing, etc.)

Output per job:
- score
- classification:
  - high priority
  - apply soon
  - low probability
  - do not apply
  - evergreen listing
- explanation

---

### 4. Strategy Layer

For high-quality opportunities, provide:

- apply now vs wait
- referral recommendation
- urgency signal
- positioning advice (high level, not content generation)

This is NOT cover letter generation.

---

### 5. Tracking Layer

Track:
- discovered
- viewed
- saved
- applied
- rejected

Purpose:
- build outcome dataset
- enable future learning

---

### 6. Learning Layer (Future)

Use:
- application outcomes
- user behavior

To improve:
- scoring
- filtering
- strategy recommendations

---

## Non-Goals (DO NOT BUILD)

- generic AI career coach
- resume rewriting engine
- cover letter generator
- chat-first UX
- generic “what career should I choose” flows

---

## Product Philosophy

JORB does not try to generate content.

JORB provides:
- decision intelligence
- prioritization
- timing
- probability

---

## Key Insight

Users can bring their own job listings.

JORB’s value is:
- evaluating
- ranking
- advising

NOT sourcing alone.

---

## Success Criteria

JORB is working if:

- top surfaced roles are genuinely high quality
- users avoid low-probability applications
- recommendations feel directionally correct
- system reflects real market conditions

---

## Human Feedback Points

The operator (Sam) will evaluate:

1. Top surfaced opportunities
2. Strategy recommendations
3. Filtering correctness
4. System drift

Builder should prioritize improving these areas.

---