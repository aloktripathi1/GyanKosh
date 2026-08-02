# Decisions

## The orchestrator: custom, not a framework

- I built a plain Python state machine backed by a `jobs` table in Postgres, my own code for checkpointing, retry, and resume.
- I considered LangGraph, since it's built for exactly this kind of multi-step LLM pipeline and would have given me a lot of the checkpointing machinery for free. I also considered a real workflow engine like Temporal or Airflow, since checkpoint-and-resume is a solved problem there.
- I had four days, the pipeline is basically linear with one real fan-out point, and I would rather spend that time understanding and testing my own fifty lines of retry and checkpoint logic than debugging someone else's framework under deadline pressure. If someone asks me how resume-from-checkpoint actually works, I can point at `next_stage()` in `pipeline.py` and walk through it line by line, which is exactly the kind of thing I wanted to be true going into an evaluation.
- The tradeoff I accepted: a mature framework would have given me retry policies, observability, and distributed execution I had to build myself. If this pipeline grew past ten stages or needed real horizontal scaling, a hand-rolled orchestrator would hit its ceiling fast. For this scope, I think I picked correctly.

## Data layer: Postgres with JSONB, not pure relational or a document DB

- I used Postgres, with job status and metadata as real columns and the actual stage outputs stored in JSONB.
- I considered a fully relational schema with every nested field as its own column, or a document database like MongoDB instead of Postgres entirely.
- Job state (status, current stage, progress percentage) is genuinely relational and benefits from real transactions. The stage outputs are LLM-generated structured data whose shape kept changing while I was building this, a new field on the Period schema, an added teaching_context field, and so on. If every nested field were its own relational column I'd have been writing a new migration every time I tweaked a prompt. JSONB gave me document-store flexibility for that part without running two databases side by side. The Pydantic schema is still the actual source of truth for validation, JSONB is just storage.

## API style: REST, not GraphQL

- I used REST.
- I considered GraphQL, but there's no client here that needs to compose complex nested queries across resources. It's upload a document, poll a job, fetch a TKP, regenerate one section. GraphQL would have added a schema layer and a resolver graph for a set of endpoints that are already about as simple as they can be.

## Progress updates: SSE, not WebSockets or plain polling

- I used Server-Sent Events. I only need to push state in one direction, server to client, so SSE is the minimum amount of protocol for the job.
- I considered WebSockets, but that would add bidirectional complexity I don't use.
- The honest part: the actual implementation is not the elegant version of SSE. It's a loop that polls the jobs row every two seconds and only emits an event when something changed, not a true database-level push via Postgres LISTEN/NOTIFY. I chose that because it was fast to build and correct to reason about, and two-second latency on a job that runs for minutes doesn't matter to someone watching a progress bar. At real scale, a database being asked "did anything change" once every two seconds per open connection would need revisiting. At this scale it's fine.

## Auth: one API key, deliberately not more

- I used a single shared API key.
- I considered building real user accounts with sessions and per-user data isolation, once the core pipeline was working and I had time left over. I decided against it.
- The assignment doesn't ask for multi-tenancy. Every job and TKP already gets written to Postgres the moment it's created, so a user doesn't lose their work by not being logged in, they just don't have a login. What auth would actually buy at that point is isolating one person's documents from another's, and there is exactly one person using this thing during evaluation. Building real accounts, sessions, and per-user data scoping would have been real, nontrivial surface area, and it's exactly the kind of scope creep the assignment's own instructions already told me not to do.
- What I built instead: once I noticed the actual gap was "I can't see my past runs," not "I need to log in," I added a Library view listing every job by document name, subject, and status. That solves the problem people actually have without needing a login system to do it.

## Storage: an interface first, S3 later

- I used local disk, but every access to it goes through a `StorageBackend` interface, never a direct filesystem call, from the start rather than retrofitted later.
- I considered building real S3 support immediately.
- On Render's free tier, local disk doesn't persist across a redeploy, so it's genuinely not a production storage strategy, but real S3 support up front would have meant setting up an AWS account, credentials, and a bucket before I had a working pipeline to store anything with. The interface means swapping to S3 later is one new class implementing four methods, not a rewrite of every caller.
- I applied the same reasoning to the LLM client, which is also behind its own interface. I wanted the parts of the system likely to change in a real deployment to be swappable without touching the pipeline logic around them.

