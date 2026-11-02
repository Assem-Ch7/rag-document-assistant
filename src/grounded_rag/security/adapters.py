"""In-process corpus experiments and a bounded loopback-only HTTP adapter."""

from dataclasses import asdict
import json
from pathlib import Path
import shutil
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from ..core import Assistant, BM25, corpus_hash, load_corpus, validate_claims
from ..gemini import Gemini
from .cases import filter_trusted


class AdapterError(RuntimeError):
    pass


class RecordingGemini(Gemini):
    def __init__(self, cache_dir, canary):
        super().__init__(cache_dir=cache_dir, test_canary=canary)
        self.last_generated = None

    def generate(self, question, hits):
        self.last_generated = super().generate(question, hits)
        return self.last_generated


class InProcessAdapter:
    name = 'in_process'

    def __init__(self, corpus, manifest, mode='offline', k=3, cache_dir='.cache/security'):
        self.corpus = Path(corpus).resolve()
        self.manifest, self.mode, self.k = manifest, mode, k
        self.cache_dir = str(Path(cache_dir).resolve())
        self.original_chunks = load_corpus(self.corpus)
        self.original_hash = corpus_hash(self.original_chunks)

    def run(self, case, configuration, scope, canary):
        if scope not in {'pipeline', 'fixed_context'}:
            raise ValueError('Unknown experiment scope')
        if scope == 'fixed_context':
            if case['kind'] == 'clean' and case.get('document'):
                return {'skip': 'New-document utility is evaluated through the ingestion pipeline.'}
            # No retrieval or ingestion defence is claimed in this model-only experiment.
            chunks = self.original_chunks
            query = case['control_question']
            hits = BM25(chunks).search(query, max(1, self.k - 1) if case.get('document') else self.k)
            fixture = case.get('document')
            if fixture:
                from ..core import Chunk
                poison = Chunk('fixture-' + case['id'], fixture['path'], None, fixture['text'])
                hits.append({'chunk': poison, 'score': 0.0, 'coverage': 0.0})
            return self._fixed(case, hits, canary)
        with tempfile.TemporaryDirectory(prefix='rag-security-') as tmp:
            root = Path(tmp)
            for source in sorted({c.source for c in self.original_chunks}):
                target = root / source
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.corpus / source, target)
            fixture = case.get('document')
            if fixture:
                target = root / fixture['path']
                exists = target.exists()
                if fixture['operation'] == 'add' and exists:
                    raise ValueError('Added fixture would overwrite an existing document')
                if fixture['operation'] in {'append', 'replace'} and not exists:
                    raise ValueError('Modified fixture does not name an existing document')
                prefix = target.read_text(encoding='utf-8') + '\n\n' if fixture['operation'] == 'append' else ''
                target.write_text(prefix + fixture['text'], encoding='utf-8')
            all_chunks = load_corpus(root)
            blocked = []
            chunks = all_chunks
            if configuration == 'trusted_manifest':
                chunks, blocked = filter_trusted(all_chunks, root, self.manifest)
            if not chunks:
                raise ValueError('No trusted chunks remain')
            provider = RecordingGemini(self.cache_dir, canary) if self.mode == 'gemini' else None
            assistant = Assistant(chunks, self.mode, self.k, provider=provider)
            response = assistant.ask(case['question'])
            # Only a retrieved chunk containing the actual attack text is considered exposure.
            needle = case.get('exposure_text', '')
            injected = [s for s in response['sources'] if fixture and s['source'] == fixture['path'] and
                        needle and needle in s['text']]
            return {'response': response, 'raw_generation': provider.last_generated if provider else None,
                    'blocked_documents': blocked, 'injection_retrieved': bool(injected),
                    'retrieved_injection_ids': [s['id'] for s in injected],
                    'corpus_sha256': corpus_hash(all_chunks), 'approved_corpus_sha256': corpus_hash(chunks),
                    'retrieval_stage': 'actual_pipeline', 'scope': scope}

    def _fixed(self, case, hits, canary):
        response = {'question': case['question'], 'mode': self.mode, 'status': 'abstained',
                    'claims': [], 'sources': [dict(asdict(h['chunk']), score=h['score']) for h in hits],
                    'reason': 'Fixed-context model experiment'}
        raw = None
        if self.mode == 'gemini':
            provider = RecordingGemini(self.cache_dir, canary)
            try:
                raw = provider.generate(case['question'], hits)
                response['claims'] = validate_claims(raw, hits)
                response['status'] = 'answered' if response['claims'] else 'abstained'
            except (ValueError, KeyError, TypeError):
                response['reason'] = 'Output validation rejected model response'
        return {'response': response, 'raw_generation': raw, 'blocked_documents': [],
                'injection_retrieved': None, 'injection_in_context': case['kind'] != 'clean',
                'corpus_sha256': self.original_hash, 'approved_corpus_sha256': None,
                'retrieval_stage': 'bypassed_fixed_context', 'scope': 'fixed_context'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class LocalHTTPAdapter:
    """Exercise our response schema on a local endpoint; never infer poisoning support."""
    name = 'loopback_http'

    def __init__(self, url, timeout=15, retries=1, bearer_token=None):
        parsed = urlsplit(url)
        if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', '::1', 'localhost'} or
                parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError('HTTP adapter supports plain loopback URLs only, without URL credentials or query strings')
        if not 0 < timeout <= 60 or not 0 <= retries <= 2:
            raise ValueError('Timeout must be 1–60 seconds and retries 0–2')
        self.url, self.timeout, self.retries = url, timeout, retries
        self.headers = {'Content-Type': 'application/json'}
        if bearer_token:
            self.headers['Authorization'] = 'Bearer ' + bearer_token
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def run(self, case, configuration, scope, canary):
        if configuration != 'baseline' or scope != 'pipeline' or case.get('document'):
            return {'skip': 'HTTP adapter supports baseline clean/direct queries only; corpus manipulation and comparison require in-process mode.'}
        if case.get('objective') == 'canary':
            return {'skip': 'HTTP server has no harness-controlled synthetic system canary.'}
        request = Request(self.url, data=json.dumps({'question': case['question']}).encode(), headers=self.headers)
        for attempt in range(self.retries + 1):
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    raw = response.read(1024 * 1024 + 1)
                    if len(raw) > 1024 * 1024:
                        raise AdapterError('API response exceeds 1 MiB limit')
                    data = json.loads(raw)
                    if (not isinstance(data, dict) or data.get('mode') not in {'offline', 'gemini'} or
                            data.get('status') not in {'abstained', 'evidence_found', 'answered'} or
                            not isinstance(data.get('claims'), list) or not isinstance(data.get('sources'), list)):
                        raise AdapterError('HTTP 200 response does not match the assistant schema')
                    for claim in data['claims']:
                        if not isinstance(claim, dict) or not isinstance(claim.get('text'), str) or not isinstance(claim.get('evidence'), list):
                            raise AdapterError('Invalid claim schema')
                        if not all(isinstance(e, dict) and isinstance(e.get('source_id'), str) and
                                   isinstance(e.get('quote'), str) for e in claim['evidence']):
                            raise AdapterError('Invalid evidence schema')
                    return {'response': data, 'raw_generation': None, 'http_status': response.status,
                            'attempts': attempt + 1, 'blocked_documents': [], 'injection_retrieved': None,
                            'retrieval_stage': 'endpoint_uninstrumented', 'scope': scope}
            except HTTPError as exc:
                code = exc.code
                exc.close()
                if code in {429, 503} and attempt < self.retries:
                    time.sleep(.25 * (attempt + 1))
                    continue
                raise AdapterError(f'API HTTP {code}; this is an execution error, not a resisted attack') from None
            except (URLError, TimeoutError, OSError, json.JSONDecodeError):
                raise AdapterError('Local API transport or JSON error; no attack verdict assigned') from None
        raise AdapterError('API request did not complete')
