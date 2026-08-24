# AGENTS.md — Coding Standards for smart-table-analyzer-demo

This repository is maintained as a modular, production-level codebase. Every file and change must follow the rules below.

## 1. Modular architecture

Design **deep modules**: a lot of behaviour behind a small interface, placed at a clean seam, testable through that interface.

Use the vocabulary from the `/codebase-design` skill exactly. Do not substitute these terms with "component", "service", "API", or "boundary":

- **Module** — any function, class, package, or tier-spanning slice with an interface and implementation.
- **Interface** — everything a caller must know: signatures, invariants, ordering, errors, config, performance.
- **Seam** — the place where a module's interface lives; alter behaviour without editing callers.
- **Adapter** — a concrete thing that satisfies an interface at a seam.
- **Depth** — large behaviour behind a small interface.
- **Leverage** — callers get more capability per unit of interface they learn.
- **Locality** — bugs, knowledge, and verification concentrate in one place.

### Principles

- Favour deep modules over shallow ones.
- Apply the deletion test: deleting a module should make complexity reappear in callers, not vanish.
- The interface is the test surface; test through the seam.
- One adapter means a hypothetical seam; two adapters make a real seam. Do not introduce seams for one-off abstractions.
- Accept dependencies, do not create them inside functions.
- Return results; avoid mutating inputs as side effects.
- Keep module surfaces small: fewer methods, simpler parameters.

## 2. Readability

- Keep logic flat; avoid deep nesting.
- Name after the domain concept (use `CONTEXT.md` and `/domain-modeling`).
- One file = one module responsibility.
- Do not add comments unless asked or unless the code itself cannot express the intent.
- Use the project's existing formatting and lint settings.
- Prefer explicit, boring code over clever abstractions.

## 3. File size

**No source file may exceed 200 lines.** If a file grows beyond 200 lines, split it along module seams before continuing. This rule applies to the file you are currently editing, including `AGENTS.md`.

## 4. Skill usage

Before any non-trivial work, invoke the most specific project skill:

- Designing or redesigning an interface → `/codebase-design`
- Reviewing or improving architecture → `/improve-codebase-architecture`
- Naming, sharpening, or adding domain terms → `/domain-modeling`

Use the skill vocabulary in all design discussions and keep `CONTEXT.md` current when domain decisions change.

## 5. Verification

- Run the project's type checker, linter, and test command before finishing.
- If you cannot find a verification command, ask the user.
- For architectural changes, confirm the module passes the deletion test and that tests exercise the interface, not implementation internals.

## 6. General

- Never commit secrets or credentials.
- Never rewrite history, force-push, or delete files unless explicitly asked.
- Update `AGENTS.md` and `CONTEXT.md` when architecture or domain decisions evolve.

## 7. Delegation

- For any non-trivial, self-contained, or multi-step work, always spawn a subagent instead of doing the work inline.
- Use `subagent_explore` for read-only research (runs on SWE-1.6 — cheapest).
- Use the custom `implementer` profile (`.devin/agents/implementer.md`) for all write work: edits, new files, test runs. It is pinned to `model: swe` (SWE-1.6) and costs far less than `subagent_general`.
- Only use `subagent_general` when the task genuinely requires the parent model's reasoning level and cannot be broken into a plan (main) + execution (implementer) split.
## 8. Prompt Engineering & Knowledge Base

- **Do not stuff business logic, rules, or constraints directly into LLM prompts** (e.g., `analysis_prompt.txt`).
- Maintain consistency by placing all domain rules, best practices, and constraints into the knowledge base runbooks (e.g., `knowledge/runbooks/`).
- The LLM should retrieve and apply rules dynamically via RAG. Prompts should remain structural and generic, focusing only on output format and general guidance.
