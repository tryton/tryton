# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import sys
import unittest
from unittest.mock import patch

import trytond.config as config

try:
    from trytond.modules.company.tests import CompanyTestMixin
except ImportError:
    class CompanyTestMixin:
        pass
from trytond.modules.notification_email import \
    notification as notification_module
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.transaction import Transaction

FROM = 'tryton@example.com'


class NotificationEmailTestCase(CompanyTestMixin, ModuleTestCase):
    "Test Notification Email module"
    module = 'notification_email'
    extras = ['company', 'commission', 'party', 'web_user']

    def setUp(self):
        super().setUp()
        reset_from = config.get('email', 'from', default='')
        config.set('email', 'from', FROM)
        self.addCleanup(lambda: config.set('email', 'from', reset_from))

    def _setup_notification(self, recipient_field='create_uid'):
        pool = Pool()
        ModelField = pool.get('ir.model.field')
        Action = pool.get('ir.action')
        Report = pool.get('ir.action.report')
        User = pool.get('res.user')
        NotificationEmail = pool.get('notification.email')

        action = Action(name="Notification Email", type='ir.action.report')
        action.save()
        report = Report()
        report.report_name = 'notification_notification.test.report'
        report.action = action
        report.template_extension = 'txt'
        report.report_content = b'Hello ${records[0].name}'
        report.model = User.__name__
        report.save()

        user = User(Transaction().user)
        user.email = 'user@example.com'
        user.save()

        notification_email = NotificationEmail()
        notification_email.recipients, = ModelField.search([
                ('model', '=', User.__name__),
                ('name', '=', recipient_field),
                ])
        notification_email.content = report
        notification_email.save()

    def run_tasks(self, count=None):
        pool = Pool()
        Queue = pool.get('ir.queue')
        transaction = Transaction()
        self.assertTrue(transaction.tasks)
        i = 0
        while transaction.tasks:
            task = Queue(transaction.tasks.pop())
            task.run()
            i += 1
            if count is not None:
                if i >= count:
                    break

    @unittest.skipIf(
        (3, 5, 0) <= sys.version_info < (3, 5, 2), "python bug #25195")
    @with_transaction()
    def test_notification_email(self):
        "Test email notification is sent on trigger"
        pool = Pool()
        User = pool.get('res.user')
        Trigger = pool.get('ir.trigger')
        Model = pool.get('ir.model')
        NotificationEmail = pool.get('notification.email')
        Email = pool.get('ir.email')

        self._setup_notification()
        notification_email, = NotificationEmail.search([])

        model, = Model.search([
                ('name', '=', User.__name__),
                ])
        trigger = Trigger(
            name="Test creation",
            model=model,
            on_create_=True,
            condition='true',
            notification_email=notification_email)
        trigger.on_change_notification_email()
        self.assertEqual(trigger.action, 'notification.email|trigger')
        trigger.save()

        with patch.object(
                notification_module,
                'send_message_transactional') as send_message, \
                patch.object(notification_module, 'SMTPDataManager'):
            user, = User.create([{'name': "Michael Scott", 'login': "msc"}])
            self.run_tasks()
            send_message.assert_called_once()
            msg, = send_message.call_args[0]
            self.assertEqual(msg['From'], FROM)
            self.assertEqual(msg['Subject'], 'Notification Email')
            self.assertEqual(msg['To'], 'Administrator <user@example.com>')
            self.assertEqual(msg['Auto-Submitted'], 'auto-generated')
            self.assertEqual(
                msg.get_body().get_content(), 'Hello Michael Scott\n')

        email, = Email.search([])
        self.assertEqual(email.recipients, 'Administrator <user@example.com>')
        self.assertEqual(email.recipients_secondary, None)
        self.assertEqual(email.recipients_hidden, None)
        self.assertEqual(email.subject, 'Notification Email')
        self.assertEqual(email.resource, user)
        self.assertEqual(email.notification_email, notification_email)
        self.assertEqual(email.notification_trigger, trigger)

    @unittest.skipIf(
        (3, 5, 0) <= sys.version_info < (3, 5, 2), "python bug #25195")
    @with_transaction()
    def test_notification_email_id_recipient(self):
        "Test email notificiation is sent when using id as recipient"
        pool = Pool()
        User = pool.get('res.user')
        Trigger = pool.get('ir.trigger')
        Model = pool.get('ir.model')
        NotificationEmail = pool.get('notification.email')
        Email = pool.get('ir.email')

        self._setup_notification(recipient_field='id')
        notification_email, = NotificationEmail.search([])

        model, = Model.search([
                ('name', '=', User.__name__),
                ])
        trigger, = Trigger.create([{
                    'name': 'Test creation',
                    'model': model.id,
                    'on_create_': True,
                    'condition': 'true',
                    'notification_email': notification_email.id,
                    'action': 'notification.email|trigger',
                    }])

        with patch.object(
                notification_module,
                'send_message_transactional') as send_message, \
                patch.object(notification_module, 'SMTPDataManager'):
            user, = User.create([{
                        'name': "Michael Scott",
                        'login': "msc",
                        'email': 'msc@example.com'}])
            self.run_tasks()
            send_message.assert_called_once()

        email, = Email.search([])
        self.assertEqual(email.recipients, 'Michael Scott <msc@example.com>')
        self.assertEqual(email.resource, user)
        self.assertEqual(email.notification_email, notification_email)
        self.assertEqual(email.notification_trigger, trigger)

    @with_transaction()
    def test_notification_email_delay(self):
        "Test email notification is sent with delay"
        pool = Pool()
        User = pool.get('res.user')
        Trigger = pool.get('ir.trigger')
        Model = pool.get('ir.model')
        NotificationEmail = pool.get('notification.email')

        self._setup_notification()
        notification_email, = NotificationEmail.search([])
        notification_email.send_after = dt.timedelta(minutes=5)
        notification_email.save()

        model, = Model.search([
                ('name', '=', User.__name__),
                ])
        Trigger.create([{
                    'name': 'Test creation',
                    'model': model.id,
                    'on_create_': True,
                    'condition': 'true',
                    'notification_email': notification_email.id,
                    'action': 'notification.email|trigger',
                    }])

        with patch.object(
                notification_module,
                'send_message_transactional') as send_message, \
                patch.object(notification_module, 'SMTPDataManager'):
            User.create([{'name': "Michael Scott", 'login': "msc"}])
            self.run_tasks(1)
            send_message.assert_not_called()
            self.run_tasks()
            send_message.assert_called_once()

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
                ('name', '=', User.__name__),
                ])
        en, = Language.search([('code', '=', 'en')])

        attachment = Report()
        attachment.name = "Attachment"
        attachment.report_name = 'notification_notification.test.report'
        attachment.template_extension = 'txt'
        attachment.report_content = b'attachment for ${records[0].name}'
        attachment.model = model.name
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

        attachment = list(msg.iter_attachments())[0]
        self.assertEqual(
            attachment.get_payload(None, True),
            b'attachment for Michael Scott')
        self.assertEqual(
            attachment.get_content_type(), 'text/plain')
        self.assertEqual(
            attachment.get_filename(), "Attachment-Michael-Scott.txt")

    @with_transaction()
    def test_notification_email_subject(self):
        "Test email notificiation with subject"
        pool = Pool()
        Model = pool.get('ir.model')
        User = pool.get('res.user')
        NotificationEmail = pool.get('notification.email')
        Language = pool.get('ir.lang')

        self._setup_notification()
        model, = Model.search([
                ('name', '=', User.__name__),
                ])
        en, = Language.search([('code', '=', 'en')])

        notification_email, = NotificationEmail.search([])
        notification_email.subject = 'Notification for ${record.name}'
        notification_email.save()

        user, = User.create([{'name': "Michael Scott", 'login': "msc"}])

        msg = notification_email.get_email(
            user, FROM, ['Administrator <user@example.com>'], [], [], [en])

        self.assertEqual(msg['Subject'], 'Notification for Michael Scott')

    @with_transaction()
    def test_notification_email_translated_subject(self):
        "Test email notificiation with translated subject"
        pool = Pool()
        Model = pool.get('ir.model')
        User = pool.get('res.user')
        NotificationEmail = pool.get('notification.email')
        Language = pool.get('ir.lang')

        self._setup_notification()
        model, = Model.search([
                ('name', '=', User.__name__),
                ])
        es, = Language.search([('code', '=', 'es')])
        Language.load_translations([es])

        notification_email, = NotificationEmail.search([])
        notification_email.subject = 'Notification for ${record.name}'
        notification_email.save()

        with Transaction().set_context(lang='es'):
            notification_email, = NotificationEmail.search([])
            notification_email.subject = 'Notificación para ${record.name}'
            notification_email.save()

        user, = User.create([{
                    'name': "Michael Scott",
                    'login': "msc",
                    'language': es.id,
                    }])

        msg = notification_email.get_email(
            user, FROM, ['Administrator <user@example.com>'], [], [], [es])

        self.assertEqual(msg['Subject'], 'Notificación para Michael Scott')

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
                ('name', '=', User.__name__),
                ])
        Trigger.create([{
                    'name': 'Test creation',
                    'model': model.id,
                    'on_create_': True,
                    'condition': 'true',
                    'notification_email': notification_email.id,
                    'action': 'notification.email|trigger',
                    }])

        with patch.object(
                notification_module,
                'send_message_transactional') as send_message, \
                patch.object(notification_module, 'SMTPDataManager'):
            User.create([{'name': "Michael Scott", 'login': "msc"}])
            self.run_tasks()
            send_message.assert_called_once()
            msg, = send_message.call_args[0]
            self.assertEqual(msg['To'], 'Fallback <fallback@example.com>')

    @with_transaction()
    def test_notification_email_no_recipient(self):
        "Test email notification no recipient"
        pool = Pool()
        User = pool.get('res.user')
        Trigger = pool.get('ir.trigger')
        Model = pool.get('ir.model')
        NotificationEmail = pool.get('notification.email')
        User = pool.get('res.user')

        self._setup_notification()
        notification_email, = NotificationEmail.search([])
        notification_email.recipients = None
        notification_email.save()

        model, = Model.search([
                ('name', '=', User.__name__),
                ])
        Trigger.create([{
                    'name': 'Test creation',
                    'model': model.id,
                    'on_create_': True,
                    'condition': 'true',
                    'notification_email': notification_email.id,
                    'action': 'notification.email|trigger',
                    }])

        with patch.object(
                notification_module,
                'send_message_transactional') as send_message_transactional, \
                patch.object(notification_module, 'SMTPDataManager'):
            User.create([{'name': "Michael Scott", 'login': "msc"}])
            self.run_tasks()
            send_message_transactional.assert_not_called()


del ModuleTestCase
