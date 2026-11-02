from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from grounded_rag.core import Assistant, Chunk
from grounded_rag.web import make_handler


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assistant = Assistant([Chunk('p1', 'pump.md', None, 'The pump alert threshold is 4.5 mm/s RMS.')])
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(assistant))
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_health_endpoint(self):
        with urlopen(self.url + '/health') as response:
            self.assertEqual(json.load(response)['mode'], 'offline')

    def test_question_round_trip(self):
        req = Request(self.url + '/api/ask', data=json.dumps({'question': 'pump threshold'}).encode(),
                      headers={'Content-Type': 'application/json'})
        with urlopen(req) as response:
            self.assertEqual(json.load(response)['claims'][0]['evidence'][0]['source_id'], 'p1')

    def test_empty_question_returns_bad_request(self):
        req = Request(self.url + '/api/ask', data=b'{"question":""}', headers={'Content-Type': 'application/json'})
        with self.assertRaises(HTTPError) as error:
            urlopen(req)
        self.assertEqual(error.exception.code, 400)

    def test_cross_origin_request_rejected(self):
        req = Request(self.url + '/api/ask', data=b'{"question":"pump"}',
                      headers={'Content-Type': 'application/json', 'Origin': 'https://unrelated.example'})
        with self.assertRaises(HTTPError) as error:
            urlopen(req)
        self.assertEqual(error.exception.code, 403)


if __name__ == '__main__':
    unittest.main()
