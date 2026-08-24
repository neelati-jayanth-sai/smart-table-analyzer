# Investigation Harness — MVP Build Reference

**Scope:** This document is self-contained. It includes enough background, mechanism detail, and rationale to be read and acted on entirely on its own — no other document is required to understand or build from it.

---

## 1. Background: What This Is and Why It Exists

Before this project, there was a deterministic health-scoring calculator for Apache Iceberg tables: six weighted dimensions, a fixed formula, no AI anywhere in it. Given a table, it produces a single number. What it never provided is an explanation — *why* a table scores the way it does — or a concrete fix. Getting from "this table scored 42" to an actual remediation has always meant an engineer manually pulling metrics, writing ad-hoc SQL, and forming a hypothesis by hand: an hour-plus of work, per table, repeated every time a table needs attention.

The Investigation Harness exists to replace that manual step with an AI system that investigates a table the way an experienced engineer would: adaptively, using its own read-only SQL, grounded in a curated body of knowledge about this platform and this team's own practice — producing a report where every claim traces back to something it actually queried or fetched, never an unbacked assertion.

**The core bet being tested:** adaptive investigation, grounded in curated domain knowledge and with evidence enforced mechanically, produces more trustworthy and more useful table diagnostics than the static score alone. This document describes the smallest version of the system that can honestly test that bet — the MVP.

**What the MVP does not touch:** the original scoring calculator's formula is frozen. Nothing in this build modifies it, reruns it differently, or second-guesses its output. The MVP only adds explanation on top of a number that already exists and is trusted as-is.

---

## 2. What Gets Built

One operator points the system at one Apache Iceberg table. The existing scoring function computes that table's health once. An adaptive Investigator — a self-hosted language model — then examines the table with its own read-only SQL, grounds every check in a curated knowledge base, and produces one report where every claim traces to something it actually queried or fetched. A human reads that report and decides what to do. Nothing executes automatically.

One investigation domain (table layout — partitioning, file sizing, sort order, skew, predicate alignment), one table, one report. That's the entire MVP.

---

## 3. The One Rule Governing This Build

Build only what's specified in this document. Two richer mechanisms were designed in real detail during architecture and deliberately left out of MVP — not because they were wrong, but because nothing had yet demonstrated the system needs them:

- **A richer Claim Validator.** The MVP's Claim Validator (§7, step 8) only checks that a claim points to something real. A fuller version would additionally type each claim — a plain observation vs. a comparison vs. something built on more than one piece of evidence — and add a content-matching stage that catches a claim citing a real, existing piece of evidence while still misstating what that evidence actually says. That failure mode — a correct citation attached to a wrong interpretation — is not caught by the simple version.
- **A formal score-ranked check menu.** The MVP shows the Investigator the baseline score as informal context (§7, step 6) and lets it decide what to check on its own judgment. A fuller version would require an explicit, formal mapping between the score's six scored dimensions and the investigation's checks, and use that mapping to rank what gets checked first, rather than leaving the ordering to judgment.

Both are real, well-reasoned designs, not shortcuts taken for lack of a better idea. Neither is built in MVP. The trigger for building either is a real, observed failure in real output — a report where the simple Claim Validator lets through a claim that misstates its evidence, or a report where the Investigator visibly wastes its check budget on a low-value area while an obviously worse one goes unexamined. A hypothetical version of either failure, however plausible, is not the trigger. If either failure shows up in a real report once MVP is running, that's the point to build the fuller version — not before.

---

## 4. Scope Boundary

**In scope:**
- One table, manually specified by the operator.
- The knowledge base (three trees — see §5).
- The existing scoring function, invoked once, against that one table only.
- A local SQLite database for the run's trail, findings, baseline score, and knowledge index.
- One adaptive Investigator, using free-form, validated, read-only SQL.
- A read-only database credential as the enforced safety boundary.
- Mechanical, minimal Claim Validation (the simple version — see §3).
- A basic query timeout and snapshot pinning.
- List-then-fetch knowledge retrieval (see §5).
- Structural trail compaction, a per-check retry bound of three, and a deliberately generous whole-investigation check bound.
- One human-reviewed report. Nothing executes automatically.

