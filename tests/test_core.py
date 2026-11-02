import json
from pathlib import Path
import tempfile
import unittest

from grounded_rag.core import Assistant, BM25, Chunk, corpus_hash, load_corpus, validate_claims


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [Chunk('pump', 'pump.md', None, 'The pump alert threshold is 4.5 mm/s RMS.'),
                       Chunk('api', 'api.md', None, 'The telemetry API retains measurements for 30 days.')]

    def test_retrieves_relevant_source(self):
        self.assertEqual(BM25(self.chunks).search('pump threshold')[0]['chunk'].id, 'pump')

    def test_unrelated_query_abstains(self):
        self.assertEqual(Assistant(self.chunks).ask('football champion')['status'], 'abstained')

    def test_offline_returns_exact_quotes(self):
        result = Assistant(self.chunks).ask('pump threshold')
        self.assertEqual(result['status'], 'evidence_found')
        self.assertEqual(result['claims'][0]['text'], self.chunks[0].text)

    def test_blank_and_oversized_questions_rejected(self):
        for q in ['', '   ', 'x' * 2001, None]:
            with self.assertRaises(ValueError):
                Assistant(self.chunks).ask(q)

    def test_hash_changes_with_document_content(self):
        self.assertNotEqual(corpus_hash(self.chunks), corpus_hash(self.chunks[:1]))

    def test_chunk_overlap_and_deterministic_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'manual.md').write_text(' '.join('word' + str(i) for i in range(300)), encoding='utf-8')
            a = load_corpus(tmp, 150, 30)
            self.assertGreater(len(a), 3)
            self.assertEqual(a, load_corpus(tmp, 150, 30))
            self.assertTrue(all(len(c.text) <= 150 for c in a))
            self.assertTrue(any(word in a[1].text for word in a[0].text.split()[-3:]))

    def test_empty_corpus_is_explicit_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_corpus(tmp)

    def test_invalid_chunk_configuration(self):
        with self.assertRaises(ValueError):
            load_corpus('.', 100, 100)

    def test_pdf_without_text_requires_ocr(self):
        try:
            from pypdf import PdfWriter
        except ImportError:
            self.skipTest('Optional PDF dependency not installed')
        with tempfile.TemporaryDirectory() as tmp:
            writer = PdfWriter()
            writer.add_blank_page(width=300, height=300)
            writer.write(Path(tmp) / 'scan.pdf')
            with self.assertRaisesRegex(ValueError, 'OCR'):
                load_corpus(tmp)


class CitationTests(unittest.TestCase):
    def setUp(self):
        self.hit = {'chunk': Chunk('p1', 'manual.md', 1, 'The pump alert threshold is 4.5 mm/s RMS.'), 'score': 1, 'coverage': 1}
        self.good = {'abstain': False, 'claims': [{'text': 'The threshold is 4.5 mm/s RMS.',
                     'evidence': [{'source_id': 'p1', 'quote': 'threshold is 4.5 mm/s RMS.'}]}]}

    def test_known_source_and_exact_quote_accepted(self):
        self.assertEqual(len(validate_claims(self.good, [self.hit])), 1)

    def test_hallucinated_source_rejected(self):
        self.good['claims'][0]['evidence'][0]['source_id'] = 'invented'
        with self.assertRaisesRegex(ValueError, 'Unknown citation'):
            validate_claims(self.good, [self.hit])

    def test_fabricated_quote_rejected(self):
        self.good['claims'][0]['evidence'][0]['quote'] = 'threshold is 99 mm/s RMS.'
        with self.assertRaisesRegex(ValueError, 'verbatim'):
            validate_claims(self.good, [self.hit])

    def test_abstention_discards_claims(self):
        self.good['abstain'] = True
        self.assertEqual(validate_claims(self.good, [self.hit]), [])

    def test_unsupported_claim_without_evidence_rejected(self):
        self.good['claims'][0]['evidence'] = []
        with self.assertRaises(ValueError):
            validate_claims(self.good, [self.hit])

    def test_invalid_provider_output_fails_closed(self):
        class FakeProvider:
            def prepare(self, chunks):
                pass
            def search(provider, question, k):
                return [self.hit]
            def generate(provider, question, hits):
                return {'abstain': False, 'claims': []}
        assistant = Assistant([self.hit['chunk']], mode='gemini', provider=FakeProvider())
        self.assertEqual(assistant.ask('threshold')['status'], 'abstained')


if __name__ == '__main__':
    unittest.main()
