# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import heapq
import mimetypes
import re
from email.message import EmailMessage
from email.utils import getaddresses

try:
    import html2text
except ImportError:
    html2text = None
from genshi.template import TextTemplate

from trytond.config import config
from trytond.i18n import gettext
from trytond.model import EvalEnvironment, ModelSQL, ModelView, fields
from trytond.model.exceptions import AccessError, ValidationError
from trytond.pool import Pool
from trytond.pyson import Bool, Eval, PYSONDecoder
from trytond.report import Report
from trytond.rpc import RPC
from trytond.sendmail import send_message_transactional
from trytond.tools import escape_wildcard
from trytond.tools.email_ import (
    convert_ascii_email, format_address, set_from_header)
from trytond.tools.string_ import StringMatcher
from trytond.transaction import Transaction

from .resource import ResourceAccessMixin

HTML_EMAIL = """<!DOCTYPE html>
<html>
<head><title>%(subject)s</title></head>
<body>%(body)s<br/>
<hr style="width: 2em; text-align: start; display: inline-block"/><br/>
%(signature)s</body>
</html>"""
specialsre = re.compile(r'[][\\()<>@,:;".]')
escapesre = re.compile(r'[\\"]')


class EmailTemplateError(ValidationError):
    pass


def _formataddr(pair):
    "Format address without encoding"
    name, address = pair
    convert_ascii_email(address).encode('ascii')
    if name:
        quotes = ''
        if specialsre.search(name):
            quotes = '"'
        name = escapesre.sub(r'\\\g<0>', name)
        return '%s%s%s <%s>' % (quotes, name, quotes, address)
    return address


