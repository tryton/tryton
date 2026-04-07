# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from operator import attrgetter

from naiad import Record

from .common import NaiadTestCase


class SearchTestCase(NaiadTestCase):

    def test_search(self):
        "Test search"
        records = self.client().search('res.user')
        self.assertEqual(records, [Record('res.user', id=1)])

    def test_search_domain(self):
        "Test search with domain"
        record, = self.client().search(
            'res.user', domain=[('login', '=', 'admin')], fields=['login'])
        self.assertEqual(record.login, 'admin')

    def test_search_order(self):
        "Test search with order"
        records = self.client().search(
            'res.user',
            domain=[('active', 'in', [True, False])],
            order=[('login', 'DESC')],
            fields=['login'])
        self.assertEqual(
            records, sorted(records, key=attrgetter('login'), reverse=True))

    def test_search_range(self):
        "Test search with range"
        all_records = self.client().search('ir.model')
        (start, end, size), records = self.client().search(
            'ir.model', range_=(5, 10))

        self.assertEqual(start, 5)
        self.assertEqual(end, 10)
        self.assertEqual(size, len(all_records))
        self.assertEqual(len(records), 5)
        self.assertEqual(records, all_records[5:10])

    def test_search_limit(self):
        "Test search with limit"
        all_records = self.client().search('ir.model')
        records = self.client().search('ir.model', limit=5)

        self.assertEqual(len(records), 5)
        self.assertEqual(records, all_records[:5])

    def test_search_offset(self):
        "Test search with offset"
        all_records = self.client().search('ir.model')
        records = self.client().search('ir.model', offset=5)

        self.assertEqual(records, all_records[5:])

    def test_search_fields(self):
        "Test search with fields"
        record, = self.client().search(
            'res.user', domain=[('login', '=', 'admin')], fields=['name'])

        self.assertEqual(record.name, "Administrator")
