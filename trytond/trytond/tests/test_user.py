# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
import datetime
import os
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from trytond.config import config
from trytond.pool import Pool
from trytond.res import user as user_module
from trytond.res.user import PasswordError
from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction

FROM = 'tryton@example.com'


@contextmanager
def set_authentications(methods):
    saved_methods = config.get('session', 'authentications')
    config.set('session', 'authentications', methods)
    try:
        yield
    finally:
        config.set('session', 'authentications', saved_methods)


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
        config.set('password', 'length', '4')
        self.addCleanup(config.set, 'password', 'length', length)

        forbidden = config.get('password', 'forbidden', default='')
        config.set(
            'password', 'forbidden',
            os.path.join(os.path.dirname(__file__), 'forbidden.txt'))
        self.addCleanup(config.set, 'password', 'forbidden', forbidden)

        reset_from = config.get('email', 'from', fallback='')
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

        with self.assertRaises(PasswordError):
            User.validate_password('123', [])
        User.validate_password('1234', [])

    @with_transaction()
    def test_validate_password_forbidden(self):
        "Test validate password forbidden"
        pool = Pool()
        User = pool.get('res.user')

        with self.assertRaises(PasswordError):
            User.validate_password('password', [])

    @with_transaction()
    def test_validate_password_name(self):
        "Test validate password name"
        pool = Pool()
        User = pool.get('res.user')
        user = User(name='name')

        with self.assertRaises(PasswordError):
            User.validate_password('name', [user])

    @with_transaction()
    def test_validate_password_login(self):
        "Test validate password login"
        pool = Pool()
        User = pool.get('res.user')
        user = User(login='login')

        with self.assertRaises(PasswordError):
            User.validate_password('login', [user])

    @with_transaction()
    def test_validate_password_email(self):
        "Test validate password email"
        pool = Pool()
        User = pool.get('res.user')
        user = User(email='email')

        with self.assertRaises(PasswordError):
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

        with patch.object(
                user_module, 'send_message_transactional') as send_message:
            User.reset_password([user], length=8)
            send_message.assert_called_once()

        cursor.execute(*user_table.select(
                user_table.password_hash,
                where=user_table.id == user.id))
        password_hash, = cursor.fetchone()

        self.assertEqual(len(user.password_reset), 8)
        self.assertTrue(user.password_reset_expire)
        self.check_user('user', '12345')
        self.check_user('user', user.password_reset)

    @with_transaction()
    def test_reset_password_expired(self):
        "Test reset password not working when expired"
        pool = Pool()
        User = pool.get('res.user')

        user = User(login='user', email='user@example.com')
        user.save()

        with patch.object(user_module, 'send_message_transactional'):
            User.reset_password([user], length=8)

        user.password_reset_expire = (
            datetime.datetime.now() - datetime.timedelta(10))
        user.save()
        self.assertFalse(User.get_login('user', {
                    'password': user.password_reset,
                    }))

    @with_transaction()
    def test_authentications(self):
        "Test authentications"
        pool = Pool()
        User = pool.get('res.user')

        user = User(login='user')
        user.save()

        with patch.object(User, '_login_always',
                Mock(return_value=user.id), create=True), \
                patch.object(User, '_login_different',
                    Mock(return_value=user.id + 1), create=True), \
                patch.object(User, '_login_never',
                    Mock(return_value=None), create=True):
            for methods, result in (
                    ('never,never', None),
                    ('never,always', user.id),
                    ('always,never', user.id),
                    ('always,always', user.id),
                    ('never+never', None),
                    ('never+always', None),
                    ('always+never', None),
                    ('always+always', user.id),
                    ('always+different', None),
                    ):
                with self.subTest(methods=methods, result=result):
                    with set_authentications(methods):
                        self.assertEqual(User.get_login('user', {}), result)

    @with_transaction()
    def test_bad_authentication_logging(self):
        "Test the logging of log in attempts"
        pool = Pool()
        LoginAttempt = pool.get('res.user.login.attempt')

        self.create_user('user', '12345')
        self.check_user('user', '12345')
        self.assertEqual(LoginAttempt.count('user', None), 1)

    @with_transaction()
    def test_bad_authentication_valid_cookie(self):
        "Test the logging of log in attempts with a valid cookie"
        pool = Pool()
        User = pool.get('res.user')
        UserDevice = pool.get('res.user.device')
        LoginAttempt = pool.get('res.user.login.attempt')

        user = self.create_user('user', '12345')
        with Transaction().set_user(user.id):
            cookie = UserDevice.renew(None)

        User.get_login('user', {'password': '', 'device_cookie': cookie})
        self.assertEqual(LoginAttempt.count('user', None), 0)
        self.assertEqual(LoginAttempt.count('user', cookie), 1)

    @with_transaction()
    def test_bad_authentication_invalid_cookie(self):
        "Test the logging of log in attempts without a valid cookie"
        pool = Pool()
        User = pool.get('res.user')
        UserDevice = pool.get('res.user.device')
        LoginAttempt = pool.get('res.user.login.attempt')

        user = self.create_user('user', '12345')
        with Transaction().set_user(user.id):
            cookie = UserDevice.renew(None)

        User.get_login('user', {
                'password': '',
                'device_cookie': cookie + 'wrong',
                })
        self.assertEqual(LoginAttempt.count('user', None), 1)
        self.assertEqual(LoginAttempt.count('user', cookie), 0)

    @with_transaction()
    def test_authentication_option_ip_address(self):
        "Test authentication with ip_address option"
        pool = Pool()
        User = pool.get('res.user')

        user = User(login='user')
        user.save()

        ip_network = config.get(
            'session', 'authentication_ip_network', default='')
        config.set(
            'session', 'authentication_ip_network',
            '192.168.0.0/16,127.0.0.0/8')
        self.addCleanup(
            config.set, 'session', 'authentication_ip_network', ip_network)

        with patch.object(User, '_login_always', create=True) as always, \
                patch.object(User, '_login_never', create=True) as never:
            always.return_value = user.id
            never.return_value = None

            with set_authentications('always+never?ip_address'):
                for address, result in [
                        ('192.168.0.1', user.id),
                        ('172.17.0.1', None),
                        ('127.0.0.1', user.id),
                        ]:
                    with self.subTest(address=address):
                        with Transaction().set_context(_request={
                                    'remote_addr': address,
                                    }):
                            self.assertEqual(
                                User.get_login('user', {}), result)

    @with_transaction()
    def test_authentication_option_device_cookie(self):
        "Test authentication with device cookie option"
        pool = Pool()
        User = pool.get('res.user')
        UserDevice = pool.get('res.user.device')

        user = User(login='user')
        user.save()
        with Transaction().set_user(user.id):
            cookie = UserDevice.renew(None)

        with patch.object(User, '_login_always', create=True) as always, \
                patch.object(User, '_login_never', create=True) as never:
            always.return_value = user.id
            never.return_value = None

            with set_authentications('always+never?device_cookie'):
                for value, result in [
                        (cookie, user.id),
                        ('not cookie', None),
                        ]:
                    with self.subTest(cookie=value):
                        self.assertEqual(
                            User.get_login('user', {'device_cookie': value}),
                            result)
