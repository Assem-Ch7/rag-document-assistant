import json
import os
import tempfile
import unittest
from unittest.mock import patch

from grounded_rag.core import Chunk
from grounded_rag.gemini import Gemini, ProviderError


class GeminiContractTests(unittest.TestCase):
    def test_key_required_without_network_call(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ProviderError):
                Gemini()

    def test_retrieval_tasks_and_cache(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'GEMINI_API_KEY': 'test-placeholder'}):
            calls = []
            def fake_post(model, method, payload):
                calls.append(payload)
                return {'embedding': {'values': [1.0] + [0.0] * 767}}
            provider = Gemini(tmp)
            provider._post = fake_post
            chunks = [Chunk('one', 'manual.md', None, 'Pump threshold is 4.5 mm/s RMS.')]
            provider.prepare(chunks)
            provider.prepare(chunks)
            provider.search('pump threshold', 1)
            self.assertEqual([c['taskType'] for c in calls], ['RETRIEVAL_DOCUMENT', 'RETRIEVAL_QUERY'])

    def test_generation_request_and_json_parsing(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-placeholder'}):
            provider = Gemini()
            calls = []
            def fake_post(model, method, payload):
                calls.append(payload)
                return {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [
                    {'text': json.dumps({'abstain': True, 'claims': []})}]}}]}
            provider._post = fake_post
            self.assertTrue(provider.generate('unknown question', [])['abstain'])
            self.assertEqual(calls[0]['generationConfig']['responseMimeType'], 'application/json')


if __name__ == '__main__':
    unittest.main()
