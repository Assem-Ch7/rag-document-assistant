# Project evolution

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

## Application refactor

The runnable application adds:

- An installable Python package and zero-install checkout runner.
- A deterministic offline lexical baseline, optional Gemini REST integration and embedding cache.
- Bounded local ingestion, stable chunk IDs and PDF page metadata.
- Structured claim validation requiring known source IDs and verbatim quotes.
- A local evidence-inspection UI and JSON API.
- A synthetic corpus, labelled diagnostic set, measurement code and failure analysis.
- Unit/integration tests, Docker configuration and CI definition.

## Evaluation status

The offline evaluation and tests have been executed. Docker build and container evaluation passed in GitHub CI. Live Gemini evaluation remains a separate next experiment; the current report documents the baseline results and observed failures.
