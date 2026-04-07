# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest import TestCase
from unittest.mock import patch

from naiad import Client, __version__, _format_accept_language


class HeadersTestCase(TestCase):

    def test_format_accept_language(self):
        "Test format accept language"
        languages = ['fr', ('en', .5)]

        header = _format_accept_language(languages)

        self.assertEqual(header, 'fr,en;q=0.5')

    @patch('httpx.Client')
    def test_context_header(self, httpx_client):
        "Test context header"
        Client('http://localhost/', 'secret', context={'foo': 'bar'})

        self.assertEqual(httpx_client.call_args.kwargs['headers'], {
                'User-Agent': f'naiad/{__version__}',
                'X-Tryton-Context': 'eyJmb28iOiJiYXIifQ==',
                })

    @patch('httpx.Client')
    def test_language_header(self, httpx_client):
        "Test language header"
        Client('http://localhost/', 'secret', languages=['fr', ('en', .5)])

        self.assertEqual(httpx_client.call_args.kwargs['headers'], {
                'User-Agent': f'naiad/{__version__}',
                'Accept-Language': 'fr,en;q=0.5',
                })

    @patch('httpx.Client')
    def test_usage_header(self, httpx_client):
        "Test usage header"
        Client('http://localhost/', 'secret', usages=['foo', 'bar'])

        self.assertEqual(httpx_client.call_args.kwargs['headers'], {
                'User-Agent': f'naiad/{__version__}',
                'X-Tryton-Usage': 'foo,bar',
                })
