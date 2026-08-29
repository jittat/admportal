# Semantic major search — plan

**Status: Phases 0–1 built and verified against the live API; the bake-off itself is blocked on
label review. Phases 2–7 not started.** This records the design
agreed in August 2026. The shipped search is [Major search](major-search.md); nothing semantic runs
in production. The eval set, its scoring, and the provider layer exist (Phases 0–1 below); the eval set already
serves as a regression net for the existing search. No model has been chosen: `eval_embeddings.py`
refuses to spend money while the Phase 0 labels are unreviewed.

## Goal

Extend `/majors/search/` so that after the exact matches it also shows *related* majors found by
embedding similarity — so that `หมอ` reaches `สพ.บ. สัตวแพทยศาสตร์`, or `เขียนโปรแกรม` reaches
`วท.บ. วิทยาการคอมพิวเตอร์`, neither of which any substring match can do.

Two sections, never interleaved. Exact-first is **structural**, not score-based:

```
ผลการค้นหา          ← today's find_major_cupt_codes, unchanged
สาขาที่เกี่ยวข้อง     ← embedding neighbours, excluding anything above
```

When the exact section is empty the related section carries the page, with wording to match. Every
existing gate still applies: `HIDE_CRITERIA` → 403, `ALLOW_SEARCH` → redirect, and related majors
are filtered by `major_detail_visible` exactly as exact ones are.

## Decisions already taken

| Decision | Choice | Why |
| --- | --- | --- |
| Embedding gateway | **OpenRouter** (`https://openrouter.ai/api/v1/embeddings`) | Existing credits, and one OpenAI-shaped endpoint reaches every candidate model. The four separate adapters originally planned collapse into one adapter with a model parameter. |
| Embedding model | **Decide by bake-off** | Thai quality is the discriminator and cannot be predicted from English benchmarks. Build the eval first, measure, then pin. |
| Local model option | **Dropped** (Aug 2026) | BGE-m3 running locally was the plan's answer to data egress. Decided against; every candidate is now hosted, so **egress is accepted rather than mitigated** — see Phase 4. |
| Runtime strategy | **Live query embedding** | Precomputed major→major neighbours are cheaper and have no runtime dependency, but only work when the query already matches a title — which excludes exactly the queries this feature exists for (`หมอ`, `อยากทำงานธนาคาร`). |

**The Claude API has no embeddings endpoint** (its surfaces are Messages, Batches, Files, Token
Counting, Models), which is why vectors come from OpenRouter. Claude still has a role here —
enriching each major's text before embedding (Phase 2) — but it does not produce the vectors, and
Phase 2 stays on the Anthropic API directly: the Batches API's 50% discount is what makes that step
cost ~$1.70.

## Phase 0 — the eval set

Comes first, because it decides everything after it. **Built.**

| File | What |
| --- | --- |
| `criteria/evaldata/major_search_eval.json` | 39 Thai queries with hand-drafted labels |
| `criteria/evaluation.py` | loader, recall@k, MRR, per-band report. No Django import at module scope, so `python -m doctest criteria/evaluation.py` runs standalone |
| `scripts/eval_baseline.py` | validates every label against the live corpus, then scores today's substring search |
| `criteria/tests.py` | `EvalSetTest`, `EvalMetricsTest` — fixture shape and metric behaviour |

### Bands

| Band | n | Example |
| --- | --- | --- |
| Near-exact | 7 | `วิศวกรรมคอมพิวเตอร์` |
| Colloquial | 7 | `หมอ`, `ครู`, `ทนาย` |
| Career-phrased | 8 | `อยากทำงานธนาคาร`, `เขียนโปรแกรม` |
| Field-level | 8 | `ดูแลสัตว์`, `สิ่งแวดล้อม`, `ทะเล` |
| Misspellings | 6 | `วิศวะคอม`, `เศรษฐสาสตร์`, `ภาษาอังกิด` |
| **Negative** | 3 | `หมอฟัน`, `ทันตแพทยศาสตร์`, `นาฏศิลป์` |

