#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import zipfile
import time
import os
import datetime
import inspect
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
import lxml.etree
from trytond.config import CONFIG
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.url import URLMixin
from trytond.rpc import RPC

MIMETYPES = {
    'odt': 'application/vnd.oasis.opendocument.text',
    'odp': 'application/vnd.oasis.opendocument.presentation',
    'ods': 'application/vnd.oasis.opendocument.spreadsheet',
    'odg': 'application/vnd.oasis.opendocument.graphics',
    }
FORMAT2EXT = {
    'doc6': 'doc',
    'doc95': 'doc',
    'docbook': 'xml',
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
            self.cache[self.language] = {}
            translations = self.translation.search([
                ('lang', '=', self.language),
                ('type', '=', 'odt'),
                ('name', '=', self.report_name),
                ('value', '!=', ''),
                ('value', '!=', None),
                ('fuzzy', '=', False),
                ('res_id', '=', None),
                ])
            for translation in translations:
                self.cache[self.language][translation.src] = translation.value
        return self.cache[self.language].get(text, text)

    def set_language(self, language):
        self.language = language


class Report(URLMixin):
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        cls.__rpc__ = {
            'execute': RPC(),
            }

    @classmethod
    def __register__(cls, module_name):
        pass

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
        action_reports = ActionReport.search([
                ('report_name', '=', cls.__name__)
                ])
        if not action_reports:
            raise Exception('Error', 'Report (%s) not find!' % cls.__name__)
        action_report = action_reports[0]
        records = None
        if action_report.model:
            records = cls._get_records(ids, action_report.model, data)
        type, data = cls.parse(action_report, records, data, {})
        return (type, buffer(data), action_report.direct_print,
            action_report.name)

    @classmethod
    def _get_records(cls, ids, model, data):
        pool = Pool()
        Model = pool.get(model)

        class TranslateModel:
            _languages = {}

            def __init__(self, id):
                self.id = id
                self._language = Transaction().language

            def setLang(self, language):
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
    def parse(cls, report, records, data, localcontext):
        '''
        Parse the report and return a tuple with report type and report.
        '''
        pool = Pool()
        User = pool.get('res.user')
        Translation = pool.get('ir.translation')

        localcontext['data'] = data
        localcontext['user'] = User(Transaction().user)
        localcontext['formatLang'] = lambda *args, **kargs: \
            cls.format_lang(*args, **kargs)
        localcontext['StringIO'] = StringIO.StringIO
        localcontext['time'] = time
        localcontext['datetime'] = datetime
        localcontext['context'] = Transaction().context

        translate = TranslateFactory(cls.__name__, Transaction().language,
            Translation)
        localcontext['setLang'] = lambda language: translate.set_language(
            language)

        # Convert to str as buffer from DB is not supported by StringIO
        report_content = (str(report.report_content) if report.report_content
            else False)
        style_content = (str(report.style_content) if report.style_content
            else False)

        if not report_content:
            raise Exception('Error', 'Missing report file!')

        fd, path = tempfile.mkstemp(
            suffix=(os.extsep + report.template_extension),
            prefix='trytond_')
        outzip = zipfile.ZipFile(path, mode='w')

        content_io = StringIO.StringIO()
        content_io.write(report_content)
        content_z = zipfile.ZipFile(content_io, mode='r')

        style_info = None
        style_xml = None
        manifest = None
        for f in content_z.infolist():
            if f.filename == 'styles.xml' and style_content:
                style_info = f
                style_xml = content_z.read(f.filename)
                continue
            elif Manifest and f.filename == MANIFEST:
                manifest = Manifest(content_z.read(f.filename))
                continue
            outzip.writestr(f, content_z.read(f.filename))

        if style_content:
            pictures = []

            # cStringIO difference:
            # calling StringIO() with a string parameter creates a read-only
            # object
            new_style_io = StringIO.StringIO()
            new_style_io.write(style_content)
            new_style_z = zipfile.ZipFile(new_style_io, mode='r')
            new_style_xml = new_style_z.read('styles.xml')
            for file in new_style_z.namelist():
                if file.startswith('Pictures'):
                    picture = new_style_z.read(file)
                    pictures.append((file, picture))
                    if manifest:
                        manifest.add_file_entry(file)
            new_style_z.close()
            new_style_io.close()

            style_tree = lxml.etree.parse(StringIO.StringIO(style_xml))
            style_root = style_tree.getroot()

            new_style_tree = lxml.etree.parse(StringIO.StringIO(new_style_xml))
            new_style_root = new_style_tree.getroot()

            for style in ('master-styles', 'automatic-styles'):
                node, = style_tree.xpath(
                        '/office:document-styles/office:%s' % style,
                        namespaces=style_root.nsmap)
                new_node, = new_style_tree.xpath(
                        '/office:document-styles/office:%s' % style,
                        namespaces=new_style_root.nsmap)
                node.getparent().replace(node, new_node)

            outzip.writestr(style_info,
                    lxml.etree.tostring(style_tree, encoding='utf-8',
                        xml_declaration=True))

            for file, picture in pictures:
                outzip.writestr(file, picture)

        if manifest:
            outzip.writestr(MANIFEST, str(manifest))

        content_z.close()
        content_io.close()
        outzip.close()

        # Since Genshi >= 0.6, Translator requires a function type
        translator = Translator(lambda text: translate(text))

        mimetype = MIMETYPES[report.template_extension]
        rel_report = relatorio.reporting.Report(path, mimetype,
                ReportFactory(), relatorio.reporting.MIMETemplateLoader())
        rel_report.filters.insert(0, translator)
        #convert unicode key into str
        localcontext = dict(map(lambda x: (str(x[0]), x[1]),
            localcontext.iteritems()))
        #Test compatibility with old relatorio version <= 0.3.0
        if len(inspect.getargspec(rel_report.__call__)[0]) == 2:
            data = rel_report(records, **localcontext).render().getvalue()
        else:
            localcontext['objects'] = records  # XXX to remove
            localcontext['records'] = records
            data = rel_report(**localcontext).render()
            if hasattr(data, 'getvalue'):
                data = data.getvalue()
        os.close(fd)
        os.remove(path)
        output_format = report.extension or report.template_extension
        if output_format not in MIMETYPES:
            data = cls.unoconv(data, report.template_extension, output_format)
        oext = FORMAT2EXT.get(output_format, output_format)
        return (oext, data)

    @classmethod
    def unoconv(cls, data, input_format, output_format):
        '''
        Call unoconv to convert the OpenDocument
        '''
        fd, path = tempfile.mkstemp(suffix=(os.extsep + input_format),
            prefix='trytond_')
        oext = FORMAT2EXT.get(output_format, output_format)
        with os.fdopen(fd, 'wb+') as fp:
            fp.write(data)
        cmd = ['unoconv', '--connection=%s' % CONFIG['unoconv'],
            '-f', oext, '--stdout', path]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            stdoutdata, stderrdata = proc.communicate()
            if proc.wait() != 0:
                raise Exception(stderrdata)
            return stdoutdata
        finally:
            os.remove(path)

    @classmethod
    def format_lang(cls, value, lang, digits=2, grouping=True, monetary=False,
            date=False, currency=None, symbol=True):
        pool = Pool()
        Lang = pool.get('ir.lang')
        Config = pool.get('ir.configuration')

        if date:
            if lang:
                locale_format = lang.date
                code = lang.code
            else:
                locale_format = Lang.default_date()
                code = Config.get_language()
            if not isinstance(value, time.struct_time):
                # assume string, parse it
                if len(str(value)) == 10:
                    # length of date like 2001-01-01 is ten
                    # assume format '%Y-%m-%d'
                    string_pattern = '%Y-%m-%d'
                else:
                    # assume format '%Y-%m-%d %H:%M:%S'
                    value = str(value)[:19]
                    locale_format = locale_format + ' %H:%M:%S'
                    string_pattern = '%Y-%m-%d %H:%M:%S'
                date = datetime.datetime(*time.strptime(str(value),
                    string_pattern)[:6])
            else:
                date = datetime.datetime(*(value.timetuple()[:6]))
            return Lang.strftime(date, code, locale_format)
        if currency:
            return Lang.currency(lang, value, currency, grouping=grouping,
                symbol=symbol)
        return Lang.format(lang, '%.' + str(digits) + 'f', value,
            grouping=grouping, monetary=monetary)
