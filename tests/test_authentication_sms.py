# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import unittest

from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import suite as test_suite
from trytond.config import config
from trytond.pool import Pool
from trytond.exceptions import LoginException


def send_sms(text, to, from_):
    sms_queue.append({
            'text': text,
            'to': to,
            'from': from_,
            })


sms_queue = []


class AuthenticationSMSTestCase(ModuleTestCase):
    'Test Authentication SMS module'
    module = 'authentication_sms'

    def setUp(self):
        super(AuthenticationSMSTestCase, self).setUp()
        methods = config.get('session', 'authentications', default='')
        config.set('session', 'authentications', 'sms')
        self.addCleanup(config.set, 'session', 'authentications', methods)
        config.add_section('authentication_sms')
        config.set(
            'authentication_sms', 'function',
            'trytond.modules.authentication_sms.tests.send_sms')
        self.addCleanup(config.remove_section, 'authentication_sms')
        del sms_queue[:]

    @with_transaction()
    def test_sms_code_default_code(self):
        pool = Pool()
        SMSCode = pool.get('res.user.login.sms_code')
        code = SMSCode.default_code()
        self.assertEqual(len(code), 6)

    @with_transaction()
    def test_sms_code_get(self):
        pool = Pool()
        SMSCode = pool.get('res.user.login.sms_code')

        record, = SMSCode.create([{'user_id': 1}])

        records = list(SMSCode.get(1))
        self.assertEqual(records, [record])

        future = datetime.datetime.now() + datetime.timedelta(10 * 60)
        records = list(SMSCode.get(1, _now=future))
        self.assertFalse(records)
        self.assertFalse(SMSCode.search([]))

    @with_transaction()
    def test_sms_code_send(self):
        pool = Pool()
        User = pool.get('res.user')
        SMSCode = pool.get('res.user.login.sms_code')

        user = User(name='sms', login='sms', mobile='+123456789')
        user.save()

        SMSCode.send(user.id)
        record, = SMSCode.search([])
        self.assertEqual(len(sms_queue), 1)
        sms, = sms_queue
        self.assertEqual(record.user_id, user.id)
        self.assertIn(record.code, sms['text'])
        self.assertEqual(user.mobile, sms['to'])

        # Don't send a second SMS as long as the first is valid
        SMSCode.send(user.id)
        self.assertEqual(len(sms_queue), 1)

    @with_transaction()
    def test_sms_code_check(self):
        pool = Pool()
        SMSCode = pool.get('res.user.login.sms_code')

        record, = SMSCode.create([{'user_id': 1}])
        sms_code = record.code

        self.assertFalse(SMSCode.check(1, 'foo'))
        self.assertTrue(SMSCode.check(1, sms_code))
        # Second check should fail
        self.assertFalse(SMSCode.check(1, sms_code))

    @with_transaction()
    def test_user_get_login(self):
        pool = Pool()
        User = pool.get('res.user')
        SMSCode = pool.get('res.user.login.sms_code')

        user = User(name='sms', login='sms', mobile='+123456789')
        user.save()

        with self.assertRaises(LoginException) as cm:
            User.get_login('sms', {})
        self.assertEqual(cm.exception.name, 'sms_code')
        self.assertEqual(cm.exception.type, 'char')

        record, = SMSCode.search([])
        sms_code = record.code

        user_id = User.get_login('sms', {
                'sms_code': sms_code,
                })
        self.assertEqual(user_id, user.id)


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            AuthenticationSMSTestCase))
    return suite