The negative band is an addition to the five bands originally planned. Phase 4 says a similarity
floor set too low is worse than not shipping the feature — that is a claim about precision, and
recall@5 and MRR cannot see it. These three queries have no correct answer anywhere in the corpus,
so anything returned above the floor is a false positive, counted and reported separately. They are
excluded from the recall and MRR averages.

### Labels are titles, not ids

`MajorCuptCode.id` is reassigned every cycle, so labels name titles. 290 rows are **159 distinct
titles**: a major can repeat across campuses, across programme types, and across `major_title`
(วิชาเอก) tracks — `ศษ.บ. สาขาวิชาศึกษาศาสตร์` alone carries eight. Left as rows, one popular title
could fill a whole top-5 by itself. A ranker under test must therefore collapse its row ranking to
titles, best rank winning; `evaluation.dedupe` does this.

### Metrics

`recall@5` is normalized by `min(len(expected), 5)`, not by `len(expected)`. Several queries have
six to eight correct answers, and no top-5 can hold them all — dividing by the label count would
score the breadth of the gold set rather than the quality of the ranking. `MRR` is the usual
reciprocal rank of the first correct title.

### Baseline

`python eval_baseline.py` from inside `scripts/`, against the 2570 corpus:

```
band                n   recall@5     MRR
----------------------------------------
near_exact          7      0.952   0.929
colloquial          7      0.143   0.071
career_phrased      8      0.042   0.125
field_level         8      0.375   0.625
misspelling         6      0.167   0.167
negative            3          -       -   (0.00 false positives/query)
----------------------------------------
OVERALL            36      0.333   0.389
```

**This is the number to beat.** It also states the shape of the opportunity precisely: substring
matching is already near-perfect on near-exact queries and near-useless on colloquial and
career-phrased ones — `หมอ`, `ครู`, `ทนาย`, `เขียนโปรแกรม`, `อยากทำงานธนาคาร`, `สร้างหุ่นยนต์` and
`ดูแลสัตว์` all return literally nothing today. The two colloquial queries it does answer
(`พยาบาล`, `สัตวแพทย์`) it answers by accident of substring overlap. Its perfect negative-band score
is likewise free: a retriever that returns nothing unless the letters match cannot produce a false
positive.

Its field-level MRR (0.625) is much higher than its field-level recall (0.375) — where a broad word
does appear in some titles it ranks them first, but it never reaches the sibling majors that do not
share the word. That gap is what the related section is for.

### The labels still need a human

**Every `reviewed` flag in the fixture is `false`, and `eval_baseline.py` prints a warning while any
remain so.** The labels were drafted by reading the 290 titles. That is enough to make them
plausible and to catch a title that no longer exists, but it is *not* validation: nobody has
confirmed what a Thai high-school student actually means by `หมอ` (drafted as แพทยศาสตร์ only — but
should สัตวแพทย์, พยาบาล and เภสัช sit in a related section for it?), by `ทะเล`, or by `วิศวะคอม`.

> A wrong gold set silently selects the wrong provider in Phase 1, and every later measurement
> inherits the error. **Do not run the bake-off against an unreviewed set.** Queries carrying a
> specific open question have a `note` field.

## Phase 1 — provider interface + bake-off

**Built, except the bake-off run itself.**

| File | What |
| --- | --- |
| `criteria/embeddings/base.py` | `EmbeddingProvider`, `FakeProvider`, `cosine`, `rank_by_similarity` (with the Phase 4 `floor`/`limit` knobs). Doctested standalone. |
| `criteria/embeddings/openrouter.py` | the one adapter: batching, retry, index-ordered responses, key from `OPENROUTER_API_KEY` then `.env` |
| `criteria/embeddings/corpus.py` | what gets embedded, and the seam Phase 2 enrichment slots into |
| `scripts/eval_embeddings.py` | the bake-off runner, with an on-disk vector cache |
| `criteria/tests.py` | `FakeProviderTest`, `VectorMathTest`, `OpenRouterProviderTest`, `ApiKeyTest` — 34 tests; every provider is built with a stub session, so nothing reaches the network |

