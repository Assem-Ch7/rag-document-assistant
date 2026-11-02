# Measured offline evaluation

Measured on 2 November 2026. Raw per-question output: [reports/offline.json](../reports/offline.json).

## Setup

- Four hand-authored synthetic documents, eight chunks.
- Eighteen labelled diagnostic questions: eleven answerable, seven unanswerable.
- Chunk size 650 characters; overlap 80; top-k = 3.
- BM25 retrieval; evidence returned when a passage covers at least 45% of non-stopword query terms.
- No language model, embedding API, cloud deployment or original private notebook corpus was used in this run.
- Corpus and dataset hashes, runtime version and configuration are stored in the JSON report.

## Results

| Metric | Measured result | Interpretation |
| --- | ---: | --- |
| Mean gold-source recall@3 | 100% | Expected source documents were in the top three for answerable cases |
| Evidence passage hit@3 | 11/11 | At least one labelled evidence span was retrieved for each answerable question |
| MRR@3 | 1.00 | First matching labelled passage ranked first in this small set |
| Evidence returned for answerable questions | 10/11 | One paraphrase was rejected despite retrieving its relevant passage |
| Abstention on unanswerable questions | 3/7 | Four questions received excerpts despite missing requested information |
| Evidence/abstention decision accuracy | 13/18 | A diagnostic selection score, not generated-answer accuracy |
| Citation ID and exact-quote validity | 100% | Expected for verbatim evidence copied directly from retrieved chunks |
| Citation gold-source precision | 50% | Additional irrelevant/unsupported excerpts reduced relevance precision |
| Semantic faithfulness / human answer correctness | Not measured | Neither is inferred from valid citations or keyword matching |

These scores do **not** show that the assistant answers every question correctly. All documents and questions were authored for development. The set is small and not held out. Retrieval success is aided by lexical overlap and a small corpus.

## Observed failures

| Case | Observation | What it demonstrates |
| --- | --- | --- |
| a09: “silent for over two minutes” | Retrieved the runbook but abstained | Lexical coverage fails to connect paraphrases such as silence/staleness and two minutes/120 seconds |
| u03: pump purchase price | Returned pump excerpts without a price | Knowing the entity does not establish a missing attribute |
| u04: API rate limit | Returned API excerpts without a rate limit | Related document content is not an answer |
| u05: actuator voltage | Returned actuator excerpts without a voltage | Retrieval can match the right topic while lacking the requested fact |
| u06: threshold plus price | Returned evidence for a partially supported request | Multi-part questions require checking every requested component |

The instruction-attempt case was abstained on in this offline run. This is **not** evidence that the Gemini mode resists prompt injection: no model was invoked.

## Next comparison

Run `python run.py --mode gemini evaluate --output reports/live/gemini.json` with your own API access. Inspect whether semantic retrieval recovers a09 and whether the generation prompt correctly abstains on missing attributes and partial support. Report errors as well as successes. Then add unseen documents/questions before tuning thresholds.

The code validates source identity and exact quoted evidence. A claim can still misinterpret an authentic quote. Manual semantic review or separately validated entailment evaluation is required before reporting faithfulness.

## Reproduce

```bash
python run.py evaluate --output reports/offline.json
```

Deterministic retrieval/selection outcomes should match for the same source and dataset. Wall-clock timestamps and latency will differ. The report's latency excludes startup, corpus loading and index construction, and should not be compared with end-to-end API latency.
