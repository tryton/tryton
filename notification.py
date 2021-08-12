# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import mimetypes
from email.encoders import encode_base64
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart
from email.utils import getaddresses

from sql import Null
from sql.operators import Concat
from genshi.template import TextTemplate

from trytond.config import config
from trytond.i18n import gettext
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.report import get_email
from trytond.sendmail import sendmail_transactional, SMTPDataManager
from trytond.transaction import Transaction
from .exceptions import TemplateError

from trytond.ir.resource import ResourceAccessMixin


class Email(ModelSQL, ModelView):
    "Email Notification"
    __name__ = 'notification.email'

    from_ = fields.Char(
        "From",
        help="Leave empty for the value defined in the configuration file.")
    subject = fields.Char(
        "Subject", translate=True,
        help="The Genshi syntax can be used "
        "with 'record' in the evaluation context.\n"
        "If empty the report name will be used.")
    recipients = fields.Many2One(
        'ir.model.field', "Recipients",
        domain=[
            ('model.model', '=', Eval('model')),
            ],
        depends=['model'],
        help="The field that contains the recipient(s).")
    fallback_recipients = fields.Many2One(
        'res.user', "Recipients Fallback User",
        domain=[
            ('email', '!=', None),
            ],
        states={
            'invisible': ~Eval('recipients'),
            },
        depends=['recipients'],
        help="User notified when no recipients e-mail is found")
    recipients_secondary = fields.Many2One(
        'ir.model.field', "Secondary Recipients",
        domain=[
            ('model.model', '=', Eval('model')),
            ],
        depends=['model'],
        help="The field that contains the secondary recipient(s).")
    fallback_recipients_secondary = fields.Many2One(
        'res.user', "Secondary Recipients Fallback User",
        domain=[
            ('email', '!=', None),
            ],
        states={
            'invisible': ~Eval('recipients_secondary'),
            },
        depends=['recipients'],
        help="User notified when no secondary recipients e-mail is found")
    recipients_hidden = fields.Many2One(
        'ir.model.field', "Hidden Recipients",
        domain=[
            ('model.model', '=', Eval('model')),
            ],
        depends=['model'],
        help="The field that contains the hidden recipient(s).")
    fallback_recipients_hidden = fields.Many2One(
        'res.user', "Hidden Recipients Fallback User",
        domain=[
            ('email', '!=', None),
            ],
        states={
            'invisible': ~Eval('recipients_hidden'),
            },
        depends=['recipients_hidden'],
        help="User notified when no hidden recipients e-mail is found")

    contact_mechanism = fields.Selection(
        'get_contact_mechanisms', "Contact Mechanism",
        help="Define which email to use from the party's contact mechanisms")

    content = fields.Many2One(
        'ir.action.report', "Content", required=True,
        domain=[('template_extension', 'in', ['txt', 'html', 'xhtml'])],
        help="The report used as email template.")
    attachments = fields.Many2Many(
        'notification.email.attachment', 'notification', 'report',
        "Attachments",
        domain=[
            ('model', '=', Eval('model')),
            ],
        depends=['model'],
        help="The reports used as attachments.")

    triggers = fields.One2Many(
        'ir.trigger', 'notification_email', "Triggers",
        domain=[('model.model', '=', Eval('model'))],
        depends=['model'],
        help="Add a trigger for the notification.")

    model = fields.Function(
        fields.Char("Model"), 'on_change_with_model', searcher='search_model')

    @classmethod
    def __setup__(cls):
        pool = Pool()
        EmailTemplate = pool.get('ir.email.template')
        super().__setup__()
        for field in [
                'recipients',
                'recipients_secondary',
                'recipients_hidden',
                ]:
            field = getattr(cls, field)
            field.domain.append(['OR',
                    ('relation', 'in', EmailTemplate.email_models()),
                    [
                        ('model.model', 'in', EmailTemplate.email_models()),
                        ('name', '=', 'id'),
                        ],
                    ])

    def get_rec_name(self, name):
        return self.content.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('content',) + tuple(clause[1:])]

    @classmethod
    def get_contact_mechanisms(cls):
        pool = Pool()
        try:
            ContactMechanism = pool.get('party.contact_mechanism')
        except KeyError:
            return [(None, "")]
        return ContactMechanism.usages()

    @fields.depends('content')
    def on_change_with_model(self, name=None):
        if self.content:
            return self.content.model

    @classmethod
    def search_model(cls, name, clause):
        return [('content.model',) + tuple(clause[1:])]

    def _get_addresses(self, value):
        pool = Pool()
        EmailTemplate = pool.get('ir.email.template')
        with Transaction().set_context(usage=self.contact_mechanism):
            return EmailTemplate.get_addresses(value)

    def _get_languages(self, value):
        pool = Pool()
        EmailTemplate = pool.get('ir.email.template')
        return EmailTemplate.get_languages(value)

    def get_email(self, record, from_, to, cc, bcc, languages):
        pool = Pool()
        Attachment = pool.get('notification.email.attachment')

        # TODO order languages to get default as last one for title
        content, title = get_email(self.content, record, languages)
        language = list(languages)[-1]
        if self.subject:
            with Transaction().set_context(language=language.code):
                notification = self.__class__(self.id)
                title = (TextTemplate(notification.subject)
                    .generate(record=record)
                    .render())

        if self.attachments:
            msg = MIMEMultipart('mixed')
            msg.attach(content)
            for report in self.attachments:
                msg.attach(Attachment.get_mime(report, record, language.code))
        else:
            msg = content

        msg['From'] = from_
        msg['To'] = ', '.join(to)
        msg['Cc'] = ', '.join(cc)
        msg['Subject'] = Header(title, 'utf-8')
        msg['Auto-Submitted'] = 'auto-generated'
        return msg

    def get_log(self, record, trigger, msg, bcc=None):
        return {
            'recipients': msg['To'],
            'recipients_secondary': msg['Cc'],
            'recipients_hidden': bcc,
            'resource': str(record),
            'notification': trigger.notification_email.id,
            'trigger': trigger.id,
            }

    @classmethod
    def trigger(cls, records, trigger):
        "Action function for the triggers"
        if not trigger.notification_email:
            raise ValueError(
                'Trigger "%s" is not related to any email notification'
                % trigger.rec_name)
        trigger.notification_email.send_email(records, trigger)

    def send_email(self, records, trigger):
        pool = Pool()
        Log = pool.get('notification.email.log')
        datamanager = SMTPDataManager()
        Transaction().join(datamanager)
        from_ = self.from_ or config.get('email', 'from')
        logs = []
        for record in records:
            languagues = set()
            to = []
            if self.recipients:
                recipients = getattr(record, self.recipients.name, None)
                if recipients:
                    languagues.update(self._get_languages(recipients))
                    to = self._get_addresses(recipients)
            if not to and self.fallback_recipients:
                languagues.update(
                    self._get_languages(self.fallback_recipients))
                to = self._get_addresses(self.fallback_recipients)

            cc = []
            if self.recipients_secondary:
                recipients_secondary = getattr(
                    record, self.recipients_secondary.name, None)
                if recipients_secondary:
                    languagues.update(
                        self._get_languages(recipients_secondary))
                    cc = self._get_addresses(recipients_secondary)
            if not cc and self.fallback_recipients_secondary:
                languagues.update(
                    self._get_languages(self.fallback_recipients_secondary))
                cc = self._get_addresses(self.fallback_recipients_secondary)

            bcc = []
            if self.recipients_hidden:
                recipients_hidden = getattr(
                    record, self.recipients_hidden.name, None)
                if recipients_hidden:
                    languagues.update(self._get_languages(recipients_hidden))
                    bcc = self._get_addresses(recipients_hidden)
            if not bcc and self.fallback_recipients_hidden:
                languagues.update(
                    self._get_languages(self.fallback_recipients_hidden))
                bcc = self._get_addresses(self.fallback_recipients_hidden)

            to_addrs = [e for _, e in getaddresses(to + cc + bcc)]
            if to_addrs:
                msg = self.get_email(record, from_, to, cc, bcc, languagues)
                sendmail_transactional(
                    from_, to_addrs, msg, datamanager=datamanager)
                logs.append(self.get_log(
                        record, trigger, msg, bcc=', '.join(bcc)))
        if logs:
            Log.create(logs)

    @classmethod
    def validate(cls, notifications):
        super().validate(notifications)
        for notification in notifications:
            notification.check_subject()

    def check_subject(self):
        if not self.subject:
            return
        try:
            TextTemplate(self.subject)
        except Exception as exception:
            raise TemplateError(
                gettext('notification_email.'
                    'msg_notification_invalid_subject',
                    notification=self.rec_name,
                    exception=exception)) from exception