**Built on `requests`** (`~=2.32`, added to `Pipfile` and `requirements.txt`). The provider holds one
`Session` for its lifetime: the corpus takes three batched calls and Phase 4 embeds a query per cache
miss, so connection reuse pays on both paths — against a ~1.5s runtime budget, a fresh TLS handshake
per call is a large share of it.

Retries are an explicit loop rather than an `HTTPAdapter`/urllib3 `Retry` policy. Both work; the loop
keeps the behaviour in one readable place, makes it directly testable against a stub session, and
lets a 429's `Retry-After` override the backoff (capped at 10s — a rate limiter may ask for longer
than a search page can wait).

`provider: {data_collection: "deny"}` is sent by default. It narrows onward use of the queries
without preventing the egress itself (Phase 4); if a model turns out to be unroutable under it,
turning it off is a deliberate one-line decision, not a silent default.

Vectors are cached to `data/embedding-cache/<model>.json` (git-ignored), keyed by model and text
hash, so re-running a model is free and adding a sixth candidate pays only for the sixth.

**Verified against the live API** (August 2026, `qwen/qwen3-embedding-8b`, one request, 5 texts):
the key resolves from `.env`, `data_collection: "deny"` routes without error, and the vectors are
sane — for the query `หมอ`, cosine ranked แพทยศาสตร์ (0.593) > สัตวแพทยศาสตร์ (0.406) >
พยาบาลศาสตร์ (0.335) > วิศวกรรมโยธา (0.311). Substring search returns *nothing* for that query. That
is the feature working in miniature, on the one query this whole plan is motivated by — and it is a
smoke test, not a measurement. The bake-off is still what decides anything.

### Design notes

- `criteria/embeddings/base.py` — a two-method interface: `embed_documents(list[str])` and
  `embed_query(str)`. Plus `FakeProvider`, returning deterministic vectors, so tests never touch the
  network.
- `criteria/embeddings/openrouter.py` — **one** adapter. OpenRouter's endpoint is OpenAI-shaped
  (`model`, `input` as a string or an array, optional `dimensions`), so a candidate is a model id,
  not another adapter. Responses are re-ordered by their `index` field rather than trusted in array
  order: mispairing 290 majors with 290 vectors would be completely silent.
- `scripts/eval_embeddings.py` — runs each configured model against Phase 0, prints a
  recall@5 / MRR table against the substring baseline. No similarity floor is applied during the
  bake-off: a floor would hide how far down the list a correct answer actually sits, which is the
  measurement Phase 4 needs to tune it.

Candidates, all multilingual, all trivially cheap at this corpus size — 290 short titles is a few
thousand tokens, so the entire bake-off costs well under a cent:

| Model id | $/M tokens | Notes |
| --- | --- | --- |
| `qwen/qwen3-embedding-8b` | 0.01 | strong multilingual candidate |
| `baai/bge-m3` | 0.01 | hosted, not local |
| `voyage/voyage-4` | 0.06 | 256–2048 dims |
| `openai/text-embedding-3-large` | 0.13 | |
| `google/gemini-embedding-2` | 0.20 | 128–3072 dims |

Thai has no word boundaries, so models diverge more here than their published benchmarks imply.

**Output: a model decision with numbers behind it.** Everything downstream pins to that choice.

**Do not run the bake-off until the Phase 0 labels are human-reviewed.** The whole point of the
table is to discriminate between models on Thai; an unreviewed gold set discriminates on nothing.
This is enforced, not just advised: `eval_embeddings.py` exits 2 rather than make an API call while
any label is unreviewed. `--fake` runs the whole pipeline on `FakeProvider` with no key and no
network — useful for the plumbing, meaningless as retrieval:

```
$ python eval_embeddings.py --fake
model: fake  (159 titles, 64 dims, 0 cached / 198 embedded, 0 requests)
OVERALL            36      0.018   0.039
negative            3   (5.00 false positives/query)
```

The five false positives per negative query are the expected result of ranking with no floor, and a
preview of exactly what Phase 4's floor is for.

## Phase 2 — Claude enrichment (eval-gated)

