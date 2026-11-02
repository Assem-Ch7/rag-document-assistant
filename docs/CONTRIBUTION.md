# Contribution and provenance

## Original notebook supplied by Assem

Source: https://colab.research.google.com/drive/1mpTUM73m5Gd1kfeVuYwYafSqUmPhSAgS

Observed notebook components:

- PDF loading and live web document loading.
- Recursive character splitting, 500 characters with 50-character overlap.
- Gemini embeddings and a persistent Chroma store.
- Top-three retrieval and Gemini answer generation.
- A context-only prompt and an explicit missing-information response.
- LangSmith tracing configuration.

The supplied original corpus was not available. Saved notebook outputs cannot establish new evaluation results. The notebook is preserved as an output-free, metadata-cleaned historical reference, not the application's supported installation path. Some original dependencies were not installed in its first cell, and its preview embedding model is historical.

## Codex-assisted refactor

Created in this collaboration:

- An installable Python package and zero-install checkout runner.
- A deterministic offline lexical baseline, optional Gemini REST integration and embedding cache.
- Bounded local ingestion, stable chunk IDs and PDF page metadata.
- Structured claim validation requiring known source IDs and verbatim quotes.
- A local evidence-inspection UI and JSON API.
- A synthetic corpus, labelled diagnostic set, measurement code and failure analysis.
- Unit/integration tests, Docker configuration and CI definition.

The changes were not all present in Assem's original notebook. They should not be described as a previously deployed professional system or work completed without assistance.

## Before an interview

Assem should run the commands, inspect each reported failure, explain the distinction between BM25 and semantic retrieval, and make at least one reasoned improvement with a measured comparison. Record subsequent changes and results honestly in Git commits.
