# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import unittest
from trytond.transaction import Transaction
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, \
    install_module
from trytond.res.user import bcrypt


class UserTestCase(unittest.TestCase):
    'Test User'

    def setUp(self):
        install_module('res')
        self.user = POOL.get('res.user')

    def create_user(self, login, password, hash_method=None):
        user, = self.user.create([{
                    'name': login,
                    'login': login,
                    }])
        if hash_method:
            hash = getattr(self.user, 'hash_' + hash_method)
            self.user.write([user], {
                    'password_hash': hash(password),
                    })
        else:
            self.user.write([user], {
                    'password': password,
                    })

    def check_user(self, login, password):
        user, = self.user.search([('login', '=', login)])
        user_id = self.user.get_login(login, password)
        self.assertEqual(user_id, user.id)

        bad_user_id = self.user.get_login(login, password + 'wrong')
        self.assertEqual(bad_user_id, 0)

    def test0010test_hash(self):
        'Test default hash password'
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.create_user('user', '12345')
            self.check_user('user', '12345')

    def test0011test_sha1(self):
        'Test sha1 password'
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.create_user('user', '12345', 'sha1')
            self.check_user('user', '12345')

    @unittest.skipIf(bcrypt is None, 'requires bcrypt')
    def test0012test_bcrypt(self):
        'Test bcrypt password'
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.create_user('user', '12345', 'bcrypt')
            self.check_user('user', '12345')


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(UserTestCase)