A title alone cannot match `หมอ` to `สพ.บ. สัตวแพทยศาสตร์` — no words overlap, so no vectors will
either. Before embedding, enrich each major with Claude: two or three Thai sentences on what the
major covers, its career outcomes, and the colloquial terms people use for it.

- `scripts/generate_major_descriptions.py` — `claude-opus-5` over all 290 majors through the
  **Batches API** (50% cost, no latency pressure). Stored on a new field.
- Cost: roughly 87K input / 116K output tokens ≈ **$3.30, or ~$1.70 batched** — once per admission
  cycle.
- **Gate:** run the Phase 0 eval with and without enrichment; keep it only if recall moves. Expect a
  large gain on the colloquial and career bands and near-zero on near-exact — but that is a
  prediction, not a result.

> These are model-written descriptions of real academic programmes on a public university site.
> Keep them **embedding-only and never rendered**: then a bad sentence costs one poor neighbour
> rather than a false public claim. Displaying them later would need review by the admissions office.

## Phase 3 — storage and generation

Two models in `criteria/models.py`, both with migrations:

| Model | Fields | Notes |
| --- | --- | --- |
| `MajorEmbedding` | `cupt_code` FK, `provider`, `model_name`, `dimensions`, `vector`, `source_text_hash`, `created_at` | Unique on (`cupt_code`, `provider`, `model_name`), so the bake-off can hold several sets side by side |
| `QueryEmbedding` | `normalized_query`, `provider`, `model_name`, `vector`, `created_at`, `hit_count` | The runtime cache. The key includes the model so changing models cannot serve stale vectors |

`vector` as a `BinaryField` of packed float32 (`struct.pack`), not JSON — ~4KB per major instead of
~20KB of text to parse per load. `source_text_hash` lets regeneration skip unchanged majors.

`scripts/generate_embeddings.py` embeds every major and upserts. Add it to
[data-import.md](data-import.md) as a post-import step: majors change every cycle.

**No vector database, no pgvector.** 290 vectors is a brute-force cosine, and `VectorIndex`
(`criteria/embeddings/base.py`) already does it: the corpus is unit-normalized once at construction,
so a search is a single float32 matrix-vector product. It lives in a module-level cache loaded once
per worker, invalidated by a version stamp.

The plan originally said to start without numpy. **numpy is now a dependency** (`~=2.2`), decided
after measuring — the pure-Python loop cost 182 ms per query at the corpus and dimensions actually in
use, which is the largest single item in a Phase 4 latency budget. Measured over 290 majors:

| dims | index build (once per worker) | search (per query) | pure Python was |
| --- | --- | --- | --- |
| 1024 | 10.1 ms | 0.076 ms | 42.9 ms |
| 4096 | 38.8 ms | 0.367 ms | 182.3 ms |

Ranking is no longer where the time goes. The whole latency budget now sits on the API call, which
makes the query cache — not the cosine — the thing that matters for speed.

## Phase 4 — runtime

`criteria/search.py` gains `find_related_major_cupt_codes(query)`:

1. Normalize the query, check `QueryEmbedding` — on a hit, **no API call at all**.
2. On a miss, call the provider with a hard timeout (~1.5s), then cache the vector.
3. Cosine against the in-process corpus; drop anything already in the exact results; apply a
   similarity floor and a top-K cap.

Both thresholds are tuned against Phase 0. **A floor set too low is worse than not shipping the
feature** — unrelated majors below the real results erode trust in the whole page.

**Failure is a degrade path, not an error path.** Provider down, timed out, key missing, or
`SEMANTIC_SEARCH_ENABLED=False` → the page renders exact results exactly as it does today. A search
page must never 500 because a vendor is having a bad afternoon.

Two exposures that do not exist today, both handled in this phase rather than deferred:

- **Cost.** A public endpoint calling a metered API per uncached query can be run up by a crawler.
  Mitigations: the query cache (most traffic is repeated phrases), a minimum and maximum query
  length, and a per-IP throttle **on cache misses only**.
