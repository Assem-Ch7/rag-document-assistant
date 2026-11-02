"""Document loading, reproducible chunking, lexical retrieval and answer validation."""

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

STOP = set("a an the is are was were what which who how when where why of to for in on at and or with from does do this that it its be by as can please tell me about i my our your de du des le la les un une est sont quel quelle quels quelles comment pour dans au aux et ou en sur avec que qu ce cette il elle son sa ses".split())


def tokens(text):
    text = unicodedata.normalize('NFKD', text.lower())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return [t for t in re.findall(r'[a-z0-9]+', text) if t not in STOP]


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    page: int | None
    text: str


def load_corpus(directory, chunk_size=650, overlap=80):
    """Load local UTF-8 text/Markdown and text-based PDF; fail rather than silently skip."""
    if chunk_size < 100 or not 0 <= overlap < chunk_size:
        raise ValueError('Require chunk_size >= 100 and 0 <= overlap < chunk_size')
    root = Path(directory).resolve()
    if not root.is_dir():
        raise ValueError('Corpus directory does not exist')
    chunks = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in {'.txt', '.md', '.pdf'}:
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Corpus symlinks outside the directory are not supported')
        if path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError('Document exceeds the 10 MiB demo limit: ' + path.name)
        source = path.relative_to(root).as_posix()
        if path.suffix.lower() == '.pdf':
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise ValueError('PDF loading requires pip install -e ".[pdf]"') from exc
            reader = PdfReader(path)
            if len(reader.pages) > 200:
                raise ValueError('PDF exceeds the 200-page demo limit')
            pages = [(i + 1, page.extract_text() or '') for i, page in enumerate(reader.pages)]
        else:
            pages = [(None, path.read_text(encoding='utf-8'))]
        if not any(text.strip() for _, text in pages):
            raise ValueError('No extractable text (OCR is not included): ' + source)
        for page, text in pages:
            text = re.sub(r'\s+', ' ', text).strip()
            start = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                if end < len(text):
                    boundary = text.rfind(' ', start + chunk_size // 2, end)
                    if boundary > start:
                        end = boundary
                content = text[start:end].strip()
                identifier = hashlib.sha256(f'{source}|{page}|{start}|{content}'.encode()).hexdigest()[:12]
                chunks.append(Chunk(identifier, source, page, content))
                if end >= len(text):
                    break
                start = max(start + 1, end - overlap)
    if not chunks:
        raise ValueError('Corpus contains no supported non-empty documents')
    if len(chunks) > 10000:
        raise ValueError('Corpus exceeds the 10,000-chunk demo limit')
    return chunks


def corpus_hash(chunks):
    payload = json.dumps([asdict(c) for c in chunks], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


class BM25:
    """Small transparent BM25 baseline. Scores are rankings, not confidence probabilities."""

    def __init__(self, chunks):
        self.chunks = chunks
        self.counts = [Counter(tokens(c.text)) for c in chunks]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / len(self.lengths) or 1
        df = Counter(t for c in self.counts for t in c)
        self.idf = {t: math.log(1 + (len(chunks) - n + .5) / (n + .5)) for t, n in df.items()}

    def search(self, question, k=3):
        query = set(tokens(question))
        hits = []
        for chunk, count, length in zip(self.chunks, self.counts, self.lengths):
            score = sum(self.idf.get(t, 0) * count[t] * 2.5 /
                        (count[t] + 1.5 * (.25 + .75 * length / self.average))
                        for t in query if count[t])
            if score > 0:
                hits.append({'chunk': chunk, 'score': score,
                             'coverage': len(query.intersection(count)) / max(1, len(query))})
        return sorted(hits, key=lambda h: (-h['score'], h['chunk'].id))[:k]


def validate_claims(payload, hits):
    """Require actual retrieved source IDs and verbatim support quotes for every claim.

    This checks citation provenance, not whether a quote logically entails a claim.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get('abstain'), bool):
        raise ValueError('Invalid answer object')
    if payload['abstain']:
        return []
    claims = payload.get('claims')
    if not isinstance(claims, list) or not 1 <= len(claims) <= 8:
        raise ValueError('Answer must contain 1 to 8 supported claims')
    allowed = {h['chunk'].id: h['chunk'].text for h in hits}
    clean = []
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get('text'), str) or not claim['text'].strip():
            raise ValueError('Invalid claim text')
        evidence = claim.get('evidence')
        if not isinstance(evidence, list) or not 1 <= len(evidence) <= 6:
            raise ValueError('Every claim requires evidence')
        for item in evidence:
            if not isinstance(item, dict):
                raise ValueError('Invalid evidence')
            cid, quote = item.get('source_id'), item.get('quote')
            if not isinstance(cid, str) or cid not in allowed:
                raise ValueError('Unknown citation')
            if not isinstance(quote, str) or len(quote.strip()) < 12 or quote not in allowed[cid]:
                raise ValueError('Evidence must be a verbatim retrieved quote')
        clean.append({'text': claim['text'].strip(), 'evidence': evidence})
    return clean


class Assistant:
    def __init__(self, chunks, mode='offline', k=3, min_coverage=.45, provider=None):
        if mode not in {'offline', 'gemini'} or not 1 <= k <= 10 or not 0 <= min_coverage <= 1:
            raise ValueError('Invalid assistant configuration')
        self.chunks, self.mode, self.k, self.min_coverage = chunks, mode, k, min_coverage
        self.retriever = BM25(chunks)
        self.provider = provider
        if mode == 'gemini':
            if provider is None:
                from .gemini import Gemini
                self.provider = Gemini()
            self.provider.prepare(chunks)

    def ask(self, question):
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            raise ValueError('Question must contain 1–2000 characters')
        hits = (self.retriever.search(question, self.k) if self.mode == 'offline'
                else self.provider.search(question, self.k))
        result = {'question': question, 'mode': self.mode, 'status': 'abstained',
                  'reason': 'No sufficiently supported passage found.', 'claims': [],
                  'sources': [dict(asdict(h['chunk']), score=round(h['score'], 6),
                                   query_coverage=round(h['coverage'], 4)) for h in hits]}
        if not hits:
            return result
        if self.mode == 'offline':
            selected = [h for h in hits if h['coverage'] >= self.min_coverage]
            if not selected:
                return result
            # Evidence-only mode does not pretend to synthesise a factual answer.
            result['claims'] = [{'text': h['chunk'].text,
                                 'evidence': [{'source_id': h['chunk'].id, 'quote': h['chunk'].text}]}
                                for h in selected]
            result.update(status='evidence_found', reason='Verbatim excerpts; relevance still needs human review.')
        else:
            try:
                payload = self.provider.generate(question, hits)
                result['claims'] = validate_claims(payload, hits)
            except (ValueError, KeyError, TypeError):
                result['reason'] = 'Model output failed citation or response validation.'
                return result
            if result['claims']:
                result.update(status='answered', reason='Generated claims with validated source IDs and quotes; entailment is not guaranteed.')
        return result