class Email(ResourceAccessMixin, ModelSQL, ModelView):
    "Email"
    __name__ = 'ir.email'

    user = fields.Function(fields.Char("User"), 'get_user')
    at = fields.Function(fields.DateTime("At"), 'get_at')
    recipients = fields.Char("Recipients", readonly=True)
    recipients_secondary = fields.Char("Secondary Recipients", readonly=True)
    recipients_hidden = fields.Char("Hidden Recipients", readonly=True)
    addresses = fields.One2Many(
        'ir.email.address', 'email', "Addresses", readonly=True)
    subject = fields.Char("Subject", readonly=True)
    body = fields.Text("Body", readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._order.insert(0, ('create_date', 'DESC'))
        cls.__rpc__.update({
                'send': RPC(readonly=False, result=int),
                'complete': RPC(check_access=False),
                })
        del cls.__rpc__['create']

    def get_user(self, name):
        return self.create_uid.rec_name

    def get_at(self, name):
        return self.create_date.replace(microsecond=0)

    @classmethod
    def send(cls, to='', cc='', bcc='', subject='', body='',
            files=None, record=None, reports=None, attachments=None):
        pool = Pool()
        User = pool.get('res.user')
        ActionReport = pool.get('ir.action.report')
        Attachment = pool.get('ir.attachment')
        transaction = Transaction()
        user = User(transaction.user)

        Model = pool.get(record[0])
        record = Model(record[1])

        msg = EmailMessage()

        body_html = HTML_EMAIL % {
            'subject': subject,
            'body': body,
            'signature': user.signature or '',
            }
        if html2text:
            body_text = HTML_EMAIL % {
                'subject': subject,
                'body': body,
                'signature': '',
                }
            converter = html2text.HTML2Text()
            body_text = converter.handle(body_text)
            if user.signature:
                body_text += '\n-- \n' + converter.handle(user.signature)
            msg.add_alternative(body_text, subtype='plain')
        if msg.is_multipart():
            msg.add_alternative(body_html, subtype='html')
        else:
            msg.set_content(body_html, subtype='html')
        if files or reports or attachments:
            if files is None:
                files = []
            else:
                files = list(files)

            for report_id in (reports or []):
                report = ActionReport(report_id)
                Report = pool.get(report.report_name, type='report')
                ext, content, _, title = Report.execute(
                    [record.id], {
                        'action_id': report.id,
                        })
                name = '%s.%s' % (title, ext)
                if isinstance(content, str):
                    content = content.encode('utf-8')
                files.append((name, content))
            if attachments:
                files += [
                    (a.name, a.data) for a in Attachment.browse(attachments)]
            for name, data in files:
                ctype, _ = mimetypes.guess_type(name)
                if not ctype:
                    ctype = 'application/octet-stream'
                maintype, subtype = ctype.split('/', 1)
                msg.add_attachment(
                    data,
                    maintype=maintype,
                    subtype=subtype,
                    filename=('utf-8', '', name))
        from_ = config.get('email', 'from')
        set_from_header(msg, from_, user.email or from_)
        msg['To'] = [format_address(a, n) for n, a in getaddresses([to])]
        msg['Cc'] = [format_address(a, n) for n, a in getaddresses([cc])]
        msg['Bcc'] = [format_address(a, n) for n, a in getaddresses([bcc])]
        msg['Subject'] = subject

        send_message_transactional(msg, strict=True)

        email = cls.from_message(msg, body=body, resource=record)
        email.save()
        if files:
            attachments_ = []
            for name, data in files:
                attachments_.append(
                    Attachment(resource=email, name=name, data=data))
            Attachment.save(attachments_)
        return email

    @classmethod
    def complete(cls, text, limit):
        limit = int(limit)
        if not limit > 0:
            raise ValueError('limit must be > 0: %r' % (limit,))
        emails = getaddresses([text])
        if not emails:
            return []
        name, email = map(str.strip, emails[-1])
        if not name and not email:
            return []
        s = StringMatcher()
        try:
            s.set_seq2(_formataddr((name, email)))
        except UnicodeEncodeError:
            return []

        def generate(name, email):
            for name, email in cls._match(name, email):
                try:
                    address = _formataddr((name, email))
                except UnicodeEncodeError:
                    continue
                s.set_seq1(address)
                yield (
                    s.ratio(), address,
                    ', '.join(map(_formataddr, emails[:-1] + [(name, email)])))
        return heapq.nlargest(limit, generate(name, email))

    @classmethod
    def _match(cls, name, email):
        pool = Pool()
        User = pool.get('res.user')
        domain = ['OR']
        for field in ['name', 'login', 'email']:
            for value in [name, email]:
                if value and len(value) >= 3:
                    domain.append(
                        (field, 'ilike', '%' + escape_wildcard(value) + '%'))
        for user in User.search([
                    ('email', '!=', ''),
                    domain,
                    ], order=[]):
            yield user.name, user.email

    @classmethod
    def from_message(cls, msg, **values):
        to_addrs = [e for _, e in getaddresses(
                filter(None, (msg['To'], msg['Cc'], msg['Bcc'])))]
        return cls(
            recipients=msg['To'],
            recipients_secondary=msg['Cc'],
            recipients_hidden=msg['Bcc'],
            addresses=[{'address': a} for a in to_addrs],
            subject=msg['Subject'],
            **values)


class EmailAddress(ModelSQL):
    "Email Address"
    __name__ = 'ir.email.address'

    email = fields.Many2One(
        'ir.email', "E-mail", required=True, ondelete='CASCADE')
    address = fields.Char("Address", required=True)


class EmailTemplate(ModelSQL, ModelView):
    "Email Template"
    __name__ = 'ir.email.template'

    model = fields.Many2One('ir.model', "Model", required=True)
    name = fields.Char("Name", required=True, translate=True)
    recipients = fields.Many2One(
        'ir.model.field', "Recipients",
        states={
            'invisible': Bool(Eval('recipients_pyson')),
            },
        depends=['recipients_pyson'],
        help="The field that contains the recipient(s).")
    recipients_pyson = fields.Char(
        "Recipients",
        states={
            'invisible': Bool(Eval('recipients')),
            },
        depends=['recipients'],
        help="A PYSON expression that generates a list of recipients "
        'with the record represented by "self".')
    recipients_secondary = fields.Many2One(
        'ir.model.field', "Secondary Recipients",
        states={
            'invisible': Bool(Eval('recipients_secondary_pyson')),
            },
        depends=['recipients_secondary_pyson'],
        help="The field that contains the secondary recipient(s).")
    recipients_secondary_pyson = fields.Char(
        "Secondary Recipients",
        states={
            'invisible': Bool(Eval('recipients_secondary')),
            },
        depends=['recipients_secondary'],
        help="A PYSON expression that generates a list "
        'of secondary recipients with the record represented by "self".')
    recipients_hidden = fields.Many2One(
        'ir.model.field', "Hidden Recipients",
        states={
            'invisible': Bool(Eval('recipients_hidden_pyson')),
            },
        depends=['recipients_hidden_pyson'],
        help="The field that contains the secondary recipient(s).")
    recipients_hidden_pyson = fields.Char(
        "Hidden Recipients",
        states={
            'invisible': Bool(Eval('recipients_hidden')),
            },
        depends=['recipients_hidden'],
        help="A PYSON expression that generates a list of hidden recipients "
        'with the record represented by "self".')
    subject = fields.Char("Subject", translate=True)
    body = fields.Text("Body", translate=True)
    reports = fields.Many2Many(
        'ir.email.template-ir.action.report', 'template', 'report',
        "Reports",
        domain=[
            ('model', '=', Eval('model_name')),
            ],
        depends=['model_name'])

    model_name = fields.Function(
        fields.Char("Model Name"), 'on_change_with_model_name')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        for field in [
                'recipients',
                'recipients_secondary',
                'recipients_hidden',
                ]:
            field = getattr(cls, field)
            field.domain = [
                ('model_ref.id', '=', Eval('model', -1)),
                ['OR',
                    ('relation', 'in', cls.email_models()),
                    [
                        ('model', 'in', cls.email_models()),
                        ('name', '=', 'id'),
                        ],
                    ]
                ]
            field.depends.add('model')
        cls.__rpc__.update({
                'get': RPC(instantiate=0),
                'get_default': RPC(),
                })

    @fields.depends('model')
    def on_change_with_model_name(self, name=None):
        if self.model:
            return self.model.model

    @classmethod
    def validate_fields(cls, templates, field_names):
        super().validate_fields(templates, field_names)
        cls.check_subject(templates, field_names)
        cls.check_body(templates, field_names)
        cls.check_fields_pyson(templates, field_names)

    @classmethod
    def check_subject(cls, templates, field_names=None):
        if field_names and 'subject' not in field_names:
            return
        for template in templates:
            if not template.subject:
                continue
            try:
                TextTemplate(template.subject)
            except Exception as exception:
                raise EmailTemplateError(gettext(
                        'ir.msg_email_template_invalid_subject',
                        template=template.rec_name,
                        exception=exception)) from exception

    @classmethod
    def check_body(self, templates, field_names=None):
        if field_names and 'body' not in field_names:
            return
        for template in templates:
            if not template.body:
                continue
            try:
                TextTemplate(template.body)
            except Exception as exception:
                raise EmailTemplateError(gettext(
                        'ir.msg_email_template_invalid_body',
                        template=template.rec_name,
                        exception=exception)) from exception

    @classmethod
    def check_fields_pyson(cls, templates, field_names=None):
        pyson_fields = {
            'recipients_pyson',
            'recipients_secondary_pyson',
            'recipients_hidden_pyson',
            }
        if field_names:
            pyson_fields &= field_names
        if not pyson_fields:
            return
        encoder = PYSONDecoder(noeval=True)
        for template in templates:
            for field in pyson_fields:
                value = getattr(template, field)
                if not value:
                    continue
                try:
                    pyson = encoder.decode(value)
                except Exception as exception:
                    raise EmailTemplateError(
                        gettext('ir.msg_email_template_invalid_field_pyson',
                            template=template.rec_name,
                            field=cls.__names__(field)['field'],
                            exception=exception)) from exception
                if not isinstance(pyson, list) and pyson.types() != {list}:
                    raise EmailTemplateError(gettext(
                            'ir.msg_email_template_invalid_field_pyson_type',
                            template=template.rec_name,
                            field=cls.__names__(field)['field'],
                            ))

    def get(self, record):
        pool = Pool()
        Model = pool.get(self.model.model)
        record = Model(int(record))

        values = {}
        for attr, key in [
                ('recipients', 'to'),
                ('recipients_secondary', 'cc'),
                ('recipients_hidden', 'bcc'),
                ]:
            field = getattr(self, attr)
            try:
                if field:
                    if field.name == 'id':
                        value = record
                    else:
                        value = getattr(record, field.name, None)
                    if value:
                        values[key] = self.get_addresses(value)
                else:
                    value = getattr(self, attr + '_pyson')
                    if value:
                        value = self.eval(record, value)
                        if value:
                            values[key] = self.get_addresses(value)
            except AccessError:
                continue

        if self.subject:
            try:
                values['subject'] = (TextTemplate(self.subject)
                    .generate(**self.get_context(record))
                    .render())
            except AccessError:
                pass
        if self.body:
            try:
                values['body'] = (TextTemplate(self.body)
                    .generate(**self.get_context(record))
                    .render())
            except AccessError:
                pass
        if self.reports:
            values['reports'] = [r.id for r in self.reports]
        return values

    def get_context(self, record):
        pool = Pool()
        User = pool.get('res.user')
        return {
            'context': Transaction().context,
            'user': User(Transaction().user),
            'record': record,
            'format_date': Report.format_date,
            'format_datetime': Report.format_datetime,
            'format_timedelta': Report.format_timedelta,
            'format_currency': Report.format_currency,
            'format_number': Report.format_number,
            }

    def eval(self, record, pyson, _env=None):
        'Evaluate the pyson with the record'
        if _env is None:
            env = {}
        else:
            env = _env.copy()
        env['context'] = Transaction().context
        env['self'] = EvalEnvironment(record, record.__class__)
        return PYSONDecoder(env).decode(pyson)

    @classmethod
    def _get_default_exclude(cls, record):
        return ['create_uid', 'write_uid']

    @classmethod
    def get_default(cls, model, record):
        pool = Pool()
        Field = pool.get('ir.model.field')
        Model = pool.get(model)
        record = Model(int(record))
        values = {}

        fields = Field.search([
                ('model.model', '=', model),
                ('name', 'not in', cls._get_default_exclude(record)),
                ['OR',
                    ('relation', 'in', cls.email_models()),
                    [
                        ('model.model', 'in', cls.email_models()),
                        ('name', '=', 'id'),
                        ],
                    ],
                ])
        addresses = set()
        for field in fields:
            try:
                if field.name == 'id':
                    value = record
                else:
                    value = getattr(record, field.name)
                addresses.update(cls.get_addresses(value))
            except AccessError:
                pass
        values['to'] = list(addresses)

        try:
            values['subject'] = '%s: %s' % (
                Model.__names__()['model'], record.rec_name)
        except AccessError:
            pass
        return values

    @classmethod
    def email_models(cls):
        return ['res.user']

    @classmethod
    def get_addresses(cls, value):
        if isinstance(value, (list, tuple)):
            addresses = (cls._get_address(v) for v in value)
        else:
            addresses = [cls._get_address(value)]
        return [
            _formataddr((name, email))
            for name, email in filter(None, addresses)
            if email]

    @classmethod
    def _get_address(cls, record):
        pool = Pool()
        User = pool.get('res.user')
        if isinstance(record, str):
            return (None, record)
        elif isinstance(record, User) and record.email:
            return (record.name, record.email)

    @classmethod
    def get_languages(cls, value):
        pool = Pool()
        Configuration = pool.get('ir.configuration')
        Lang = pool.get('ir.lang')
        if isinstance(value, (list, tuple)):
            languages = {cls._get_language(v) for v in value}
        else:
            languages = {cls._get_language(value)}
        languages = list(filter(None, languages))
        if not languages:
            return Lang.search([
                    ('code', '=', Configuration.get_language()),
                    ], limit=1)
        return languages

    @classmethod
    def _get_language(cls, record):
        pool = Pool()
        User = pool.get('res.user')
        if isinstance(record, User) and record.language:
            return record.language

    @classmethod
    def create(cls, vlist):
        ModelView._view_toolbar_get_cache.clear()
        return super().create(vlist)

    @classmethod
    def write(cls, *args):
        if any({'name', 'model'} & v.keys() for v in args[1:None:2]):
            ModelView._view_toolbar_get_cache.clear()
        super().write(*args)

    @classmethod
    def delete(cls, records):
        ModelView._view_toolbar_get_cache.clear()
        super().delete(records)


class EmailTemplate_Report(ModelSQL):
    "Email Template - Report"
    __name__ = 'ir.email.template-ir.action.report'

    template = fields.Many2One(
        'ir.email.template', "Template", required=True, ondelete='CASCADE')
    report = fields.Many2One(
        'ir.action.report', "Report", required=True, ondelete='CASCADE')
