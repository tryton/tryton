# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from .common import ProteusTestCase


class TestContext(ProteusTestCase):

    def test_config(self):
        prev_ctx = self.config._context

        with self.config.set_context({'a': 1}):
            self.assertEqual(self.config.context['a'], 1)
            for key, value in prev_ctx.items():
                self.assertEqual(self.config.context[key], value)

        self.assertEqual(self.config.context, prev_ctx)
