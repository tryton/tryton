# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, getaddresses

try:
    import html2text
except ImportError:
    html2text = None

from trytond.config import config
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.sendmail import sendmail_transactional, SMTPDataManager
from trytond.transaction import Transaction

__all__ = ['Email', 'Log']


def _formataddr(name, email):
    if name:
        name = str(Header(name, 'utf-8'))
    return formataddr((name, email))


def _get_email_template(report, record, languages):
    pool = Pool()
    Report = pool.get(report, type='report')
    converter = None
    msg = MIMEMultipart('alternative')
    msg.add_header('Content-Language', ', '.join(languages))
    # TODO order languages to get default as last one for title
    for language in languages:
        with Transaction().set_context(language=language):
            ext, content, _, title = Report.execute([record.id], {})
        if ext == 'html' and html2text:
            if not converter:
                converter = html2text.HTML2Text()
            part = MIMEText(
                converter.handle(content), 'plain', _charset='utf-8')
            part.add_header('Content-Language', language)
            msg.attach(part)
        part = MIMEText(content, ext, _charset='utf-8')
        part.add_header('Content-Language', language)
        msg.attach(part)
    return msg, title


class Email(ModelSQL, ModelView):
    "Email Notitification"
    __name__ = 'notification.email'

    from_ = fields.Char(
        "From",
        help="Leave empty for the value defined in the configuration file.")
    recipients = fields.Many2One(
        'ir.model.field', "Recipients",
        domain=[
            ('model.model', '=', Eval('model')),
            ('relation', 'in', ['res.user', 'party.party', 'web.user']),
            ],
        depends=['model'],
        help="The field that contains the recipient(s).")
    recipients_secondary = fields.Many2One(
        'ir.model.field', "Secondary Recipients",
        domain=[
            ('model.model', '=', Eval('model')),
            ('relation', 'in', ['res.user', 'party.party', 'web.user']),
            ],
        depends=['model'],
        help="The field that contains the secondary recipient(s).")
    recipients_hidden = fields.Many2One(
        'ir.model.field', "Hidden Recipients",
        domain=[
            ('model.model', '=', Eval('model')),
            ('relation', 'in', ['res.user', 'party.party', 'web.user']),
            ],
        depends=['model'],
        help="The field that contains the hidden recipient(s).")

    content = fields.Many2One(
        'ir.action.report', "Content", required=True,
        domain=[('template_extension', 'in', ['plain', 'html', 'xhtml'])],
        help="The report used as email template.")

    triggers = fields.One2Many(
        'ir.trigger', 'notification_email', "Triggers",
        domain=[('model.model', '=', Eval('model'))],
        depends=['model'],
        help="Add a trigger for the notification.")

    model = fields.Function(
        fields.Char("Model"), 'on_change_with_model', searcher='search_model')

    def get_rec_name(self, name):
        return self.content.rec_name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('content',) + tuple(clause[1:])]

    @fields.depends('content')
    def on_change_with_model(self, name=None):
        if self.content:
            return self.content.model

    @classmethod
    def search_model(cls, name, clause):
        return [('content.model',) + tuple(clause[1:])]

    def _get_address(self, record):
        pool = Pool()
        User = pool.get('res.user')
        try:
            Party = pool.get('party.party')
        except KeyError:
            Party = None
        try:
            WebUser = pool.get('web.user')
        except KeyError:
            WebUser = None
        if isinstance(record, User) and record.email:
            return _formataddr(record.rec_name, record.email)
        elif Party and isinstance(record, Party) and record.email:
            # TODO similar to address_get for contact mechanism
            return _formataddr(record.rec_name, record.email)
        elif WebUser and isinstance(record, WebUser):
            name = None
            if record.party:
                name = record.party.rec_name
            return _formataddr(name, record.email)

    def _get_addresses(self, value):
        if isinstance(value, (list, tuple)):
            addresses = [(self._get_address(v) for v in value)]
        else:
            addresses = [self._get_address(value)]
        return filter(None, addresses)

    def _get_language(self, record):
        pool = Pool()
        Configuration = pool.get('ir.configuration')
        User = pool.get('res.user')
        try:
            Party = pool.get('party.party')
        except KeyError:
            Party = None
        try:
            WebUser = pool.get('web.user')
        except KeyError:
            WebUser = None
        if isinstance(record, User):
            if record.language:
                return record.language.code
        elif Party and isinstance(record, Party):
            if record.lang:
                return record.lang.code
        elif WebUser and isinstance(record, WebUser):
            if record.party and record.party.lang:
                return record.party.lang.code
        return Configuration.get_language()

    def _get_languages(self, value):
        if isinstance(value, (list, tuple)):
            return {self._get_language(v) for v in value}
        else:
            return {self._get_language(value)}

    def get_email(self, record, from_, to, cc, bcc, languages):
        msg, title = _get_email_template(
            self.content.report_name, record, languages)
        msg['From'] = from_
        msg['To'] = ', '.join(to)
        msg['Cc'] = ', '.join(cc)
        msg['Bcc'] = ', '.join(bcc)
        msg['Subject'] = Header(title, 'utf-8')
        msg['Auto-Submitted'] = 'auto-generated'
        return msg

    def get_log(self, record, trigger, msg):
        return {
            'recipients': msg['To'],
            'recipients_secondary': msg['Cc'],
            'recipients_hidden': msg['Bcc'],
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
        Log = pool.get('notification.log')
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
            cc = []
            if self.recipients_secondary:
                recipients_secondary = getattr(
                    record, self.recipients_secondary.name, None)
                if recipients_secondary:
                    languagues.update(
                        self._get_languages(recipients_secondary))
                    cc = self._get_addresses(recipients_secondary)
            bcc = []
            if self.recipients_hidden:
                recipients_hidden = getattr(
                    record, self.recipients_hidden.name, None)
                if recipients_hidden:
                    languagues.update(self._get_languages(recipients_hidden))
                    bcc = self._get_addresses(recipients_hidden)

            msg = self.get_email(record, from_, to, cc, bcc, languagues)
            to_addrs = [e for _, e in getaddresses(to + cc + bcc)]
            if to_addrs:
                sendmail_transactional(
                    from_, to_addrs, msg, datamanager=datamanager)
                logs.append(self.get_log(record, trigger, msg))
        if logs:
            Log.create(logs)


class Log(ModelSQL, ModelView):
    "Notitification Log"
    __name__ = 'notification.log'
    date = fields.Function(fields.DateTime('Date'), 'get_date')
    recipients = fields.Char("Recipients")
    recipients_secondary = fields.Char("Secondary Recipients")
    recipients_hidden = fields.Char("Hidden Recipients")
    trigger = fields.Many2One('ir.trigger', 'Trigger', required=True)

    def get_date(self, name):
        return self.create_date.replace(microsecond=0)

    @classmethod
    def search_date(cls, name, clause):
        return [('create_date',) + tuple(clause[1:])]

    @staticmethod
    def order_date(tables):
        table, _ = tables[None]
        return [table.create_date]
