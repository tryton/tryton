# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest.mock import patch

import trytond.config as config
from trytond.modules.party.tests import (
    PartyCheckEraseMixin, PartyCheckReplaceMixin)
from trytond.modules.web_user import user as user_module
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction

VALIDATION_URL = 'http://www.example.com/validation'
RESET_PASSWORD_URL = 'http://www.example.com/reset_password'
FROM = 'tryton@example.com'


class WebUserTestCase(
        PartyCheckEraseMixin, PartyCheckReplaceMixin, ModuleTestCase):
    'Test Web User module'
    module = 'web_user'

    def setUp(self):
        super().setUp()
        validation_url = config.get('web', 'email_validation_url', default='')
        config.set('web', 'email_validation_url', VALIDATION_URL)
        self.addCleanup(
            lambda: config.set('web', 'email_validation_url', validation_url))
        reset_password_url = config.get(
            'web', 'reset_password_url', default='')
        config.set('web', 'reset_password_url', RESET_PASSWORD_URL)
        self.addCleanup(lambda: config.set(
                'web', 'reset_password_url', reset_password_url))
        reset_from = config.get('email', 'from', default='')
        config.set('email', 'from', FROM)
        self.addCleanup(lambda: config.set('email', 'from', reset_from))

        length = config.get('password', 'length', default='')
        config.set('password', 'length', '4')
        self.addCleanup(config.set, 'password', 'length', length)

        entropy = config.get('password', 'entropy', default='')
        config.set('password', 'entropy', '0.8')
        self.addCleanup(config.set, 'password', 'entropy', entropy)

    def create_user(self, email, password):
        pool = Pool()
        User = pool.get('web.user')

        user = User(email=email)
        user.password = password
        user.save()
        return user

    def check_user(self, email, password):
        pool = Pool()
        User = pool.get('web.user')

        user, = User.search([('email', '=', email)])
        auth_user = User.authenticate(email, password)
        self.assertEqual(auth_user, user)

        bad_user = User.authenticate(email, password + 'wrong')
        self.assertEqual(bad_user, None)

        bad_user = User.authenticate(email + 'wrong', password)
        self.assertEqual(bad_user, None)

    @with_transaction()
    def test_default_hash(self):
        'Test default hash'
        self.create_user('user@example.com', 'secret')
        self.check_user('user@example.com', 'secret')

    @with_transaction()
    def test_read_password_hash(self):
        "Test password_hash can not be read"
        user = self.create_user('user@example.com', 'secret')
        self.assertIsNone(user.password_hash)

    @with_transaction()
    def test_session(self):
        'Test session'
        pool = Pool()
        User = pool.get('web.user')

        user = User(email='user@example.com')
        user.save()

        key = user.new_session()
        self.assertTrue(key)

        session_user = User.get_user(key)
        self.assertEqual(session_user, user)

        wrong_session_user = User.get_user('foo')
        self.assertEqual(wrong_session_user, None)

    @with_transaction()
    def test_validate_email(self):
        'Test email validation'
        pool = Pool()
        User = pool.get('web.user')

        user = User(email='user@example.com')
        user.save()
        self.assertFalse(user.email_valid)
        self.assertFalse(user.email_token)

        with patch.object(
                user_module, 'send_message_transactional') as send_message:
            User.validate_email([user])
            send_message.assert_called_once()

        token = user.email_token
        self.assertTrue(token)

        self.assertEqual(
            user.get_email_validation_url(),
            '%s?token=%s' % (VALIDATION_URL, token))

        self.assertFalse(
            User.validate_email_url(VALIDATION_URL))
        self.assertFalse(
            User.validate_email_url('%s?token=12345' % VALIDATION_URL))

        self.assertTrue(
            User.validate_email_url(user.get_email_validation_url()))

        self.assertTrue(user.email_valid)
        self.assertFalse(user.email_token)

    @with_transaction()
    def test_read_reset_password_token(self):
        "Test reset_password_token can not be read"
        pool = Pool()
        User = pool.get('web.user')

        user = User(email='user@example.com', email_valid=True)
        user.save()
        with patch.object(user_module, 'send_message_transactional'):
            User.reset_password([user])

        self.assertIsNone(user.reset_password_token)

    @with_transaction()
    def test_reset_password(self):
        'Test reset password'
        pool = Pool()
        User = pool.get('web.user')
        user_table = User.__table__()
        transaction = Transaction()
        cursor = transaction.connection.cursor()

        user = User(email='user@example.com', email_valid=True)
        user.save()

        with patch.object(
                user_module, 'send_message_transactional') as send_message:
            User.reset_password([user])
            send_message.assert_called_once()
            msg, = send_message.call_args.args

        cursor.execute(*user_table.select(
                user_table.password_hash,
                user_table.reset_password_token,
                where=user_table.id == user.id))
        password_hash, token = cursor.fetchone()

        self.assertTrue(token)
        self.assertTrue(user.reset_password_token_expire)
        self.assertIn(token, msg.get_body().get_content())

        self.assertEqual(
            user._get_reset_password_url(),
            '%s?email=user%%40example.com&token=%s'
            % (RESET_PASSWORD_URL, token))

        self.assertFalse(password_hash)
        self.assertFalse(
            User.set_password_token('foo@example.com', '12345', 'secret'))
        self.assertFalse(
            User.set_password_token('user@example.com', '12345', 'secret'))
        self.assertFalse(
            User.set_password_token('foo@example.com', token, 'secret'))

        self.assertTrue(User.set_password_url(
                user._get_reset_password_url(), 'secret'))

        cursor.execute(*user_table.select(
                user_table.password_hash,
                user_table.reset_password_token,
                where=user_table.id == user.id))
        password_hash, token = cursor.fetchone()

        self.assertTrue(password_hash)
        self.assertFalse(token)
        self.assertFalse(user.reset_password_token_expire)

    @with_transaction()
    def test_create_format_email(self):
        "Test create format email"
        pool = Pool()
        User = pool.get('web.user')

        user = User(email='FOO@Example.com')
        user.save()

        self.assertEqual(user.email, 'foo@example.com')

    @with_transaction()
    def test_write_format_email(self):
        "Test write format email"
        pool = Pool()
        User = pool.get('web.user')

        user = User(email='foo@example.com')
        user.save()
        User.write([user], {'email': 'BAR@Example.com'})

        self.assertEqual(user.email, 'bar@example.com')

    @with_transaction()
    def test_authenticate_case_insensitive(self):
        "Test authenticate case insensitive"
        pool = Pool()
        User = pool.get('web.user')

        user = User(email='foo@example.com', password='secret')
        user.save()
        auth_user = User.authenticate('FOO@Example.com', 'secret')

        self.assertEqual(auth_user, user)


del ModuleTestCase
