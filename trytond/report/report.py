# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import dateutil.tz
import os
import inspect
import logging
import math
import subprocess
import tempfile
import time
import warnings
import zipfile
import operator
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import BytesIO
from itertools import groupby

try:
    import html2text
except ImportError:
    html2text = None

try:
    import weasyprint
except ImportError:
    weasyprint = None

from genshi.filters import Translator

from trytond.i18n import gettext
from trytond.pool import Pool, PoolBase
from trytond.transaction import Transaction
from trytond.tools import slugify
from trytond.url import URLMixin
from trytond.rpc import RPC
from trytond.exceptions import UserError

warnings.simplefilter("ignore")
import relatorio.reporting  # noqa: E402
warnings.resetwarnings()
try:
    from relatorio.templates.opendocument import Manifest, MANIFEST
except ImportError:
    Manifest, MANIFEST = None, None

logger = logging.getLogger(__name__)

MIMETYPES = {
    'odt': 'application/vnd.oasis.opendocument.text',
    'odp': 'application/vnd.oasis.opendocument.presentation',
    'ods': 'application/vnd.oasis.opendocument.spreadsheet',
    'odg': 'application/vnd.oasis.opendocument.graphics',
    'txt': 'text/plain',
    'xml': 'text/xml',
    'html': 'text/html',
    'xhtml': 'text/xhtml',
    }
FORMAT2EXT = {
    'doc6': 'doc',
    'doc95': 'doc',
    'docbook': 'xml',
    'docx7': 'docx',
    'ooxml': 'xml',
    'latex': 'ltx',
    'sdc4': 'sdc',
    'sdc3': 'sdc',
    'sdd3': 'sdd',
    'sdd4': 'sdd',
    'sdw4': 'sdw',
    'sdw3': 'sdw',
    'sxd3': 'sxd',
    'sxd5': 'sxd',
    'text': 'txt',
    'xhtml': 'html',
    'xls5': 'xls',
    'xls95': 'xls',
    }

TIMEDELTA_DEFAULT_CONVERTER = {
    's': 1,
    }
TIMEDELTA_DEFAULT_CONVERTER['m'] = TIMEDELTA_DEFAULT_CONVERTER['s'] * 60
TIMEDELTA_DEFAULT_CONVERTER['h'] = TIMEDELTA_DEFAULT_CONVERTER['m'] * 60
TIMEDELTA_DEFAULT_CONVERTER['d'] = TIMEDELTA_DEFAULT_CONVERTER['h'] * 24
TIMEDELTA_DEFAULT_CONVERTER['w'] = TIMEDELTA_DEFAULT_CONVERTER['d'] * 7
TIMEDELTA_DEFAULT_CONVERTER['M'] = TIMEDELTA_DEFAULT_CONVERTER['d'] * 30
TIMEDELTA_DEFAULT_CONVERTER['Y'] = TIMEDELTA_DEFAULT_CONVERTER['d'] * 365


class TranslateFactory:

    def __init__(self, report_name, translation):
        self.report_name = report_name
        self.translation = translation

    def __call__(self, text):
        return self.translation.get_report(self.report_name, text)


