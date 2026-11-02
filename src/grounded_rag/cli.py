"""Command-line interface."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from .core import Assistant, load_corpus
from .gemini import ProviderError


def main(argv=None):
    parser = argparse.ArgumentParser(description='Grounded document assistant')
    parser.add_argument('--corpus', default='data/sample')
    parser.add_argument('--mode', choices=['offline', 'gemini'], default='offline')
    parser.add_argument('--k', type=int, default=3)
    sub = parser.add_subparsers(dest='command', required=True)
    ask = sub.add_parser('ask')
    ask.add_argument('question')
    ev = sub.add_parser('evaluate')
    ev.add_argument('--dataset', default='evaluation/questions.json')
    ev.add_argument('--output', default='reports/offline.json')
    security = sub.add_parser('security', help='Run the controlled security evaluation suite')
    security.add_argument('--cases', default='evaluation/security_cases.json')
    security.add_argument('--manifest', default='evaluation/trusted_manifest.json')
    security.add_argument('--configuration', choices=['baseline', 'trusted_manifest', 'both'], default='both')
    security.add_argument('--scope', choices=['pipeline', 'fixed_context', 'both'], default='pipeline')
    security.add_argument('--repeats', type=int, default=1)
    security.add_argument('--concurrency', type=int, default=1)
    security.add_argument('--endpoint', help='Optional loopback-only HTTP endpoint; direct/clean cases only')
    security.add_argument('--timeout', type=float, default=15)
    security.add_argument('--retries', type=int, default=1)
    security.add_argument('--output', default='reports/security_offline.json')
    web = sub.add_parser('serve')
    web.add_argument('--host', default='127.0.0.1')
    web.add_argument('--port', type=int, default=8765)
    web.add_argument('--trusted-manifest', help='Optional approved document hash manifest for serving')
    args = parser.parse_args(argv)
    try:
        if args.command == 'security':
            from .security.runner import run_suite
            from .security.report import write_report
            configs = ('baseline', 'trusted_manifest') if args.configuration == 'both' else (args.configuration,)
            scopes = ('pipeline', 'fixed_context') if args.scope == 'both' else (args.scope,)
            report = asyncio.run(run_suite(args.corpus, args.cases, args.manifest, args.mode, configs, scopes,
                                           args.repeats, args.concurrency, args.endpoint, args.timeout, args.retries,
                                           os.environ.get('RAG_TEST_BEARER_TOKEN'), args.k))
            outputs = write_report(report, args.output)
            print(json.dumps(report['summary'], indent=2))
            print('Reports: ' + ', '.join(str(p) for p in outputs))
            return 1 if any(s['execution_errors'] for s in report['summary']) else 0
        chunks = load_corpus(args.corpus)
        if args.command == 'serve' and args.trusted_manifest:
            from .security.cases import filter_trusted, load_manifest
            chunks, blocked = filter_trusted(chunks, args.corpus, load_manifest(args.trusted_manifest))
            if not chunks:
                raise ValueError('No approved documents remain after manifest verification')
            print(f'Trust policy: {len(blocked)} unapproved/modified documents excluded', file=sys.stderr)
        if args.command == 'evaluate':
            from .evaluate import evaluate
            report = evaluate(chunks, args.dataset, args.output, args.mode, args.k)
            print(json.dumps(report['metrics'], indent=2))
            print('Report saved to ' + str(Path(args.output)))
        else:
            assistant = Assistant(chunks, args.mode, args.k)
            if args.command == 'ask':
                print(json.dumps(assistant.ask(args.question), indent=2, ensure_ascii=False))
            else:
                from .web import serve
                serve(assistant, args.host, args.port)
    except (ValueError, ProviderError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
