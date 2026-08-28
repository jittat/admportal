# Semantic major search — plan

**Status: planned, not implemented.** This records the design agreed in August 2026 so the work can
be picked up later. Nothing described here exists in the codebase yet; the shipped search is
[Major search](major-search.md).

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
| Embedding provider | **Decide by bake-off** | Thai quality is the discriminator and cannot be predicted from English benchmarks. Build the eval first, measure, then pin. |
| Runtime strategy | **Live query embedding** | Precomputed major→major neighbours are cheaper and have no runtime dependency, but only work when the query already matches a title — which excludes exactly the queries this feature exists for (`หมอ`, `อยากทำงานธนาคาร`). |

**The Claude API has no embeddings endpoint** (its surfaces are Messages, Batches, Files, Token
Counting, Models). Vectors must come from a separate provider or a local model. Claude still has a
role here — enriching each major's text before embedding (Phase 2) — but it does not produce the
vectors.

## Phase 0 — the eval set

Comes first, because it decides everything after it.

~30 Thai queries with hand-labelled expected majors, as a fixture
(`criteria/evaldata/major_search_eval.json`). Five bands:

| Band | Example |
| --- | --- |
| Near-exact | `วิศวกรรมคอมพิวเตอร์` |
| Colloquial | `หมอ`, `หมอฟัน` |
| Career-phrased | `อยากทำงานธนาคาร`, `เขียนโปรแกรม` |
| Field-level | `ดูแลสัตว์`, `สิ่งแวดล้อม` |
| Misspellings | — |

Metrics: **recall@5** and **MRR**.

> The queries can be drafted from the 290 titles, but the labels **must be validated by someone who
> knows what a Thai high-school student means by a given phrase**. A wrong gold set silently selects
> the wrong provider, and every later measurement inherits the error.

## Phase 1 — provider interface + bake-off

- `criteria/embeddings/base.py` — a two-method interface: `embed_documents(list[str])` and
  `embed_query(str)`. Plus `FakeProvider`, returning deterministic vectors, so tests never touch the
  network.
- One adapter per candidate, ~30 lines each: **Voyage**, **OpenAI**, **Cohere**, and **BGE-m3 local**
  as the no-API baseline.
- `scripts/eval_embeddings.py` — runs each configured provider against Phase 0, prints a
  recall@5 / MRR table.

Thai has no word boundaries, so providers diverge more here than their published benchmarks imply.

**Output: a provider decision with numbers behind it.** Everything downstream pins to that choice.

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

**No vector database, no pgvector.** 290 vectors is a brute-force cosine — ~300K multiply-adds, a few
tens of milliseconds in pure Python. The corpus lives in a module-level cache loaded once per worker
(~2.4MB), invalidated by a version stamp. numpy would be faster but is not currently a dependency;
start without it.

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
- **Data egress.** Search queries would leave the university's servers for a third party. Innocuous
  in content, but it is a new disclosure and should be a deliberate decision, not a side effect. It
  is also the strongest argument for the local BGE-m3 option if it holds up in the bake-off.

Settings: `SEMANTIC_SEARCH_ENABLED`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`. The API key comes from
an **environment variable**, not `settings_local.py`.

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

## Sequencing and risk

Phases 0–2 are throwaway-able. If the eval says no provider beats substring matching on the real
query mix, the work stops there having cost a script and a day — and the eval set remains valuable as
a regression net for the existing search. **Treat the Phase 1 bake-off table as an explicit go/no-go
before committing to Phases 3–7.**

The main risk: **quality here is unknowable in advance.** Thai embedding quality across these
providers, over 290 short academic titles, cannot be predicted from published benchmarks, and the
gap between "genuinely useful" and "confusing noise below the real results" lives entirely in numbers
that do not exist yet. That is why the eval comes first rather than last.