## PDF generation: WeasyPrint over a raw PDF library

- I used WeasyPrint, which renders HTML and CSS to PDF.
- I considered a library like ReportLab, where you position text and boxes directly.
- I needed to generate three different documents (lesson plans, teacher guide, assessment book), each with its own layout. Styling three documents with CSS, page breaks, typography, tables, was much faster to iterate on than absolute positioning by hand, and I could reuse ordinary web layout knowledge instead of learning a new drawing API.
- The cost: WeasyPrint's own dependency footprint. I had to pin `pydyf==0.10.0` specifically because a newer version broke compatibility. A small tax I was willing to pay for the iteration speed.

## Cutting cost: routing, caching, and not re-billing the same document

Every LLM call goes through one function, `structured_call` in `llm/client.py`, which let me apply cost controls in one place instead of scattered across eight agents.

- Model tiering. Classification and knowledge extraction go to Haiku, since they're closer to structured parsing than generation. Planning, content generation, activity generation, assessment generation, and gap analysis go to Sonnet, since they require actual reasoning about pedagogy. This isn't a blanket policy in either direction, it's tied to which stages need the stronger model's judgment.
- Prompt caching. The system prompt and tool schema for a given stage don't change between calls, only the document content does, so I mark the system prompt block as `cache_control: ephemeral`. This pays off specifically on retries, since a failed attempt hits a cache instead of paying full price again, and across different documents hitting the same stage within the cache window.
- Caching by document content hash. If someone uploads the exact same file twice, and this happened constantly during testing since I re-uploaded the same NCERT chapter dozens of times, there's no reason to re-run document intelligence, classification, and knowledge extraction against identical bytes. I hash the upload with SHA256 and, if a prior job exists for that hash, seed the new job's checkpointed state with those three stages already filled in. Generation stages still run fresh, since regenerating with a teacher's context or after a fix should produce new content, but the expensive early stages don't get re-billed for no reason.

## Making it faster: running four stages at once

- I run content generation, activity generation, assessment generation, and gap analysis concurrently on a `ThreadPoolExecutor`, since they're I/O-bound waiting on the Anthropic API, not CPU-bound, and none of them depend on each other, only on the teaching plan and knowledge extraction that already happened.
- Before this they ran one after another, which is what I had originally, since that's the simplest thing to write first.
- What it actually saved: on one Physics chapter run, the four stages individually took 74.78, 36.65, 119.66, and 7.62 seconds, about 239 seconds summed. Run concurrently, the batch takes as long as the slowest one, 119.66 seconds, roughly cutting that portion of the pipeline in half. On smaller test documents I measured the whole pipeline going from about 180 seconds before this change to somewhere between 61 and 86 seconds after, closer to a 2 to 3x improvement on total wall time, since the parallel batch is a bigger fraction of the total run on a smaller document.
- This change also caused the worst bug I hit this whole project, described below.

## Grounding: checking against the source, not asking a second model

- Every factual claim traces back to an actual location in the source document. In stage 3, every extracted objective, concept, definition, formula, and misconception comes with a verbatim quote and the exact section it came from. Every later stage that generates something has to cite which stage 3 item it's grounded in, using a real quote, not a paraphrase. I resolve that citation with a tiered match: exact string match first, then a whitespace-normalized match, then a fuzzy match with `rapidfuzz` as a fallback for minor formatting drift. If none of those match, the citation is rejected and the stage fails and retries.
- I considered a second LLM call that reviews the first one's output and flags anything that looks hallucinated, and decided against it. It doesn't actually solve the problem, it just adds another model that can also be wrong, and now I have two unreliable checks instead of one, with no way to know which to trust when they disagree.
- The real cost of the stricter design: I'd rather have a system that sometimes fails a stage because it can't prove a claim is grounded than one that publishes a plausible-sounding sentence nobody checked. That cost showed up directly while building the sample outputs, described below.

