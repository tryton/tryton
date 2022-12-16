# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
import datetime
import os
import unittest
from unittest.mock import patch, ANY

from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.pool import Pool
from trytond.config import config
from trytond.error import UserError
from trytond.res import user as user_module
from trytond.transaction import Transaction

FROM = 'tryton@example.com'


class UserTestCase(unittest.TestCase):
    'Test User'

    @classmethod
    def setUpClass(cls):
        activate_module('res')

    def setUp(self):
        methods = config.get('session', 'authentications')
        config.set('session', 'authentications', 'password')
        self.addCleanup(config.set, 'session', 'authentications', methods)

        length = config.get('password', 'length')
        config.set('password', 'length', 4)
        self.addCleanup(config.set, 'password', 'length', length)

        forbidden = config.get('password', 'forbidden', default='')
        config.set(
            'password', 'forbidden',
            os.path.join(os.path.dirname(__file__), 'forbidden.txt'))
        self.addCleanup(config.set, 'password', 'forbidden', forbidden)

        entropy = config.get('password', 'entropy')
        config.set('password', 'entropy', 0.9)
        self.addCleanup(config.set, 'password', 'entropy', entropy)

        reset_from = config.get('email', 'from')
        config.set('email', 'from', FROM)
        self.addCleanup(lambda: config.set('email', 'from', reset_from))

    def create_user(self, login, password, email=None):
        pool = Pool()
        User = pool.get('res.user')

        user, = User.create([{
                    'name': login,
                    'login': login,
                    'email': email,
                    'password': password,
                    }])
        return user

    def check_user(self, login, password):
        pool = Pool()
        User = pool.get('res.user')

        user, = User.search([('login', '=', login)])
        user_id = User.get_login(login, {
                'password': password,
                })
        self.assertEqual(user_id, user.id)

        bad_user_id = User.get_login(login, {
                'password': password + 'wrong',
                })
        self.assertFalse(bad_user_id)

    @with_transaction()
    def test_test_hash(self):
        'Test default hash password'
        self.create_user('user', '12345')
        self.check_user('user', '12345')

    @with_transaction()
    def test_read_password_hash(self):
        "Test password_hash can not be read"
        user = self.create_user('user', '12345')
        self.assertIsNone(user.password_hash)

    @with_transaction()
    def test_validate_password_length(self):
        "Test validate password length"
        pool = Pool()
        User = pool.get('res.user')

        with self.assertRaises(UserError):
            User.validate_password('123', [])
        User.validate_password('1234', [])

    @with_transaction()
    def test_validate_password_forbidden(self):
        "Test validate password forbidden"
        pool = Pool()
        User = pool.get('res.user')

        with self.assertRaises(UserError):
            User.validate_password('password', [])

    @with_transaction()
    def test_validate_password_entropy(self):
        "Test validate password entropy"
        pool = Pool()
        User = pool.get('res.user')

        with self.assertRaises(UserError):
            User.validate_password('aaaaaa', [])

    @with_transaction()
    def test_validate_password_name(self):
        "Test validate password name"
        pool = Pool()
        User = pool.get('res.user')
        user = User(name='name')

        with self.assertRaises(UserError):
            User.validate_password('name', [user])

    @with_transaction()
    def test_validate_password_login(self):
        "Test validate password login"
        pool = Pool()
        User = pool.get('res.user')
        user = User(login='login')

        with self.assertRaises(UserError):
            User.validate_password('login', [user])

    @with_transaction()
    def test_validate_password_email(self):
        "Test validate password email"
        pool = Pool()
        User = pool.get('res.user')
        user = User(email='email')

        with self.assertRaises(UserError):
            User.validate_password('email', [user])

    @with_transaction()
    def test_reset_password(self):
        "Test reset password"
        pool = Pool()
        User = pool.get('res.user')
        user_table = User.__table__()
        transaction = Transaction()
        cursor = transaction.connection.cursor()

        user = self.create_user('user', '12345', email='user@example.com')

        with patch.object(user_module, 'sendmail_transactional') as sendmail:
            User.reset_password([user], length=8)
            sendmail.assert_called_once_with(FROM, ['user@example.com'], ANY)

        cursor.execute(*user_table.select(
                user_table.password_hash,
                where=user_table.id == user.id))
        password_hash, = cursor.fetchone()

        self.assertEqual(len(user.password_reset), 8)
        self.assertTrue(user.password_reset_expire)
        self.assertIsNone(password_hash)
        self.check_user('user', user.password_reset)

    @with_transaction()
    def test_reset_password_expired(self):
        "Test reset password not working when expired"
        pool = Pool()
        User = pool.get('res.user')

        user = User(login='user', email='user@example.com')
        user.save()

        with patch.object(user_module, 'sendmail_transactional'):
            User.reset_password([user], length=8)

        user.password_reset_expire = (
            datetime.datetime.now() - datetime.timedelta(10))
        user.save()
        self.assertFalse(User.get_login('user', {
                    'password': user.password_reset,
                    }))

    @with_transaction()
    def test_reset_password_with_password(self):
        "Test reset password not working when password is set"
        pool = Pool()
        User = pool.get('res.user')

        user = User(login='user', email='user@example.com')
        user.save()

        with patch.object(user_module, 'sendmail_transactional'):
            User.reset_password([user], length=8)

        user.password = '12345'
        user.save()
        self.check_user('user', '12345')
        self.assertFalse(User.get_login('user', {
                    'password': user.password_reset,
                    }))


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(UserTestCase)
