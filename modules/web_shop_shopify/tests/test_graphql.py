# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

from trytond.modules.web_shop_shopify.graphql import deep_merge, selection


class GraphQLTestCase(unittest.TestCase):
    "Test GraphQL library"

    def test_deep_merge(self):
        "Test deep_merge"
        a = {
            'id': None,
            'firstName': None,
            'birthday': {
                'month': None,
                },
            }
        b = {
            'id': None,
            'lastName': None,
            'birthday': {
                'day': None,
                },
            }
        self.assertEqual(deep_merge(a, b), {
                'id': None,
                'firstName': None,
                'lastName': None,
                'birthday': {
                    'month': None,
                    'day': None,
                    },
                })

    def test_selection(self):
        "Test selection"
        for fields, result in [
                ({'id': None}, '{\nid\n}'),
                ({
                        'id': None,
                        'firstName': None,
                        'lastName': None},
                    '{\nid\nfirstName\nlastName\n}'),
                ({
                        'id': None,
                        'firstName': None,
                        'lastName': None,
                        'birthday': {
                            'month': None,
                            'day': None,
                            },
                        },
                    '{\nid\nfirstName\nlastName\n'
                    'birthday {\nmonth\nday\n}\n}'),
                ]:
            with self.subTest(fields=fields):
                self.assertEqual(selection(fields), result)
