# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

try:
    import PIL
except ImportError:
    PIL = None

from trytond.pool import Pool

from .test_tryton import ModuleTestCase, with_transaction


class ResTestCase(ModuleTestCase):
    'Test res module'
    module = 'res'

    @unittest.skipUnless(PIL, "Avatars are not generated without PIL")
    @with_transaction()
    def test_user_avatar(self):
        pool = Pool()
        User = pool.get('res.user')

        user = User(login="avatar")
        user.save()

        self.assertEqual(len(user.avatars), 1)
        self.assertIsNotNone(user.avatar)
        self.assertRegex(user.avatar_url, r'/avatar/.*/([0-9a-fA-F]{12})')


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ResTestCase)
