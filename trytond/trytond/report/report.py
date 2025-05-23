# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import inspect
import logging
import math
import mimetypes
import operator
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import unicodedata
import warnings
import zipfile
from email.message import EmailMessage
from io import BytesIO
from itertools import groupby

import dateutil.tz

try:
    import html2text
except ImportError:
    html2text = None

try:
    import weasyprint
except ImportError:
    weasyprint = None

from genshi.filters import Translator
from genshi.template.text import TextTemplate

from trytond.config import config
from trytond.i18n import gettext
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolBase
from trytond.rpc import RPC
from trytond.tools import slugify
from trytond.transaction import Transaction, check_access
from trytond.url import URLMixin

try:
    from trytond.tools import barcode
except ImportError:
    barcode = None
try:
    from trytond.tools import qrcode
except ImportError:
    qrcode = None

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import relatorio.reporting  # noqa: E402

try:
    from relatorio.templates.opendocument import MANIFEST, Manifest
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

NO_BREAKING_SPACE = '\u00A0'

# For most OS maximum filename is 255 but Excel has a limitation which include
# the path of 218.
# As on Windows report is most likely to be open from
# C:\Users\<username>\AppData\Local\Temp\tryton_<random>\ which has a length of
# 56 with 12 for username and 8 for random. So 162 should be the maximum but we
# round it to 100.
REPORT_NAME_MAX_LENGTH = 100