class Report(URLMixin, PoolBase):

    @classmethod
    def __setup__(cls):
        super(Report, cls).__setup__()
        cls.__rpc__ = {
            'execute': RPC(),
            }

    @classmethod
    def check_access(cls):
        pool = Pool()
        ActionReport = pool.get('ir.action.report')
        User = pool.get('res.user')

        if Transaction().user == 0:
            return

        groups = set(User.get_groups())
        report_groups = ActionReport.get_groups(cls.__name__)
        if report_groups and not groups & report_groups:
            raise UserError('Calling report %s is not allowed!' % cls.__name__)

    @classmethod
    def header_key(cls, record):
        return ()

    @classmethod
    def execute(cls, ids, data):
        '''
        Execute the report on record ids.
        The dictionary with data that will be set in local context of the
        report.
        It returns a tuple with:
            report type,
            data,
            a boolean to direct print,
            the report name
        '''
        pool = Pool()
        ActionReport = pool.get('ir.action.report')
        cls.check_access()

        action_id = data.get('action_id')
        if action_id is None:
            action_reports = ActionReport.search([
                    ('report_name', '=', cls.__name__)
                    ])
            assert action_reports, '%s not found' % cls
            action_report = action_reports[0]
        else:
            action_report = ActionReport(action_id)

        def report_name(records):
            name = '-'.join(r.rec_name for r in records[:5])
            if len(records) > 5:
                name += '__' + str(len(records[5:]))
            return name

        records = []
        model = action_report.model or data.get('model')
        if model:
            records = cls._get_records(ids, model, data)

        if not records:
            groups = [[]]
            headers = [{}]
        elif action_report.single:
            groups = [[r] for r in records]
            headers = [dict(cls.header_key(r)) for r in records]
        else:
            groups = []
            headers = []
            for key, group in groupby(records, key=cls.header_key):
                groups.append(list(group))
                headers.append(dict(key))

        n = len(groups)
        if n > 1:
            padding = math.ceil(math.log10(n))
            content = BytesIO()
            with zipfile.ZipFile(content, 'w') as content_zip:
                for i, (header, group_records) in enumerate(
                        zip(headers, groups), 1):
                    oext, rcontent = cls._execute(
                        group_records, header, data, action_report)
                    filename = report_name(group_records)
                    number = str(i).zfill(padding)
                    filename = slugify('%s-%s' % (number, filename))
                    rfilename = '%s.%s' % (filename, oext)
                    content_zip.writestr(rfilename, rcontent)
            content = content.getvalue()
            oext = 'zip'
        else:
            oext, content = cls._execute(
                groups[0], headers[0], data, action_report)
        if not isinstance(content, str):
            content = bytearray(content) if bytes == str else bytes(content)
        filename = '-'.join(
            filter(None, [action_report.name, report_name(records)]))
        return (oext, content, action_report.direct_print, filename)

    @classmethod
    def _execute(cls, records, header, data, action):
        # Ensure to restore original context
        # set_lang may modify it
        with Transaction().set_context(Transaction().context):
            report_context = cls.get_context(records, header, data)
            return cls.convert(action, cls.render(action, report_context))

    @classmethod
    def _get_records(cls, ids, model, data):
        pool = Pool()
        Model = pool.get(model)
        Config = pool.get('ir.configuration')
        Lang = pool.get('ir.lang')
        context = Transaction().context

        class TranslateModel(object):
            _languages = {}

            def __init__(self, id):
                self.id = id
                self._language = Transaction().language

            def set_lang(self, language=None):
                if isinstance(language, Lang):
                    language = language.code
                if not language:
                    language = Config.get_language()
                self._language = language

            def __getattr__(self, name):
                if self._language not in TranslateModel._languages:
                    with Transaction().set_context(
                            context=context, language=self._language):
                        records = Model.browse(ids)
                    id2record = dict((r.id, r) for r in records)
                    TranslateModel._languages[self._language] = id2record
                else:
                    id2record = TranslateModel._languages[self._language]
                record = id2record[self.id]
                return getattr(record, name)

            def __int__(self):
                return int(self.id)

            def __str__(self):
                return '%s,%s' % (Model.__name__, self.id)

        return [TranslateModel(id) for id in ids]

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        User = pool.get('res.user')
        Lang = pool.get('ir.lang')

        report_context = {}
        report_context['header'] = header
        report_context['data'] = data
        report_context['context'] = Transaction().context
        report_context['user'] = User(Transaction().user)
        report_context['records'] = records
        report_context['record'] = records[0] if records else None
        report_context['format_date'] = cls.format_date
        report_context['format_datetime'] = cls.format_datetime
        report_context['format_timedelta'] = cls.format_timedelta
        report_context['format_currency'] = cls.format_currency
        report_context['format_number'] = cls.format_number
        report_context['datetime'] = datetime

        def set_lang(language=None):
            if isinstance(language, Lang):
                language = language.code
            Transaction().set_context(language=language)
        report_context['set_lang'] = set_lang

        return report_context

    @classmethod
    def _callback_loader(cls, report, template):
        if report.translatable:
            pool = Pool()
            Translation = pool.get('ir.translation')
            translate = TranslateFactory(cls.__name__, Translation)
            translator = Translator(lambda text: translate(text))
            # Do not use Translator.setup to add filter at the end
            # after set_lang evaluation
            template.filters.append(translator)
            if hasattr(template, 'add_directives'):
                template.add_directives(Translator.NAMESPACE, translator)

    @classmethod
    def render(cls, report, report_context):
        "calls the underlying templating engine to renders the report"
        template = report.get_template_cached()
        if template is None:
            mimetype = MIMETYPES[report.template_extension]
            loader = relatorio.reporting.MIMETemplateLoader()
            klass = loader.factories[loader.get_type(mimetype)]
            template = klass(BytesIO(report.report_content))
            cls._callback_loader(report, template)
            report.set_template_cached(template)
        data = template.generate(**report_context).render()
        if hasattr(data, 'getvalue'):
            data = data.getvalue()
        return data

    @classmethod
    def convert(cls, report, data, timeout=5 * 60, retry=5):
        "converts the report data to another mimetype if necessary"
        input_format = report.template_extension
        output_format = report.extension or report.template_extension

        if (weasyprint
                and input_format in {'html', 'xhtml'}
                and output_format == 'pdf'):
            return output_format, weasyprint.HTML(string=data).write_pdf()

        if output_format in MIMETYPES:
            return output_format, data

        dtemp = tempfile.mkdtemp(prefix='trytond_')
        path = os.path.join(
            dtemp, report.report_name + os.extsep + input_format)
        oext = FORMAT2EXT.get(output_format, output_format)
        mode = 'w+' if isinstance(data, str) else 'wb+'
        with open(path, mode) as fp:
            fp.write(data)
        try:
            cmd = ['soffice',
                '--headless', '--nolockcheck', '--nodefault', '--norestore',
                '--convert-to', oext, '--outdir', dtemp, path]
            output = os.path.splitext(path)[0] + os.extsep + oext
            for count in range(retry, -1, -1):
                if count != retry:
                    time.sleep(0.02 * (retry - count))
                subprocess.check_call(cmd, timeout=timeout)
                if os.path.exists(output):
                    with open(output, 'rb') as fp:
                        return oext, fp.read()
            else:
                logger.error(
                    'fail to convert %s to %s', report.report_name, oext)
                return input_format, data
        finally:
            try:
                os.remove(path)
                os.remove(output)
                os.rmdir(dtemp)
            except OSError:
                pass

    @classmethod
    def format_date(cls, value, lang=None, format=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if lang is None:
            lang = Lang.get()
        return lang.strftime(value, format=format)

    @classmethod
    def format_datetime(cls, value, lang=None, format=None, timezone=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if lang is None:
            lang = Lang.get()
        if value.tzinfo is None:
            value = value.replace(tzinfo=dateutil.tz.tzutc())
        if timezone:
            if isinstance(timezone, str):
                timezone = dateutil.tz.gettz(timezone)
            value = value.astimezone(timezone)
        return lang.strftime(value, format)

    @classmethod
    def format_timedelta(cls, value, converter=None, lang=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if lang is None:
            lang = Lang.get()
        if not converter:
            converter = TIMEDELTA_DEFAULT_CONVERTER
        if value is None:
            return ''

        def translate(k):
            xml_id = 'ir.msg_timedelta_%s' % k
            translation = gettext(xml_id)
            return translation if translation != xml_id else k

        text = []
        value = value.total_seconds()
        sign = '-' if value < 0 else ''
        value = abs(value)
        converter = sorted(
            converter.items(), key=operator.itemgetter(1), reverse=True)
        values = []
        for k, v in converter:
            part, value = divmod(value, v)
            values.append(part)

        for (k, _), v in zip(converter[:-3], values):
            if v:
                text.append(lang.format('%d', v, True) + translate(k))
        if any(values[-3:]) or not text:
            time = '%02d:%02d' % tuple(values[-3:-1])
            if values[-1] or value:
                time += ':%02d' % values[-1]
            text.append(time)
        text = sign + ' '.join(text)
        if value:
            if not any(values[-3:]):
                # Add space if no time
                text += ' '
            text += ('%.6f' % value)[1:]
        return text

    @classmethod
    def format_currency(
            cls, value, lang, currency, symbol=True, grouping=True,
            digits=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if lang is None:
            lang = Lang.get()
        return lang.currency(value, currency, symbol, grouping, digits=digits)

    @classmethod
    def format_number(cls, value, lang, digits=2, grouping=True,
            monetary=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if lang is None:
            lang = Lang.get()
        return lang.format('%.' + str(digits) + 'f', value,
            grouping=grouping, monetary=monetary)


def get_email(report, record, languages):
    "Return email.mime and title from the report execution"
    pool = Pool()
    ActionReport = pool.get('ir.action.report')
    report_id = None
    if inspect.isclass(report) and issubclass(report, Report):
        Report_ = report
    else:
        if isinstance(report, ActionReport):
            report_name = report.report_name
            report_id = report.id
        else:
            report_name = report
        Report_ = pool.get(report_name, type='report')
    converter = None
    title = None
    msg = MIMEMultipart('alternative')
    msg.add_header('Content-Language', ', '.join(l.code for l in languages))
    for language in languages:
        with Transaction().set_context(language=language.code):
            ext, content, _, title = Report_.execute(
                [record.id], {
                    'action_id': report_id,
                    'language': language,
                    })
        if ext == 'html' and html2text:
            if not converter:
                converter = html2text.HTML2Text()
            part = MIMEText(
                converter.handle(content), 'plain', _charset='utf-8')
            part.add_header('Content-Language', language.code)
            msg.attach(part)
        part = MIMEText(content, ext, _charset='utf-8')
        part.add_header('Content-Language', language.code)
        msg.attach(part)
    return msg, title
