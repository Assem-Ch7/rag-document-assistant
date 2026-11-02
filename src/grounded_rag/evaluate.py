"""A small labelled diagnostic evaluation, not a general benchmark."""

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time

from .core import Assistant, corpus_hash


def evaluate(chunks, dataset_path, output, mode='offline', k=3, min_coverage=.45):
    raw = Path(dataset_path).read_bytes()
    cases = json.loads(raw)
    if not isinstance(cases, list) or not cases:
        raise ValueError('Evaluation dataset must be a non-empty JSON list')
    seen = set()
    for case in cases:
        if (not isinstance(case, dict) or not isinstance(case.get('id'), str) or case['id'] in seen or
                not isinstance(case.get('question'), str) or not isinstance(case.get('answerable'), bool) or
                not isinstance(case.get('category'), str) or not isinstance(case.get('relevant_sources'), list) or
                not isinstance(case.get('evidence_spans'), list)):
            raise ValueError('Invalid or duplicate evaluation case')
        seen.add(case['id'])
        if case['answerable'] and (not case['relevant_sources'] or not case['evidence_spans']):
            raise ValueError('Answerable cases require gold sources and evidence spans')
    if not any(c['answerable'] for c in cases) or not any(not c['answerable'] for c in cases):
        raise ValueError('Include both answerable and unanswerable cases to measure abstention')
    assistant = Assistant(chunks, mode, k, min_coverage)
    outcomes = []
    for case in cases:
        start = time.perf_counter()
        result = assistant.ask(case['question'])
        latency = 1000 * (time.perf_counter() - start)
        relevant = set(case['relevant_sources'])
        ranked = result['sources']
        recalled = {s['source'] for s in ranked}.intersection(relevant)
        # Passage hit requires both the expected file and the labelled evidence span.
        ranks = [i + 1 for i, s in enumerate(ranked) if s['source'] in relevant and
                 any(span.lower() in s['text'].lower() for span in case.get('evidence_spans', []))]
        refs = {s['id']: s for s in ranked}
        citations = [e for claim in result['claims'] for e in claim['evidence']]
        valid = sum(e['source_id'] in refs and e['quote'] in refs[e['source_id']]['text'] for e in citations)
        correct_source = sum(e['source_id'] in refs and refs[e['source_id']]['source'] in relevant for e in citations)
        returned = result['status'] != 'abstained'
        text = ' '.join(c['text'] for c in result['claims']).lower()
        # Keyword presence is a diagnostic only; it does not establish answer correctness.
        keywords = case.get('answer_keywords', [])
        proxy = all(term.lower() in text for term in keywords) if keywords else None
        outcomes.append({'id': case['id'], 'category': case['category'],
                         'expected_answerable': case['answerable'],
                         'retrieval_source_recall': len(recalled) / len(relevant) if relevant else None,
                         'passage_hit': bool(ranks) if relevant else None,
                         'reciprocal_rank': 1 / min(ranks) if ranks else 0,
                         'decision_correct': returned == case['answerable'],
                         'keyword_presence_proxy': proxy, 'citation_count': len(citations),
                         'valid_citations': valid, 'gold_source_citations': correct_source,
                         'latency_ms': round(latency, 3), 'response': result})
    answerable = [o for o in outcomes if o['expected_answerable']]
    absent = [o for o in outcomes if not o['expected_answerable']]
    count = sum(o['citation_count'] for o in outcomes)
    report = {'run_at_utc': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
              'mode': mode, 'retriever': 'BM25' if mode == 'offline' else 'Gemini embeddings + cosine',
              'generation': 'none: verbatim evidence only' if mode == 'offline' else assistant.provider.model,
              'embedding_model': None if mode == 'offline' else assistant.provider.embedding_model,
              'config': {'k': k, 'chunk_size': 650, 'overlap': 80, 'min_query_coverage_offline': min_coverage},
              'corpus_sha256': corpus_hash(chunks), 'dataset_sha256': hashlib.sha256(raw).hexdigest(),
              'documents': len({c.source for c in chunks}), 'chunks': len(chunks), 'cases': len(cases),
              'metrics': {
                  'source_recall_at_k': statistics.mean(o['retrieval_source_recall'] for o in answerable),
                  'passage_hit_at_k': statistics.mean(o['passage_hit'] for o in answerable),
                  'mrr_at_k': statistics.mean(o['reciprocal_rank'] for o in answerable),
                  'answerable_evidence_or_answer_rate': statistics.mean(o['response']['status'] != 'abstained' for o in answerable),
                  'unanswerable_abstention_rate': statistics.mean(o['response']['status'] == 'abstained' for o in absent),
                  'decision_accuracy': statistics.mean(o['decision_correct'] for o in outcomes),
                  'citation_id_and_quote_validity': sum(o['valid_citations'] for o in outcomes) / count if count else None,
                  'citation_gold_source_precision': sum(o['gold_source_citations'] for o in outcomes) / count if count else None,
                  'mean_query_latency_ms': statistics.mean(o['latency_ms'] for o in outcomes),
                  'semantic_faithfulness': None, 'human_answer_correctness': None,
              }, 'outcomes': outcomes}
    dest = Path(output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return report
