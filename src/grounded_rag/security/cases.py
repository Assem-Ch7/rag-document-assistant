"""Labelled security cases and file-integrity policy."""

import hashlib
import json
from pathlib import Path


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_cases(path):
    cases = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(cases, list) or not 1 <= len(cases) <= 200:
        raise ValueError('Use a JSON list of 1–200 labelled cases')
    seen = set()
    for c in cases:
        if (not isinstance(c, dict) or not isinstance(c.get('id'), str) or c['id'] in seen or
                c.get('kind') not in {'clean', 'direct', 'indirect'} or
                not isinstance(c.get('question'), str) or not 1 <= len(c['question']) <= 2000 or
                not isinstance(c.get('control_question'), str) or not c['control_question'].strip() or
                not isinstance(c.get('family'), str) or
                not isinstance(c.get('expected_keywords'), list) or
                not all(isinstance(t, str) and t for t in c['expected_keywords'])):
            raise ValueError('Invalid or duplicate security case')
        seen.add(c['id'])
        if c['kind'] != 'clean' and c.get('objective') not in {'exact_marker', 'canary', 'false_fact'}:
            raise ValueError('Attack cases need a supported labelled objective')
        if c.get('objective') == 'exact_marker' and not c.get('marker'):
            raise ValueError('Exact-marker cases require a marker')
        if c.get('objective') == 'false_fact' and not c.get('false_fact'):
            raise ValueError('False-fact cases require a labelled false fact')
        fixture = c.get('document')
        if c['kind'] == 'indirect' and not fixture:
            raise ValueError('Indirect cases require a document fixture')
        if fixture:
            name = fixture.get('path', '')
            if (not isinstance(name, str) or Path(name).name != name or '/' in name or '\\' in name or
                    Path(name).suffix not in {'.md', '.txt'} or
                    fixture.get('operation') not in {'add', 'append', 'replace'} or
                    not isinstance(fixture.get('text'), str) or not 0 < len(fixture['text']) <= 10000):
                raise ValueError('Fixtures must be bounded text files with a simple relative filename')
    return cases


def load_manifest(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    files = value.get('files') if isinstance(value, dict) else None
    if not isinstance(files, dict) or not files:
        raise ValueError('Trusted manifest must contain file hashes')
    for name, digest in files.items():
        if not isinstance(name, str) or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError('Invalid trusted manifest entry')
    return files


def filter_trusted(chunks, corpus, manifest):
    """Allow only exact, previously approved document bytes; do not silently trust updates."""
    root = Path(corpus).resolve()
    approved, blocked = set(), []
    for source in sorted({c.source for c in chunks}):
        path = (root / source).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Invalid source path')
        if source not in manifest:
            blocked.append({'source': source, 'reason': 'not_in_manifest'})
        elif file_hash(path) != manifest[source]:
            blocked.append({'source': source, 'reason': 'hash_mismatch'})
        else:
            approved.add(source)
    return [c for c in chunks if c.source in approved], blocked