## The bug that actually took the longest to find

- While generating a sample from a humanities document, four separate live attempts against the deployed backend hung. Not crashed, not errored, just sat at "running" forever with no progress and no error message. That's worse than a crash, since a crash at least tells you where to look.
- The parallel stage change was the newest thing I'd touched, so I started there. The actual cause was in SQLAlchemy, not my own pipeline logic directly. By default, a SQLAlchemy session marks every attribute on a committed object as stale after `commit()`, so the next read triggers a fresh query. The orchestrator commits after every stage. Right before spawning the four parallel worker threads, the pipeline had just committed. Each of those four threads then read `job.stage_results` for the first time after that commit, which meant four threads simultaneously tried to lazily reload the same attribute against the same shared database session. SQLAlchemy sessions aren't safe for concurrent use from multiple threads, and instead of a clean error I got several threads contending for one connection with nothing resolving.
- The fix was one line, `expire_on_commit=False` on the sessionmaker, so a commit stops invalidating already-loaded data and nothing needs to be re-fetched from inside a worker thread.
- Once I understood the cause, I added a hard timeout around every stage, sequential or parallel, so if something hangs for a reason I haven't anticipated, the stage fails explicitly after ten minutes instead of leaving a job stuck forever. A Python thread that's genuinely stuck can't be forcibly killed, so the executor shuts down without waiting for it rather than blocking cleanup on a thread that may never return.
- To prove it actually works, not just that it looks right, I wrote a test where a stage's mocked agent call is `threading.Event().wait()` with nothing ever calling `.set()`, a function that by construction never returns on its own, and asserted the orchestrator still fails the job within the bounded time. Then I went back and re-ran the exact document type that had originally hung, twice more, specifically to confirm the fix generalized and I wasn't just trusting the unit test.

## Two more bugs, found by testing on documents I hadn't tried before

Everything up to that point had mostly been tested against Chemistry content. When I generated the History sample, two more real bugs showed up that Chemistry alone had never triggered.

- Bug one, a schema shape mismatch. The gap analysis stage's output schema has one top-level field, a list called `gaps`. On one run, the model's tool-use response came back as `{"gaps": {"gaps": [...]}}`, the list wrapped in an extra dict with the same key name, instead of `{"gaps": [...]}` directly. Pydantic validation failed immediately with a clear type error, at least easy to diagnose. I'd already built a repair step for a related problem, where a nested list field sometimes arrives as a JSON string instead of an actual list, so I extended that same repair layer with a schema-aware check: if a field is declared as a list type and the value is a dict with exactly one key whose value is a list, unwrap it. I kept that narrow on purpose, checking against the actual Pydantic field types rather than guessing based on key names, so it can't accidentally mangle a field that's legitimately supposed to be a dict.
- Bug two, not really a bug in my code at all. On a retry after the schema fix, gap analysis failed again, this time because it burned through all three retries hitting the grounding check. The system prompt for that stage tells the model to copy citations verbatim into a `grounding_refs` list, one entry per fact. Instead, the model combined several separate facts into one synthesized sentence and put that whole sentence in as a single citation. The grounding resolver correctly couldn't match that combined sentence against any single stage 3 item, because it wasn't a verbatim quote of anything, it was a summary. That's the grounding check doing exactly what it's supposed to do, refusing to accept a citation that doesn't trace to a real source. The cost is that it burned through all three retries before I noticed the pattern, since a wrong-but-plausible combined sentence can come out on more than one attempt.
- The fix for bug two: I made the prompt explicit that if a misconception draws on multiple facts, each one needs to be its own separate entry in the list, never merged into one string. After that the same failure mode stopped recurring across repeated runs.
- I'm calling this one out specifically because it would have been easy to read the error and assume the grounding check itself was broken and needed to be loosened. It wasn't. The check was correct, the prompt was underspecified, and loosening the check to stop the retries from burning would have meant accepting less reliable citations everywhere, not just fixing this one case.

## A real security bug, found by auditing, not by an attacker