- **Data egress.** Search queries leave the university's servers — for OpenRouter, and onward to
  whichever provider serves the chosen model. Innocuous in content, but a new disclosure.
  **Decided (Aug 2026): accepted.** The local-model option that would have avoided it is dropped, so
  there is no longer a technical mitigation on the table — only `provider: {data_collection: "deny"}`
  on the request, which narrows onward use without preventing the queries leaving. Worth stating
  plainly to whoever owns the site rather than shipping silently.

Settings: `SEMANTIC_SEARCH_ENABLED`, `EMBEDDING_MODEL` (an OpenRouter model id). The API key comes
from the **`OPENROUTER_API_KEY` environment variable**, not `settings_local.py` — `settings_local.py`
is rewritten each admission cycle, and the key must reach both the `scripts/` tools and the web
process.

## Phase 5 — view and templates

`build_search_results` already returns everything a related major needs, so it is reused wholesale.
The changes are additive: a second context key, a second section in
`criteria/templates/criteria/search.html`, and a small include wrapping
`search_result_major.html`. Related cards get a visual distinction and an honest label — these are
suggestions, not matches.

## Phase 6 — tests

All against `FakeProvider`; no test touches the network.

- Exact results always precede related ones, and never duplicate across the two sections.
- A cache hit produces zero provider calls; a miss populates the cache.
- Provider raising or timing out → page still renders exact results, HTTP 200.
- `SEMANTIC_SEARCH_ENABLED=False` → output byte-identical to today's.
- The similarity floor excludes a deliberately unrelated major.
- Related majors respect `major_detail_visible` the same way exact ones do.

## Phase 7 — docs and ops

- [major-search.md](major-search.md) — a semantic-search section: two-stage retrieval, the provider
  decision *and its eval numbers*, the degrade path.
- [data-import.md](data-import.md) — the regeneration step.
- `requirements.txt` / `Pipfile` — the chosen client.
- `CLAUDE.md` — the new commands.

## Deferred decisions

Recorded here so they are settled deliberately rather than by whatever the first working run
happened to do.

### Embedding dimensions and the choice of model

`qwen/qwen3-embedding-8b`, the current default, returns **4096 dimensions** — four times what this
plan's original storage and latency estimates assumed. After the numpy work, the CPU cost of that no
longer matters (0.367 ms per query). What remains is memory: **4.5 MB per worker** for the corpus
cache at 4096 dims, against 1.1 MB at 1024.

Three ways to reduce it if it ever matters: `qwen3-embedding` supports Matryoshka truncation through
the `dimensions` request parameter, which the adapter already passes through; a smaller model may
win the bake-off anyway; or the per-worker cache can be shared. **None of this should override
retrieval quality** — 4.5 MB is not a real constraint on this deployment. Let the bake-off numbers
pick the model, then revisit dimensions.

**Open until the Phase 1 bake-off runs.** `scripts/eval_embeddings.py` prints dimensions alongside
recall so the trade-off is visible at the moment the choice is made.

### The similarity floor

The one real observation from the smoke test: on bare titles, `หมอ` scored 0.593 against
แพทยศาสตร์ and 0.311 against วิศวกรรมโยธา — everything of interest sits inside a 0.28-wide band, with
พยาบาล (0.335) barely above civil engineering. Nothing is wrong with that; short unenriched titles
behave this way. But it means the Phase 4 floor is delicate, and it is evidence that Phase 2
enrichment is where the separation comes from rather than a nice-to-have. The negative band in the
eval set is what will tell you.

## Sequencing and risk

Phases 0–2 are throwaway-able. If the eval says no provider beats substring matching on the real
query mix, the work stops there having cost a script and a day — and the eval set remains valuable as
a regression net for the existing search. **Treat the Phase 1 bake-off table as an explicit go/no-go
before committing to Phases 3–7.**

The main risk: **quality here is unknowable in advance.** Thai embedding quality across these
providers, over 290 short academic titles, cannot be predicted from published benchmarks, and the
gap between "genuinely useful" and "confusing noise below the real results" lives entirely in numbers
that do not exist yet. That is why the eval comes first rather than last.