**Explicitly not in this build:**
- Anything that writes to, alters, or executes against the live table.
- Applying the scoring function across a fleet of tables rather than the one selected.
- Verifying that a suggestion actually works by testing it on a disposable copy of the table.
- Any investigation domain beyond layout (e.g., write-path behavior, table lifecycle/maintenance).
- More than one table or query running concurrently.
- Retry-on-claim-failure, and any query-safety layer beyond the basic timeout.
- Human escalation on an unresolved check, expert review of escalated answers, or a knowledge base that grows from that review.
- The richer Claim Validator and the formal score-ranked check menu (§3).

---

## 5. The Knowledge Base

This is the component that makes the Investigator's reasoning specific to this platform and team, rather than generic advice any model would give about any Iceberg table anywhere. A model can already write SQL and reason in general terms about database layout — that's baked into its training. What it can't know on its own is what this specific platform does differently, what this team has already learned the hard way, and what conventions the team has settled on. The knowledge base supplies exactly that.

**Structure — three separate trees, not one, and not a vector database:**

| Tree | Contains | Trust level | How it's cited in a report |
|---|---|---|---|
| `iceberg/` | Public Apache Iceberg facts — partition transforms, file formats, how manifests work | High | Cited directly and confidently |
| `iomete/` | Internal platform knowledge — quirks and limitations specific to this platform, not in any public documentation | Medium | Cited, but explicitly hedged |
| `runbooks/` | This team's own settled operating conventions | Team-authored | Cited as team practice |

They're kept separate, not merged, because they carry different trust levels — collapsing them would make it impossible for a report to distinguish "settled public fact" from "our own internal convention," a distinction that matters when deciding how much weight to give a claim.

**Retrieval — list, then fetch, never a guessed address.** The Investigator retrieves knowledge in two steps. First, a **list** call returns the topic paths available under a tree (or a filtered subset), each with a one-line description — nothing more. From that list, the Investigator picks the exact path relevant to the check at hand and issues a **fetch** for that one path, returning the full current text of that entry only. This exists so the Investigator never guesses a path from memory — a plausible-looking but wrong guess would silently return nothing, with no way to tell "no such knowledge exists" from "you asked for the wrong thing." Listing first removes that ambiguity, and keeps working context small: a list call costs a small, predictable amount however large the knowledge base grows, since it never returns full entry text.

**Versioning.** Every entry carries a version number; old versions are never deleted or overwritten. Every report records exactly which version of which entry it consulted, so a report stays fully explainable months later even after the knowledge underneath it has since changed.

**Lifecycle.** During MVP testing, the knowledge base is a mutable working document — entries get corrected and restructured directly as testing reveals gaps. It stays this way through MVP; freezing it into a permanent, append-only baseline happens later, once testing has actually validated the approach (see §9).

**Where it lives.** The authored content is reviewable text files, one per entry — the natural home for something a person writes and revises like documentation. A lightweight index (topic path → current version) lives in the same local SQLite database used for everything else in this build.

---

## 6. The Baseline Score, and How the Investigator Uses It

The existing scoring calculator produces a single overall health score, computed across six weighted dimensions. The specific dimension definitions and weights belong to that pre-existing tool — this document doesn't define or modify them; they're a fixed external input.

In MVP, the calculator runs once per investigation, against the one selected table, before the Investigator starts. Its six-dimension breakdown is shown to the Investigator as context — not a required checklist, not a formal ranking it must follow. The Investigator decides for itself what to check and in what order; the score informs that judgment without scripting it.

**One hard boundary, kept deliberately simple: the score may inform judgment, but it may never be cited as evidence.** A claim in the final report still needs its own executed query or fetched knowledge entry behind it (§7, step 8). "The score looked bad here" is why the Investigator looked — never why a claim passes validation.

---

## 7. Build Order

The order below follows dependency — what each step actually needs to exist first — not any particular filing order. Five stages.

### Stage 0 — Start now, runs in parallel with everything else

