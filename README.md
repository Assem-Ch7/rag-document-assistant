# Grounded — Document Assistant

An inspectable document assistant developed from Assem Chebly's RAG notebook: local document ingestion, retrieval, source-linked evidence, an optional Gemini generation path, and a reproducible diagnostic evaluation.

**Try the offline demo without an API key.** It returns source excerpts, not a generated answer. Gemini mode adds semantic embeddings and generated claims with supporting quotes.

## Quick start

Python 3.11+ is required. From the repository root:

```bash
python run.py ask "What is the Aster PX100 vibration alert threshold?"
python run.py serve
```

Open **http://127.0.0.1:8765**. Stop the server with Ctrl+C. These commands require no pip installation and no external model calls.

The included documents describe fictional industrial systems. They are synthetic examples, not technical guidance for real equipment.

## What it does

| Capability | Offline demo | Gemini mode |
| --- | --- | --- |
| UTF-8 Markdown/text ingestion | Yes | Yes |
| Text-based PDF ingestion | Optional PDF dependency | Optional PDF dependency |
| Retrieval | BM25 lexical ranking | Gemini embeddings and cosine ranking |
| Response | Verbatim passages | Generated claims with evidence quotes |
| Source metadata | File, chunk ID, PDF page when available | Same |
| Missing information | Query-coverage heuristic | Model abstention, plus output validation |
| External API required | No | Yes; sends selected content to Google |
| Measured evaluation in this repository | Yes | Not yet run with a live API |

The app checks that each generated claim refers to a retrieved source and includes a verbatim quote from that source. **A valid quote is not proof that the claim follows from it.** Human review remains necessary.

## Architecture

```text
Local .md/.txt/.pdf documents
        ↓
Bounded loading → deterministic overlapping chunks → stable IDs + source metadata
        ↓
BM25 baseline OR cached Gemini embeddings + cosine similarity
        ↓
Top-k passages
        ↓
Verbatim evidence OR Gemini structured claims
        ↓
Validate citation IDs + exact support quotes → answer/evidence or abstention
        ↓
CLI / local web UI / per-question JSON evaluation report
```

The original notebook used LangChain, Chroma, Gemini and live web ingestion. This refactor keeps a cleaned notebook under `notebooks/` and uses a smaller inspectable implementation for reproducible evaluation. The current app does not scrape websites or use Chroma. This is a deliberate scope change, not a claim that those notebook dependencies were eliminated without trade-offs.

## Run with your own documents

```bash
# Optional: install the package and PDF parser in a virtual environment.
python -m venv .venv
# Activate .venv for your operating system, then:
python -m pip install -e ".[pdf]"
python run.py --corpus data/private ask "Your document question"
```

Put your own files in `data/private/` (ignored by Git). Markdown/text must be UTF-8. PDFs must contain extractable text; OCR is not implemented. The demo limits each document to 10 MiB and PDFs to 200 pages. Unsupported extensions are not ingested. Empty or unreadable corpora fail explicitly.

## Gemini RAG

Set `GEMINI_API_KEY` in your local shell. Do not paste it into source code or commit it. `.env.example` lists the supported variables; the Python app does not auto-load `.env` files.

```bash
# Bash example: enter the key without echoing it.
read -rsp "Gemini API key: " GEMINI_API_KEY
export GEMINI_API_KEY
python run.py --mode gemini ask "Which fields are required by the telemetry API?"
python run.py --mode gemini serve
python run.py --mode gemini evaluate --output reports/live/gemini.json
```

Defaults: `gemini-embedding-001` with 768 dimensions and `gemini-2.5-flash`. Model access and availability vary; override `RAG_EMBEDDING_MODEL` and `RAG_GENERATION_MODEL` if needed. The adapter targets Gemini's REST API. A corpus/model fingerprint controls the local embedding cache; changing the corpus creates a new cache entry. No API keys are stored there. Embeddings and document content may still be sensitive, so `.cache/` is ignored.

Gemini mode never silently substitutes offline output when an API request fails. Network/quota errors are explicit. The API adapter has mocked contract tests, but **no live Gemini result is reported as measured**.

## Docker

```bash
docker compose up --build
```

Open http://127.0.0.1:8765. The default container runs offline as a non-root user with a read-only filesystem. Python source is included directly; there are no pip downloads in the offline image build.

```bash
docker build -t grounded-rag .
docker run --rm grounded-rag evaluate --output /tmp/offline.json
```

For Gemini mode, copy `.env.example` to `.env`, enter your key locally, then run the container separately:

```bash
docker run --rm --env-file .env -p 127.0.0.1:8765:8765 grounded-rag \
  --mode gemini serve --host 0.0.0.0 --port 8765
```

The default image does not install the optional PDF parser. Docker engine startup, image build and container execution must be checked on a machine with a running Docker engine; they were not successfully executed during initial preparation.

## Evaluation

```bash
python run.py evaluate --output reports/offline.json
```

The labelled diagnostic set contains **18 questions: 11 answerable and 7 unanswerable**. It includes direct questions, paraphrases, French, multi-document questions, missing attributes, partial support and an instruction attempt.

Read [the measured results and failures](docs/EVALUATION.md). Reports contain each question, returned passages, citations, decisions, configuration and dataset/corpus hashes. Metrics distinguish retrieval recall, passage hits, abstention and citation checks. They do not report unmeasured semantic faithfulness as a perfect score.

This tiny hand-authored dataset is a development diagnostic over four synthetic documents, not an independent benchmark or evidence of production accuracy. Do not use its scores to claim performance on real company documents.

## Tests

```bash
# Bash
PYTHONPATH=src python -m unittest discover -s tests -v
# PowerShell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

Tests cover retrieval, chunking, citation rejection, missing credentials, mocked Gemini requests/cache behaviour and local HTTP handling. The PDF test skips if the optional parser is absent. CI runs offline checks and attempts a Docker build; a workflow file is not proof that CI has already passed.

## Contribution and provenance

Original notebook supplied by **[Assem Chebly](https://github.com/Assem-Ch7/)** during his AI4CI studies. The cleaned notebook retains source cells while removing outputs, execution history and personal runtime metadata. Its original private document corpus is not included.

The application structure, offline baseline, UI, tests, Docker setup and evaluation materials were created with **Codex-assisted implementation**. Assem should review the code, run Gemini/Docker validation, and be able to explain the design before presenting these additions as independently mastered skills. See [the contribution record](docs/CONTRIBUTION.md) and [interview walkthrough](docs/WALKTHROUGH.md).

This is an educational portfolio prototype, not a deployed company system. No original model training, autonomous agent, production deployment or real predictive-maintenance outcome is claimed. No repository-wide licence has been selected.
