"""Portable escaped HTML and JSON reports, including individual evidence."""

import html
import json
from pathlib import Path


def write_report(report, output):
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding='utf-8')
    escape = lambda x: html.escape(str(x))
    percent = lambda value: 'Not measured' if value is None else f'{value:.1%}'
    summary = ''.join('<tr>' + ''.join('<td>' + escape(value) + '</td>' for value in [
        s['configuration'], s['scope'], str(s['completed']) + '/' + str(s['attempted']),
        percent(s['clean_keyword_proxy_rate']),
        str(s['poison_retrieved_cases']) + '/' + str(s['poison_pipeline_cases']),
        percent(s['application_success_rate_lower_bound']), s['execution_errors']]) + '</tr>' for s in report['summary'])
    rows = []
    for r in report['results']:
        verdict = (r.get('application_verdict') or {}).get('outcome', r['execution_status'])
        details = escape(json.dumps(r, indent=2, ensure_ascii=True))
        rows.append('<details><summary>' + escape(f"{r['case_id']} · {r['configuration']} · {r['scope']} · {verdict}") +
                    '</summary><pre>' + details + '</pre></details>')
    notes = ''.join('<li><b>' + escape(k) + ':</b> ' + escape(v) + '</li>' for k, v in report['metric_notes'].items())
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAG security evaluation</title><style>body{max-width:1180px;margin:40px auto;padding:0 24px;background:#f5f6f0;color:#173132;font:15px/1.6 system-ui}h1{font-size:36px}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid #d5e1dc}th{background:#173132;color:white}details{background:white;border:1px solid #d5e1dc;margin:12px 0;padding:14px;border-radius:8px}summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.table{overflow:auto}.note{padding:18px;border-left:4px solid #196a54;background:white}</style>
<h1>RAG security evaluation</h1>'''
    page += '<p>' + escape(report['adapter']) + ' · ' + escape(report['requested_mode']) + ' · ' + escape(report['run_at_utc']) + '</p>'
    page += '<p class="note">Offline results measure retrieval exposure and utility. They do not demonstrate LLM resistance. Expand cases to inspect the complete evidence.</p>'
    page += '<div class="table"><table><tr><th>Configuration</th><th>Scope</th><th>Completed</th><th>Clean keyword proxy</th><th>Poison retrieved</th><th>Confirmed ASR lower bound</th><th>Errors</th></tr>' + summary + '</table></div>'
    page += '<h2>Metric definitions</h2><ul>' + notes + '</ul><h2>Case evidence</h2>' + ''.join(rows) + '</html>'
    path.with_suffix('.html').write_text(page, encoding='utf-8')
    return path, path.with_suffix('.html')
