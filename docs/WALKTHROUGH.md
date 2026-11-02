# Design walkthrough

## Overview

The project started as a notebook that ingested PDFs and web content, indexed chunks using Gemini embeddings and Chroma, and generated answers from retrieved context. The current repository provides an offline retrieval baseline and an optional Gemini pipeline, with source-linked evidence and reproducible evaluation. Retrieval, citation validity and missing-information handling are measured separately because retrieving a relevant document does not establish answer correctness.

## Design questions

1. Why use overlapping chunks? What evidence might be split at a boundary?
2. How does BM25 differ from semantic embeddings? Which questions expose lexical limits?
3. Why are document and query embedding task types different?
4. Why include the model and corpus hash in the embedding-cache key?
5. Why does a valid source ID and exact quote not prove semantic entailment?
6. How can a question mention a known machine but ask for an undocumented attribute?
7. Why does an offline quote-selection system have no measured LLM answer accuracy?
8. What changes if documents contain instructions telling the model to ignore its prompt?
9. What leaves the machine in Gemini mode? What stays local in offline mode?
10. Which limitations prevent calling this a production service?

## A useful next experiment

Run Gemini evaluation with your own API access, manually inspect all 18 cases, and compare its abstention decisions with the baseline. Keep the offline report unchanged as the baseline. Add unseen questions and documents before making generalisation claims. Do not tune thresholds on a test set and then present it as held-out evaluation.
