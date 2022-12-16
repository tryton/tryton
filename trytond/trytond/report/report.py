# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import datetime
import tempfile
import warnings
import subprocess
warnings.simplefilter("ignore")
import relatorio.reporting
warnings.resetwarnings()
try:
    from relatorio.templates.opendocument import Manifest, MANIFEST
except ImportError:
    Manifest, MANIFEST = None, None
from genshi.filters import Translator
from trytond.config import config
from trytond.pool import Pool, PoolBase
from trytond.transaction import Transaction
from trytond.url import URLMixin
from trytond.rpc import RPC
from trytond.exceptions import UserError
from trytond.tools import get_parent_language

MIMETYPES = {
    'odt': 'application/vnd.oasis.opendocument.text',
    'odp': 'application/vnd.oasis.opendocument.presentation',
    'ods': 'application/vnd.oasis.opendocument.spreadsheet',
    'odg': 'application/vnd.oasis.opendocument.graphics',
    'plain': 'text/plain',
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


class ReportFactory:

    def __call__(self, records, **kwargs):
        data = {}
        data['objects'] = records  # XXX To remove
        data['records'] = records
        data.update(kwargs)
        return data


class TranslateFactory:

    def __init__(self, report_name, language, translation):
        self.report_name = report_name
        self.language = language
        self.translation = translation
        self.cache = {}

    def __call__(self, text):
        if self.language not in self.cache:
            cache = self.cache[self.language] = {}
            code = self.language
            while code:
                translations = self.translation.search([
                    ('lang', '=', code),
                    ('type', '=', 'report'),
                    ('name', '=', self.report_name),
                    ('value', '!=', ''),
                    ('value', '!=', None),
                    ('fuzzy', '=', False),
                    ('res_id', '=', -1),
                    ])
                for translation in translations:
                    cache.setdefault(translation.src, translation.value)
                code = get_parent_language(code)
        return self.cache[self.language].get(text, text)

    def set_language(self, language):
        self.language = language


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

        records = None
        model = action_report.model or data.get('model')
        if model:
            records = cls._get_records(ids, model, data)
        report_context = cls.get_context(records, data)
        oext, content = cls.convert(action_report,
            cls.render(action_report, report_context))
        if not isinstance(content, unicode):
            content = bytearray(content) if bytes == str else bytes(content)
        return (oext, content, action_report.direct_print, action_report.name)

    @classmethod
    def _get_records(cls, ids, model, data):
        pool = Pool()
        Model = pool.get(model)

        class TranslateModel:
            _languages = {}

            def __init__(self, id):
                self.id = id
                self._language = Transaction().language

            def set_lang(self, language):
                self._language = language

            def __getattr__(self, name):
                if self._language not in TranslateModel._languages:
                    with Transaction().set_context(language=self._language):
                        records = Model.browse(ids)
                    id2record = dict((r.id, r) for r in records)
                    TranslateModel._languages[self._language] = id2record
                else:
                    id2record = TranslateModel._languages[self._language]
                record = id2record[self.id]
                return getattr(record, name)
        return [TranslateModel(id) for id in ids]

    @classmethod
    def get_context(cls, records, data):
        pool = Pool()
        User = pool.get('res.user')

        report_context = {}
        report_context['data'] = data
        report_context['context'] = Transaction().context
        report_context['user'] = User(Transaction().user)
        report_context['records'] = records
        report_context['format_date'] = cls.format_date
        report_context['format_currency'] = cls.format_currency
        report_context['format_number'] = cls.format_number
        report_context['datetime'] = datetime

        return report_context

    @classmethod
    def _prepare_template_file(cls, report):
        # Convert to str as value from DB is not supported by StringIO
        report_content = (bytes(report.report_content) if report.report_content
            else None)
        if not report_content:
            raise Exception('Error', 'Missing report file!')

        fd, path = tempfile.mkstemp(
            suffix=(os.extsep + report.template_extension),
            prefix='trytond_')
        with open(path, 'wb') as f:
            f.write(report_content)
        return fd, path

    @classmethod
    def _add_translation_hook(cls, relatorio_report, context):
        pool = Pool()
        Translation = pool.get('ir.translation')

        translate = TranslateFactory(cls.__name__, Transaction().language,
            Translation)
        context['set_lang'] = lambda language: translate.set_language(language)
        translator = Translator(lambda text: translate(text))
        relatorio_report.filters.insert(0, translator)

    @classmethod
    def render(cls, report, report_context):
        "calls the underlying templating engine to renders the report"
        fd, path = cls._prepare_template_file(report)

        mimetype = MIMETYPES[report.template_extension]
        rel_report = relatorio.reporting.Report(path, mimetype,
                ReportFactory(), relatorio.reporting.MIMETemplateLoader())
        cls._add_translation_hook(rel_report, report_context)

        data = rel_report(**report_context).render()
        if hasattr(data, 'getvalue'):
            data = data.getvalue()
        os.close(fd)
        os.remove(path)

        return data

    @classmethod
    def convert(cls, report, data):
        "converts the report data to another mimetype if necessary"
        input_format = report.template_extension
        output_format = report.extension or report.template_extension

        if output_format in MIMETYPES:
            return output_format, data

        fd, path = tempfile.mkstemp(suffix=(os.extsep + input_format),
            prefix='trytond_')
        oext = FORMAT2EXT.get(output_format, output_format)
        with os.fdopen(fd, 'wb+') as fp:
            fp.write(data)
        cmd = ['unoconv', '--connection=%s' % config.get('report', 'unoconv'),
            '-f', oext, '--stdout', path]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            stdoutdata, stderrdata = proc.communicate()
            if proc.wait() != 0:
                raise Exception(stderrdata)
            return oext, stdoutdata
        finally:
            os.remove(path)

    @classmethod
    def format_date(cls, value, lang):
        pool = Pool()
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if lang:
            locale_format = lang.date
            code = lang.code
        else:
            locale_format = Lang.default_date()
            code = Config.get_language()
        return Lang.strftime(value, code, locale_format)

    @classmethod
    def format_currency(cls, value, lang, currency, symbol=True,
            grouping=True):
        pool = Pool()
        Lang = pool.get('ir.lang')

        return Lang.currency(lang, value, currency, symbol, grouping)

    @classmethod
    def format_number(cls, value, lang, digits=2, grouping=True,
            monetary=None):
        pool = Pool()
        Lang = pool.get('ir.lang')

        return Lang.format(lang, '%.' + str(digits) + 'f', value,
            grouping=grouping, monetary=monetary)