class EmailAttachment(ModelSQL):
    "Email Notification Attachment"
    __name__ = 'notification.email.attachment'

    notification = fields.Many2One(
        'notification.email', "Notification",
        required=True, select=True)
    report = fields.Many2One(
        'ir.action.report', "Report", required=True,
        domain=[
            ('model', '=', Eval('model')),
            ],
        depends=['model'])

    model = fields.Function(fields.Char("Model"), 'get_model')

    def get_model(self, name):
        return self.notification.model

    @classmethod
    def get_mime(cls, report, record, language):
        pool = Pool()
        Report = pool.get(report.report_name, type='report')
        with Transaction().set_context(language=language):
            ext, content, _, title = Report.execute(
                [record.id], {
                    'action_id': report.id,
                    })
        name = '%s.%s' % (title, ext)
        mimetype, _ = mimetypes.guess_type(name)
        if mimetype:
            msg = MIMENonMultipart(*mimetype.split('/'))
            msg.set_payload(content)
            encode_base64(msg)
        else:
            msg = MIMEApplication(content)
        if not isinstance(name, str):
            name = name.encode('utf-8')
        if not isinstance(language, str):
            language = language.encode('utf-8')
        msg.add_header(
            'Content-Disposition', 'attachment',
            filename=('utf-8', language, name))
        return msg


