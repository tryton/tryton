# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest
from trytond.tests.test_tryton import install_module, with_transaction
from trytond.pool import Pool
from trytond.res.user import bcrypt


class UserTestCase(unittest.TestCase):
    'Test User'

    @classmethod
    def setUpClass(cls):
        install_module('res')

    def create_user(self, login, password, hash_method=None):
        pool = Pool()
        User = pool.get('res.user')

        user, = User.create([{
                    'name': login,
                    'login': login,
                    }])
        if hash_method:
            hash = getattr(User, 'hash_' + hash_method)
            User.write([user], {
                    'password_hash': hash(password),
                    })
        else:
            User.write([user], {
                    'password': password,
                    })

    def check_user(self, login, password):
        pool = Pool()
        User = pool.get('res.user')

        user, = User.search([('login', '=', login)])
        user_id = User.get_login(login, password)
        self.assertEqual(user_id, user.id)

        bad_user_id = User.get_login(login, password + 'wrong')
        self.assertEqual(bad_user_id, 0)

    @with_transaction()
    def test_test_hash(self):
        'Test default hash password'
        self.create_user('user', '12345')
        self.check_user('user', '12345')

    @with_transaction()
    def test_test_sha1(self):
        'Test sha1 password'
        self.create_user('user', '12345', 'sha1')
        self.check_user('user', '12345')

    @unittest.skipIf(bcrypt is None, 'requires bcrypt')
    @with_transaction()
    def test_test_bcrypt(self):
        'Test bcrypt password'
        self.create_user('user', '12345', 'bcrypt')
        self.check_user('user', '12345')


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(UserTestCase)