CONVERT_COMMAND = config.get(
    'report', 'convert_command',
    default='soffice --headless --nolockcheck --nodefault --norestore '
    '--convert-to "%(output_extension)s" '
    '--outdir "%(directory)s" '
    '"%(input_path)s"')


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
    def check_access(cls, action, model, ids):
        pool = Pool()
        ActionReport = pool.get('ir.action.report')
        User = pool.get('res.user')
        Group = pool.get('res.group')
        ModelAccess = pool.get('ir.model.access')

        if Transaction().user == 0:
            return

        with check_access():
            groups = set(User.get_groups())
            report_groups = ActionReport.get_groups(cls.__name__, action.id)
            if report_groups and not groups & report_groups:
                groups = Group.browse(User.get_groups())
                raise AccessError(
                    gettext(
                        'ir.msg_access_report_error',
                        report=cls.__name__),
                    gettext(
                        'ir.msg_context_groups',
                        groups=', '.join(g.rec_name for g in groups)))

            if model:
                Model = pool.get(model)
                ModelAccess.check(model, 'read')
                # Check read access
                Model.read(ids, ['id'])

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
            the report name (with or without the record names)
        '''
        pool = Pool()
        ActionReport = pool.get('ir.action.report')
        context = Transaction().context
        ids = list(map(int, ids))

        action_id = data.get('action_id')
        if action_id is None:
            action_reports = ActionReport.search([
                    ('report_name', '=', cls.__name__)
                    ])
            assert action_reports, '%s not found' % cls
            action_report = action_reports[0]
        else:
            action_report = ActionReport(action_id)

        model = action_report.model or data.get('model')
        cls.check_access(action_report, model, ids)

        def report_name(records, reserved_length=0):
            names = []
            name_length = 0
            record_count = len(records)
            max_length = (REPORT_NAME_MAX_LENGTH
                - reserved_length
                - len(str(record_count)) - 2)
            if action_report.record_name:
                template = TextTemplate(action_report.record_name)
            else:
                template = None
            for record in records[:5]:
                if template:
                    record_name = template.generate(record=record).render()
                else:
                    record_name = record.rec_name
                name_length += len(
                    unicodedata.normalize('NFKD', record_name)) + 1
                if name_length > max_length:
                    break
                names.append(record_name)

            name = '-'.join(names)
            if len(records) > len(names):
                name += '__' + str(record_count - len(names))
            return name

        if model:
            records = cls._get_records(ids, model, data)
        else:
            records = []

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
        join_string = '-'
        if n > 1:
            padding = math.ceil(math.log10(n))
            content = BytesIO()
            with zipfile.ZipFile(content, 'w') as content_zip:
                for i, (header, group_records) in enumerate(
                        zip(headers, groups), 1):
                    oext, rcontent = cls._execute(
                        group_records, header, data, action_report)
                    number = str(i).zfill(padding)
                    filename = report_name(
                        group_records, len(number) + len(join_string))
                    filename = slugify(join_string.join([number, filename]))
                    rfilename = '%s.%s' % (filename, oext)
                    content_zip.writestr(rfilename, rcontent)
            content = content.getvalue()
            oext = 'zip'
        else:
            oext, content = cls._execute(
                groups[0], headers[0], data, action_report)
        if not isinstance(content, str):
            content = bytearray(content) if bytes == str else bytes(content)
        action_report_name = action_report.name[:REPORT_NAME_MAX_LENGTH]
        if context.get('with_rec_name', True):
            filename = join_string.join(
                filter(None, [
                    action_report_name,
                    report_name(
                        records, len(action_report_name) + len(join_string))]))
        else:
            filename = action_report_name
        return (oext, content, bool(action_report.direct_print), filename)

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
            __class__ = Model

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
        report_context['format_number_symbol'] = cls.format_number_symbol
        report_context['datetime'] = datetime
        if barcode:
            report_context['barcode'] = cls.barcode
        if qrcode:
            report_context['qrcode'] = cls.qrcode

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
            report.set_template_cached(template)
        cls._callback_loader(report, template)
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

        if input_format == output_format and output_format in MIMETYPES:
            return output_format, data

        directory = tempfile.mkdtemp(prefix='trytond_')
        input_extension = FORMAT2EXT.get(input_format, input_format)
        output_extension = FORMAT2EXT.get(output_format, output_format)
        path = pathlib.Path(directory, report.report_name)
        input_path = path.with_suffix(os.extsep + input_extension)
        output_path = path.with_suffix(os.extsep + output_extension)
        mode = 'w+' if isinstance(data, str) else 'wb+'
        with open(input_path, mode) as fp:
            fp.write(data)
        try:
            cmd = CONVERT_COMMAND % {
                'directory': directory,
                'input_format': input_format,
                'input_extension': input_extension,
                'input_path': input_path,
                'output_format': output_format,
                'output_extension': output_extension,
                'output_path': output_path,
                }
            for count in range(retry, -1, -1):
                if count != retry:
                    time.sleep(0.02 * (retry - count))
                try:
                    subprocess.check_call(cmd, timeout=timeout, shell=True)
                except subprocess.CalledProcessError:
                    if count:
                        continue
                    logger.error(
                        "fail to convert %s to %s",
                        report.report_name, output_format, exc_info=True)
                    break
                if os.path.exists(output_path):
                    with open(output_path, 'rb') as fp:
                        return output_extension, fp.read()
            else:
                logger.error(
                    'fail to convert %s to %s',
                    report.report_name, output_format)
            return input_format, data
        finally:
            try:
                shutil.rmtree(directory, ignore_errors=True)
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
        return text.replace(' ', NO_BREAKING_SPACE)

    @classmethod
    def format_currency(
            cls, value, lang, currency, symbol=True, grouping=True,
            digits=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if lang is None:
            lang = Lang.get()
        return lang.currency(
            value, currency, symbol=symbol, grouping=grouping, digits=digits)

    @classmethod
    def format_number(
            cls, value, lang, digits=None, grouping=True, monetary=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if lang is None:
            lang = Lang.get()
        return lang.format_number(
            value, digits=digits, grouping=grouping, monetary=monetary)

    @classmethod
    def format_number_symbol(
            cls, value, lang, symbol, digits=None, grouping=True):
        pool = Pool()
        Lang = pool.get('ir.lang')
        if lang is None:
            lang = Lang.get()
        return lang.format_number_symbol(
            value, symbol, digits=digits, grouping=grouping)

    if barcode:
        @classmethod
        def barcode(cls, name, code, size=(), **kwargs):
            image = barcode.generate_svg(name, code, **kwargs)
            return (image, 'image/svg+xml', *size)

    if qrcode:
        @classmethod
        def qrcode(cls, code, size=(), **kwargs):
            image = qrcode.generate_svg(code, **kwargs)
            return (image, 'image/svg+xml', *size)


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
    msg = EmailMessage()
    header_factory = msg.policy.header_factory
    for alternative, language in enumerate(languages):
        with Transaction().set_context(
                language=language.code, with_rec_name=False):
            ext, content, _, title = Report_.execute(
                [record.id], {
                    'action_id': report_id,
                    'language': language,
                    })
        for map in [mimetypes.types_map, mimetypes.common_types]:
            if '.' + ext in map:
                mimetype = map['.' + ext]
                maintype, subtype = mimetype.split('/')
                break
        else:
            maintype, subtype = 'application', ext
        if maintype == 'text' and subtype == 'html' and html2text:
            if not converter:
                converter = html2text.HTML2Text()
            content_text = converter.handle(content)
            msg.add_alternative(content_text, subtype='plain', headers=[
                    header_factory('Content-Language', language.code),
                    ])
        types = {
            'subtype': subtype,
            }
        if not isinstance(content, str):
            types['maintype'] = maintype
        if alternative or msg.is_multipart():
            msg.add_alternative(
                content, **types, headers=[
                    header_factory('Content-Language', language.code),
                    ])
        else:
            msg.set_content(
                content, **types, headers=[
                    header_factory('Content-Language', language.code),
                    ])
    if msg.is_multipart():
        msg.add_header(
            'Content-Language', ', '.join(l.code for l in languages))
    return msg, title