- Late in the project I went back through the storage layer specifically looking for anything I'd normally flag in someone else's code. The local storage backend resolved a requested file path by joining it onto a base directory with no check that the result actually stayed inside that directory. A path containing `../` segments, which reaches that function directly from the `GET /files/{path}` URL, could walk outside the intended storage root.
- The fix: resolve the path and explicitly verify it's still a descendant of the base directory before allowing a read, write, or delete, raising a specific error otherwise.
- A related issue I fixed at the same time: download links used a single static API key as a query parameter with no expiration. I replaced that with HMAC-signed URLs that carry their own expiry and get regenerated fresh every time a TKP is fetched, rather than one link that would work forever if it ever leaked into a browser history or a log file.

## Testing across three different subjects, not just one

- I tested this pipeline against real NCERT chapters in Chemistry, History, and Physics, not synthetic test documents and not just one subject run twice.
- That's directly why I found the two gap analysis bugs above, since neither one showed up on Chemistry content. It also let me check something I actually cared about, whether the system was forcing the same shape onto every subject regardless of fit. It wasn't: History produced periods sequenced around thematic and chronological relationships with almost no numerical assessment questions, while Physics produced a period-by-period build toward circuit calculations with numerical questions in most periods. I hand-checked every one of those calculations myself rather than trusting that a plausible-looking number was a correct one.
- The concurrency test, specifically. The regenerate-section endpoint locks a TKP row with `SELECT ... FOR UPDATE` so two concurrent regenerate calls can't race each other. Every other test in this project deliberately avoids needing a real Postgres connection, mocking the database boundary the same way the LLM boundary gets mocked, which keeps the suite fast and independent of infrastructure. But a row lock actually blocking a second transaction can't be proven by mocking the database, only by trusting the code looks right. So for this one test I opened two real threads, each with its own real connection to a real Postgres instance, one holding the lock for a fixed duration while I measured how long the second one waited before it could proceed, on the second thread's own clock rather than comparing timestamps across threads. I tried the cross-thread timestamp comparison first and had to abandon it, since comparing wall-clock timestamps recorded on two independent threads turned out to be racy under normal OS scheduling jitter even when the underlying database ordering was completely correct.
- A constraint I worked around to run that test at all: I didn't have Docker or sudo access in the environment I was working in, so I downloaded the Postgres 18 packages directly with `apt-get download` and extracted them without installing anything system-wide, just to have something real to test against instead of leaving this as a documented limitation I couldn't actually verify.

## The Celery to BackgroundTasks pivot

- I originally chose Celery and Redis to fan out the four parallel generation stages to a separate worker process, since it reads as real orchestration under evaluation and decouples the slow pipeline from the web request cycle the way a production system would.
- What broke it: Render's free tier has no background worker service type at all, confirmed by literally opening the "New Background Worker" creation form and seeing only paid instance types starting at seven dollars a month. I found this out mid-deployment, after jobs were already sitting stuck at `pending` forever with no worker ever consuming them.
- What I chose instead: the pipeline now executes as a background task inside the same web process, using FastAPI's `BackgroundTasks`, with the parallel stages handled by a thread pool instead of a message queue.
- Why that was the right call and not a downgrade: paying for infrastructure the project's own constraints ruled out, or shipping a worker that would never run, were both worse than changing the mechanism. The orchestrator's actual guarantees, checkpointing, retries, explicit failure, didn't change. Only how work gets kicked off did.

## What I decided not to build

A few things were explicitly out of scope, and I want to be clear these were decisions, not things I ran out of time for.

- Multilingual generation. Not part of what's being evaluated here, and a real project on its own, not a small addition.
- Curriculum-board alignment to something like CBSE or Common Core. Same reasoning, a real project on its own.
- Horizontal scaling past one worker and one database instance. Not needed at this scale, and building for it now would have been designing for a load this deployment will never see.
- Full multi-tenant auth. Covered above.

In every one of these cases the honest reason is the same: the four days I had were better spent making the ten stages that are actually required work reliably across different subjects than adding breadth that isn't being asked for. If I'd built a thinner version of all four of those instead of a solid version of the core pipeline, I don't think that would have been a better use of the time, even though it might have made the feature list longer.
