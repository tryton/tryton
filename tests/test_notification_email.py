# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import sys
import unittest
try:
    from unittest.mock import patch, ANY
except ImportError:
    from mock import patch, ANY

from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import suite as test_suite
from trytond.pool import Pool
from trytond.config import config
from trytond.transaction import Transaction

from trytond.modules.notification_email import notification \
    as notification_module

FROM = 'tryton@example.com'


class NotificationEmailTestCase(ModuleTestCase):
    "Test Notification Email module"
    module = 'notification_email'

    def setUp(self):
        super(NotificationEmailTestCase, self).setUp()
        reset_from = config.get('email', 'from')
        config.set('email', 'from', FROM)
        self.addCleanup(lambda: config.set('email', 'from', reset_from))

    def _setup_notification(self):
        pool = Pool()
        Model = pool.get('ir.model')
        ModelField = pool.get('ir.model.field')
        Action = pool.get('ir.action')
        Report = pool.get('ir.action.report')
        User = pool.get('res.user')
        NotificationEmail = pool.get('notification.email')

        model, = Model.search([
                ('model', '=', User.__name__),
                ])
        action_model, = Model.search([
                ('model', '=', 'notification.email'),
                ])

        action = Action(name="Notification Email", type='ir.action.report')
        action.save()
        report = Report()
        report.report_name = 'notification_notification.test.report'
        report.action = action
        report.template_extension = 'txt'
        report.report_content = b'Hello ${records[0].name}'
        report.model = model.model
        report.save()

        user = User(Transaction().user)
        user.email = 'user@example.com'
        user.save()

        notification_email = NotificationEmail()
        notification_email.recipients, = ModelField.search([
                ('model.model', '=', model.model),
                ('name', '=', 'create_uid'),
                ])
        notification_email.content = report
        notification_email.save()

    @unittest.skipIf(
        (3, 5, 0) <= sys.version_info < (3, 5, 2), "python bug #25195")
    @with_transaction()
    def test_notification_email(self):
        "Test email notificiation is sent on trigger"
        pool = Pool()
        User = pool.get('res.user')
        Trigger = pool.get('ir.trigger')
        Model = pool.get('ir.model')
        NotificationEmail = pool.get('notification.email')
        Log = pool.get('notification.email.log')

        self._setup_notification()
        notification_email, = NotificationEmail.search([])

        model, = Model.search([
                ('model', '=', User.__name__),
                ])
        action_model, = Model.search([
                ('model', '=', 'notification.email'),
                ])
        Trigger.create([{
                    'name': 'Test creation',
                    'model': model.id,
                    'on_create': True,
                    'condition': 'true',
                    'notification_email': notification_email.id,
                    'action_model': action_model.id,
                    'action_function': 'trigger',
                    }])

        with patch.object(
                notification_module, 'sendmail_transactional') as sendmail, \
                patch.object(notification_module, 'SMTPDataManager'):
            User.create([{'name': "Michael Scott", 'login': "msc"}])
            sendmail.assert_called_once_with(
                FROM, ['user@example.com'], ANY,
                datamanager=ANY)
            _, _, msg = sendmail.call_args[0]
            self.assertEqual(msg['From'], FROM)
            self.assertEqual(msg['Subject'], 'Notification Email')
            self.assertEqual(msg['To'], 'Administrator <user@example.com>')
            self.assertEqual(msg['Auto-Submitted'], 'auto-generated')
            self.assertEqual(msg.get_content_type(), 'multipart/alternative')
            self.assertEqual(
                msg.get_payload(0).get_payload(), 'Hello Michael Scott')

        log, = Log.search([])
        self.assertEqual(log.trigger.notification_email, notification_email)
        self.assertEqual(log.recipients, 'Administrator <user@example.com>')
        self.assertEqual(log.recipients_secondary, '')
        self.assertEqual(log.recipients_hidden, '')

    @with_transaction()
    def test_notification_email_attachment(self):
        "Test email notificiation with attachment"
        pool = Pool()
        Model = pool.get('ir.model')
        Report = pool.get('ir.action.report')
        User = pool.get('res.user')
        NotificationEmail = pool.get('notification.email')
        Language = pool.get('ir.lang')

        self._setup_notification()
        model, = Model.search([
                ('model', '=', User.__name__),
                ])
        action_model, = Model.search([
                ('model', '=', 'notification.email'),
                ])
        en, = Language.search([('code', '=', 'en')])

        attachment = Report()
        attachment.name = "Attachment"
        attachment.report_name = 'notification_notification.test.report'
        attachment.template_extension = 'txt'
        attachment.report_content = b'attachment for ${records[0].name}'
        attachment.model = model.model
        attachment.save()

        notification_email, = NotificationEmail.search([])
        notification_email.attachments = [attachment]
        notification_email.save()

        user, = User.create([{'name': "Michael Scott", 'login': "msc"}])

        msg = notification_email.get_email(
            user, FROM, ['Administrator <user@example.com>'], [], [], [en])

        self.assertEqual(msg['From'], FROM)
        self.assertEqual(msg['Subject'], 'Notification Email')
        self.assertEqual(msg['To'], 'Administrator <user@example.com>')
        self.assertEqual(msg.get_content_type(), 'multipart/mixed')
        self.assertEqual(
            msg.get_payload(0).get_content_type(), 'multipart/alternative')

        attachment = msg.get_payload(1)
        self.assertEqual(
            attachment.get_payload(None, True),
            b'attachment for Michael Scott')
        self.assertEqual(
            attachment.get_content_type(), 'text/plain')
        self.assertEqual(attachment.get_filename(), "Attachment.txt")

    @unittest.skipIf(
        (3, 5, 0) <= sys.version_info < (3, 5, 2), "python bug #25195")
    @with_transaction()
    def test_notification_email_fallback(self):
        "Test email notification fallback"
        pool = Pool()
        User = pool.get('res.user')
        Trigger = pool.get('ir.trigger')
        Model = pool.get('ir.model')
        NotificationEmail = pool.get('notification.email')
        User = pool.get('res.user')

        fallback_user = User()
        fallback_user.name = 'Fallback'
        fallback_user.email = 'fallback@example.com'
        fallback_user.login = 'fallback'
        fallback_user.save()

        self._setup_notification()
        notification_email, = NotificationEmail.search([])
        notification_email.recipients = None
        notification_email.fallback_recipients = fallback_user
        notification_email.save()

        model, = Model.search([
                ('model', '=', User.__name__),
                ])
        action_model, = Model.search([
                ('model', '=', 'notification.email'),
                ])
        Trigger.create([{
                    'name': 'Test creation',
                    'model': model.id,
                    'on_create': True,
                    'condition': 'true',
                    'notification_email': notification_email.id,
                    'action_model': action_model.id,
                    'action_function': 'trigger',
                    }])

        with patch.object(
                notification_module, 'sendmail_transactional') as sendmail, \
                patch.object(notification_module, 'SMTPDataManager'):
            User.create([{'name': "Michael Scott", 'login': "msc"}])
            sendmail.assert_called_once_with(
                FROM, ['fallback@example.com'], ANY,
                datamanager=ANY)
            _, _, msg = sendmail.call_args[0]
            self.assertEqual(msg['To'], 'Fallback <fallback@example.com>')


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            NotificationEmailTestCase))
    return suite