**0a. Resolve the model question.**
Nothing from Stage 4 onward can be honestly tested until a specific self-hosted model is chosen and baseline-tested — specifically on a long, many-check investigation, not just short-task tool use, since reasoning quality over a long working context is a distinct question from short-task competence. gpt-oss-120b (131K token context) is the current candidate under consideration. This doesn't block Stages 1–3, but it blocks the Investigator, so run it in parallel with infrastructure work rather than after.

**0b. Start authoring the knowledge base.**
This is real writing, not configuration, and it's the single largest risk to report quality — the Investigator's entire differentiation from a generic model with database access depends on it (§5). It has the longest lead time of anything in this build, so it starts on day one. The retrieval *mechanism* is built in Stage 3; the *content* needs to already exist, at least partially, before Stage 4 can be meaningfully tested.

---

### Stage 1 — Deterministic foundation
*No model, no knowledge base needed yet — infrastructure and integration only.*

**1. Read-only credential.**
A database role incapable of writing, altering, or deleting anything, enforced by the database itself. This is the actual safety boundary everything downstream assumes holds — not a prompt instruction, a real permission.

**2. Local SQLite schema.**
One local file, holding: the run's trail (queries, results, knowledge entries consulted), the baseline score, and the knowledge-tree index (topic path → current version). Build this before anything needs to write to it.

**3. Scoring function integration.**
The scoring calculator already exists and is frozen — this step is only the wrapper that invokes it against the single selected table and writes the result into the schema from step 2, as the run's baseline. No model involved; fully testable in isolation.

---

### Stage 2 — Safety-bounded query execution
*Depends on Stage 1's credential.*

**4. Query Workbench.**
Validates that every proposed query is a single, valid read-only `SELECT` before it's allowed through the credential from step 1. Also where the basic query timeout and snapshot pinning belong — pinning the investigation to one Iceberg snapshot for its duration, so every query within one run sees an identical, consistent view of the table even if it's written to elsewhere during the run. Fully testable with hand-written test queries — doesn't need the Investigator to exist yet.

---

### Stage 3 — Knowledge base mechanism
*Depends on Stage 1's SQLite schema. Content authoring (0b) should be underway by the time this is built, so the mechanism has something real to retrieve.*

