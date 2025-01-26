# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import mimetypes
from email.utils import getaddresses

from genshi.template import TextTemplate

from trytond.config import config
from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval, TimeDelta
from trytond.report import get_email
from trytond.sendmail import SMTPDataManager, send_message_transactional
from trytond.tools.email_ import format_address, has_rcpt, set_from_header
from trytond.transaction import Transaction

from .exceptions import TemplateError


class Email(ModelSQL, ModelView):
    __name__ = 'notification.email'

    from_ = fields.Char(
        "From", translate=True,
        help="Leave empty for the value defined in the configuration file.")
    subject = fields.Char(
        "Subject", translate=True,
        help="The Genshi syntax can be used "
        "with 'record' in the evaluation context.\n"
        "If empty the report name will be used.")
    recipients = fields.Many2One(
        'ir.model.field', "Recipients",
        domain=[
            ('model', '=', Eval('model')),
            ],
        help="The field that contains the recipient(s).")
    fallback_recipients = fields.Many2One(
        'res.user', "Recipients Fallback",
        domain=[
            ('email', '!=', None),
            ],
        help="User notified when no recipients email is found.")
    recipients_secondary = fields.Many2One(
        'ir.model.field', "Secondary Recipients",
        domain=[
            ('model', '=', Eval('model')),
            ],
        help="The field that contains the secondary recipient(s).")
    fallback_recipients_secondary = fields.Many2One(
        'res.user', "Secondary Recipients Fallback",
        domain=[
            ('email', '!=', None),
            ],
        help="User notified when no secondary recipients email is found.")
    recipients_hidden = fields.Many2One(
        'ir.model.field', "Hidden Recipients",
        domain=[
            ('model', '=', Eval('model')),
            ],
        help="The field that contains the hidden recipient(s).")
    fallback_recipients_hidden = fields.Many2One(
        'res.user', "Hidden Recipients Fallback",
        domain=[
            ('email', '!=', None),
            ],
        help="User notified when no hidden recipients email is found.")

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
        help="The reports used as attachments.")

    triggers = fields.One2Many(
        'ir.trigger', 'notification_email', "Triggers",
        domain=[('model.name', '=', Eval('model'))],
        help="Add a trigger for the notification.")
    send_after = fields.TimeDelta(
        "Send After",
        domain=['OR',
            ('send_after', '=', None),
            ('send_after', '>=', TimeDelta()),
            ],
        help="The delay after which the email must be sent.\n"
        "Applied if a worker queue is activated.")

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
                        ('model.name', 'in', EmailTemplate.email_models()),
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
            # reformat addresses with encoding
            return [
                format_address(e, n)
                for n, e in getaddresses(EmailTemplate.get_addresses(value))]

    def _get_languages(self, value):
        pool = Pool()
        EmailTemplate = pool.get('ir.email.template')
        with Transaction().set_context(usage=self.contact_mechanism):
            return EmailTemplate.get_languages(value)

    def get_email(self, record, sender, to, cc, bcc, languages):
        pool = Pool()
        Attachment = pool.get('notification.email.attachment')

        # TODO order languages to get default as last one for title
        msg, title = get_email(self.content, record, languages)
        if languages:
            language = list(languages)[-1].code
        else:
            language = None
        from_ = sender
        with Transaction().set_context(language=language):
            notification = self.__class__(self.id)
            if notification.from_:
                from_ = notification.from_
            if self.subject:
                title = (TextTemplate(notification.subject)
                    .generate(record=record)
                    .render())

        if self.attachments:
            for report in self.attachments:
                name, data = Attachment.get(report, record, language)
                ctype, _ = mimetypes.guess_type(name)
                if not ctype:
                    ctype = 'application/octet-stream'
                maintype, subtype = ctype.split('/', 1)
                msg.add_attachment(
                    data,
                    maintype=maintype,
                    subtype=subtype,
                    filename=('utf-8', '', name))

        set_from_header(msg, sender, from_)
        if to:
            msg['To'] = to
        if cc:
            msg['Cc'] = cc
        if bcc:
            msg['Bcc'] = bcc
        msg['Subject'] = title
        msg['Auto-Submitted'] = 'auto-generated'
        return msg

    @classmethod
    def trigger(cls, records, trigger):
        "Action function for the triggers"
        notification_email = trigger.notification_email
        if not notification_email:
            raise ValueError(
                'Trigger "%s" is not related to any email notification'
                % trigger.rec_name)
        if notification_email.send_after:
            with Transaction().set_context(
                    queue_scheduled_at=trigger.notification_email.send_after):
                notification_email.__class__.__queue__._send_email_queued(
                    notification_email, [r.id for r in records], trigger.id)
        else:
            notification_email.send_email(records, trigger)

    def _send_email_queued(self, ids, trigger_id):
        pool = Pool()
        Model = pool.get(self.model)
        Trigger = pool.get('ir.trigger')
        records = Model.browse(ids)
        trigger = Trigger(trigger_id)
        self.send_email(records, trigger)

    def send_email(self, records, trigger):
        pool = Pool()
        Email = pool.get('ir.email')
        datamanager = SMTPDataManager()
        Transaction().join(datamanager)
        from_ = (config.get('notification_email', 'from')
            or config.get('email', 'from'))
        emails = []
        for record in records:
            to, to_languages = self._get_to(record)
            cc, cc_languages = self._get_cc(record)
            bcc, bcc_languages = self._get_bcc(record)
            languages = to_languages | cc_languages | bcc_languages
            msg = self.get_email(record, from_, to, cc, bcc, languages)
            if has_rcpt(msg):
                send_message_transactional(msg, datamanager=datamanager)
                emails.append(Email.from_message(
                        msg, resource=record,
                        notification_email=trigger.notification_email,
                        notification_trigger=trigger))
        Email.save(emails)

    def _get_recipients(self, record, name):
        if name == 'id':
            return record
        else:
            return getattr(record, name, None)

    def _get_to(self, record):
        to = []
        languages = set()
        if self.recipients:
            recipients = self._get_recipients(record, self.recipients.name)
            if recipients:
                languages.update(self._get_languages(recipients))
                to = self._get_addresses(recipients)
        if not to and self.fallback_recipients:
            languages.update(
                self._get_languages(self.fallback_recipients))
            to = self._get_addresses(self.fallback_recipients)
        return to, languages

    def _get_cc(self, record):
        cc = []
        languages = set()
        if self.recipients_secondary:
            recipients_secondary = self._get_recipients(
                record, self.recipients_secondary.name)
            if recipients_secondary:
                languages.update(
                    self._get_languages(recipients_secondary))
                cc = self._get_addresses(recipients_secondary)
        if not cc and self.fallback_recipients_secondary:
            languages.update(
                self._get_languages(self.fallback_recipients_secondary))
            cc = self._get_addresses(self.fallback_recipients_secondary)
        return cc, languages

    def _get_bcc(self, record):
        bcc = []
        languages = set()
        if self.recipients_hidden:
            recipients_hidden = self._get_recipients(
                record, self.recipients_hidden.name)
            if recipients_hidden:
                languages.update(self._get_languages(recipients_hidden))
                bcc = self._get_addresses(recipients_hidden)
        if not bcc and self.fallback_recipients_hidden:
            languages.update(
                self._get_languages(self.fallback_recipients_hidden))
            bcc = self._get_addresses(self.fallback_recipients_hidden)
        return bcc, languages

    @classmethod
    def validate_fields(cls, notifications, field_names):
        super().validate_fields(notifications, field_names)
        cls.check_subject(notifications, field_names)

    @classmethod
    def check_subject(cls, notifications, field_names=None):
        if field_names and 'subject' not in field_names:
            return
        for notification in notifications:
            if not notification.subject:
                continue
            try:
                TextTemplate(notification.subject)
            except Exception as exception:
                raise TemplateError(gettext(
                        'notification_email.'
                        'msg_notification_invalid_subject',
                        notification=notification.rec_name,
                        exception=exception)) from exception


class EmailAttachment(ModelSQL):
    __name__ = 'notification.email.attachment'

    notification = fields.Many2One(
        'notification.email', "Notification", required=True)
    report = fields.Many2One(
        'ir.action.report', "Report", required=True,
        domain=[
            ('model', '=', Eval('model')),
            ])

    model = fields.Function(fields.Char("Model"), 'get_model')

    def get_model(self, name):
        return self.notification.model

    @classmethod
    def get(cls, report, record, language):
        pool = Pool()
        Report = pool.get(report.report_name, type='report')
        with Transaction().set_context(language=language):
            ext, content, _, title = Report.execute(
                [record.id], {
                    'action_id': report.id,
                    })
        name = '%s.%s' % (title, ext)
        if isinstance(content, str):
            content = content.encode('utf-8')
        return name, content