class EmailLog(ResourceAccessMixin, ModelSQL, ModelView):
    "Notification Email Log"
    __name__ = 'notification.email.log'
    date = fields.Function(fields.DateTime('Date'), 'get_date')
    recipients = fields.Char("Recipients")
    recipients_secondary = fields.Char("Secondary Recipients")
    recipients_hidden = fields.Char("Hidden Recipients")
    notification = fields.Many2One(
        'notification.email', "Notification",
        required=True, ondelete='RESTRICT')
    trigger = fields.Many2One('ir.trigger', "Trigger")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order = [
            ('create_date', 'DESC'),
            ('id', 'DESC'),
            ]

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Model = pool.get('ir.model')
        Trigger = pool.get('ir.trigger')
        model = Model.__table__()
        trigger = Trigger.__table__()
        table = cls.__table__()
        super().__register__(module_name)

        table_h = cls.__table_handler__(module_name)
        cursor = Transaction().connection.cursor()

        # Migration from 5.6:
        # fill notification and resource
        # remove required on trigger
        notification = trigger.select(
            trigger.notification_email,
            where=trigger.id == table.trigger)
        resource = (trigger
            .join(model, condition=trigger.model == model.id)
            .select(
                Concat(model.model, ',-1'),
                where=trigger.id == table.trigger))
        cursor.execute(*table.update(
                [table.notification, table.resource],
                [notification, resource],
                where=table.trigger != Null))
        table_h.not_null_action('trigger', 'remove')

    def get_date(self, name):
        return self.create_date.replace(microsecond=0)

    @classmethod
    def search_date(cls, name, clause):
        return [('create_date',) + tuple(clause[1:])]

    @staticmethod
    def order_date(tables):
        table, _ = tables[None]
        return [table.create_date]