**5. List-then-fetch retrieval.**
The two-call mechanism described in §5: list (paths + one-line descriptions) and fetch (one confirmed path's full text). The index lives in the SQLite schema from step 2. Build against whatever content exists at the time — it doesn't need to be complete, just real.

---

### Stage 4 — The adaptive core
*Depends on Stages 1–3, and on Stage 0a being resolved. First point the model actually runs.*

**6. Investigator loop.**
The adaptive loop: see the baseline score's six-dimension breakdown as context (§6), decide what to check, retrieve the relevant knowledge entry (Stage 3), write a query, run it through the Query Workbench (Stage 2), reason over the result, decide the next step. Two bounds apply from the start:
- **A per-check retry bound of three.** A query still invalid after three attempts gets that check marked "could not be verified" — an explicit, visible gap in the eventual report, not a silently shorter one.
- **A whole-investigation check bound.** Ships as a deliberately generous placeholder, not a tuned number, guaranteeing the run terminates regardless of what else happens.

**7. Trail compaction.**
Once a check completes, what stays in the Investigator's working context is a small, fixed record — check number, question, exact result value (copied, not reworded), one-line verdict, short rationale — never a generative paraphrase. Full detail (the full query, full result, full reasoning) stays in the SQLite trail, fetched back only if genuinely needed later. This matters because a paraphrase that quietly drifts from what a result actually said is functionally the same problem the Claim Validator exists to catch — cheaper to prevent upstream than to catch downstream. Build this alongside step 6, not after: an investigation long enough to need compaction is also long enough to need it correct from the first real test.

---

### Stage 5 — Trust and output
*Depends on Stage 4 producing at least one finding with evidence IDs attached.*

**8. Claim Validator.**
The minimal mechanism: every claim declares one or more evidence IDs (an executed query, a fetched knowledge entry, or both); the validator checks each ID actually corresponds to something real from this run. No ID, or a fake one, and the claim is dropped and logged — never silently included, and the resulting gap is stated in the report, not hidden. This is the entire mechanism for MVP; see §3 for what a fuller version would add and why it isn't built yet.

**9. Report assembly.**
Every finding is written to follow a fixed shape: current state, the observed evidence behind it, the gap being described, alternatives considered, and a recommendation that follows from the evidence — never a recommendation the evidence doesn't actually support. Where a real problem is confirmed but no confident fix exists, the report says exactly that, rather than manufacturing a suggestion for the sake of a tidier ending. This step assembles validated findings, the baseline score, and the specific knowledge versions consulted into that shape, and hands the result to a human. Nothing here executes anything.

**10. First end-to-end run.**
Wire steps 1–9 together against one real table. This is the first point every piece of the MVP's core claim — adaptive, grounded, evidence-enforced — gets tested together rather than in isolation. Its output is the actual test of the core bet from §1, and the first real input to the discipline in §3: only what this run actually shows should justify adding anything back.

---

## 8. Build-Order Diagram

```text
STAGE 0 (parallel, starts day one)
  Resolve model choice              Start authoring knowledge base content
        |                                        |
        |                                        v
        |                          STAGE 3: List-then-fetch retrieval
        |                          (needs Stage 1's SQLite schema)
        |                                        ^
        v                                        |
STAGE 1: Read-only credential -> SQLite schema -> Scoring function integration
        |
        v
STAGE 2: Query Workbench (validation, timeout, snapshot pinning)
        |
        +--------------------+---------------------+
                              v
        STAGE 4: Investigator loop (needs model choice resolved,
                  Stage 2's Workbench, Stage 3's retrieval)
                              |
                              v
                  Trail compaction (built alongside the loop)
                              |
                              v
        STAGE 5: Claim Validator -> Report assembly -> First real run
```

---

## 9. Where Things Stand Going Into This Build

**Already settled — not open questions:**
- The knowledge base is core to MVP, not an optional add-on, and follows the mutable-then-frozen lifecycle described in §5.
- The Claim Validator's MVP mechanism is the simple evidence-ID check in §7, step 8. The richer version in §3 is a deferred future upgrade with a stated trigger, not an unresolved design question.

**Still genuinely open, and what each one gates:**

| Gates | Open question |
|---|---|
| Stage 4, step 6 (Investigator loop) | Which self-hosted model executes the Investigator, and whether it's actually competent at long, many-check investigations, is untested. gpt-oss-120b is the current candidate; a baseline test specifically on a long investigation — not just short-task tool use — needs to happen before this stage is trusted. |
| Stage 4, step 6 (Investigator loop) | The whole-investigation check bound ships as a placeholder. The real value depends on real runs — don't hand-tune it now. |
| Stage 4, step 7 (trail compaction) | The general shape of a compacted record is settled (§7); exactly how much the rationale field needs to hold to keep an eventual report coherent is untested until a real run produces one. |
| Stage 4, step 6 (Investigator loop) | Whether showing the score as informal context is enough, or the Investigator will need the formal ranked-check-menu described in §3, is unresolved — watch real runs for bad prioritization before building that fuller mechanism. |
| Stage 5, step 8 (Claim Validator) | Two claim types the simple evidence-ID check can't handle: a *relational* claim (connecting two already-established facts to each other) and a *recommendation* (a synthesis over evidence that isn't itself traceable to one query result). Neither has an identified fix yet — watch real reports for this before designing anything. |
| Not required before this build | What specifically counts as "testing has validated the approach" — the trigger to freeze the knowledge base into its permanent, append-only state — isn't defined yet. Not needed until after this build produces real runs to learn from. |

---

## 10. Beyond This Document

Two further phases are anticipated beyond MVP: a verification step that tests a suggestion on a disposable copy of the table before showing it to anyone, and additional investigation domains beyond table layout. Neither begins until this MVP has been built, run, and shown value — neither is designed further in this document, since its scope is deliberately limited to the MVP described above.
