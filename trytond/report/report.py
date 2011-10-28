#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy
import xml
import sys
import base64
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import zipfile
import time
import os
import datetime
from base64 import decodestring
import traceback
import inspect
import logging
import tempfile
import warnings
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
from trytond.backend import DatabaseIntegrityError
from trytond.pool import Pool
from trytond.transaction import Transaction

PARENTS = {
    'table-row': 1,
    'list-item': 1,
    'body': 0,
    'section': 0,
}


class ReportFactory:

    def __call__(self, objects, **kwargs):
        data = {}
        data['objects'] = objects
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
            translation_ids = self.translation.search([
                ('lang', '=', self.language),
                ('type', '=', 'odt'),
                ('name', '=', self.report_name),
                ('value', '!=', ''),
                ('value', '!=', False),
                ('fuzzy', '=', False),
                ('res_id', '=', 0),
                ])
            for translation in self.translation.browse(translation_ids):
                self.cache[self.language][translation.src] = translation.value
        return self.cache[self.language].get(text, text)

    def set_language(self, language):
        self.language = language


class Report(object):
    _name = ""

    def __new__(cls):
        Pool.register(cls, type='report')

    def __init__(self):
        self._rpc = {
            'execute': False,
        }

    def init(self, module_name):
        pass

    def execute(self, ids, datas):
        '''
        Execute the report.

        :param ids: a list of record ids on which execute report
        :param datas: a dictionary with datas that will be set in
            local context of the report
        :return: a tuple with:
            report type,
            base64 encoded data,
            a boolean to direct print,
            the report name
        '''
        action_report_obj = self.pool.get('ir.action.report')
        action_report_ids = action_report_obj.search([
            ('report_name', '=', self._name)
            ])
        if not action_report_ids:
            raise Exception('Error', 'Report (%s) not find!' % self._name)
        action_report = action_report_obj.browse(action_report_ids[0])
        objects = None
        if action_report.model:
            objects = self._get_objects(ids, action_report.model, datas)
        type, data = self.parse(action_report, objects, datas, {})
        return (type, base64.encodestring(data), action_report.direct_print,
                action_report.name)

    def _get_objects(self, ids, model, datas):
        model_obj = self.pool.get(model)
        return model_obj.browse(ids)

    def parse(self, report, objects, datas, localcontext):
        '''
        Parse the report.

        :param report: a BrowseRecord of the ir.action.report
        :param objects: a BrowseRecordList of the records on which parse report
        :param datas: a dictionary with datas that will be set in local context
            of the report
        :param localcontext: the context used to parse the report
        :return: a tuple with:
            report type
            report
        '''
        localcontext['datas'] = datas
        localcontext['user'] = self.pool.get('res.user'
                ).browse(Transaction().user)
        localcontext['formatLang'] = lambda *args, **kargs: \
                self.format_lang(*args, **kargs)
        localcontext['decodestring'] = decodestring
        localcontext['StringIO'] = StringIO.StringIO
        localcontext['time'] = time
        localcontext['datetime'] = datetime
        localcontext['context'] = Transaction().context

        translate = TranslateFactory(self._name, Transaction().language,
                self.pool.get('ir.translation'))
        localcontext['setLang'] = lambda language: translate.set_language(language)

        if not report.report_content:
            raise Exception('Error', 'Missing report file!')

        fd, path = tempfile.mkstemp(suffix='.odt', prefix='trytond')
        outzip = zipfile.ZipFile(path, mode='w')

        content_io = StringIO.StringIO()
        content_io.write(base64.decodestring(report.report_content))
        content_z = zipfile.ZipFile(content_io, mode='r')

        style_info = None
        style_xml = None
        manifest = None
        for f in content_z.infolist():
            if f.filename == 'styles.xml' and report.style_content:
                style_info = f
                style_xml = content_z.read(f.filename)
                continue
            elif Manifest and f.filename == MANIFEST:
                manifest = Manifest(content_z.read(f.filename))
                continue
            outzip.writestr(f, content_z.read(f.filename))

        if report.style_content:
            pictures = []

            #cStringIO difference:
            #calling StringIO() with a string parameter creates a read-only object
            new_style_io = StringIO.StringIO()
            new_style_io.write(base64.decodestring(report.style_content))
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

        rel_report = relatorio.reporting.Report(path, 'application/vnd.oasis.opendocument.text',
                ReportFactory(), relatorio.reporting.MIMETemplateLoader())
        rel_report.filters.insert(0, translator)
        #convert unicode key into str
        localcontext = dict(map(lambda x: (str(x[0]), x[1]),
            localcontext.iteritems()))
        #Test compatibility with old relatorio version <= 0.3.0
        if len(inspect.getargspec(rel_report.__call__)[0]) == 2:
            data = rel_report(objects, **localcontext).render().getvalue()
        else:
            localcontext['objects'] = objects
            data = rel_report(**localcontext).render()
            if hasattr(data, 'getvalue'):
                data = data.getvalue()
        os.close(fd)
        os.remove(path)
        output_format = report.extension
        if output_format == 'pdf':
            data = self.convert_pdf(data)
        return (output_format, data)

    def convert_pdf(self, data):
        """
        Convert report to PDF using OpenOffice.org.
        This requires OpenOffice.org, pyuno and openoffice-python to
        be installed.
        """
        import tempfile
        try:
            import unohelper # installs import-hook
            import openoffice.interact
            import openoffice.officehelper as officehelper
            from openoffice.streams import OutputStream
            from com.sun.star.beans import PropertyValue
        except ImportError, exception:
            raise Exception('ImportError', str(exception))
        try:
            # connect to OOo
            desktop = openoffice.interact.Desktop()
        except officehelper.BootstrapException:
            raise Exception('Error', "Can't connect to (bootstrap) OpenOffice.org")

        res_data = None
        # Create temporary file (with name) and write data there.
        # We can not use NamedTemporaryFile here, since this would be
        # deleted as soon as we close it to allow OOo reading.
        #TODO use an input stream here
        fd_odt, odt_name = tempfile.mkstemp()
        fh_odt = os.fdopen(fd_odt, 'wb+')
        try:
            fh_odt.write(data)
            del data # save memory
            fh_odt.close()
            doc = desktop.openFile(odt_name, hidden=False)
            # Export as PDF
            buffer = StringIO.StringIO()
            out_props = (
                PropertyValue("FilterName", 0, "writer_pdf_Export", 0),
                PropertyValue("Overwrite", 0, True, 0),
                PropertyValue("OutputStream", 0, OutputStream(buffer), 0),
                )
            doc.storeToURL("private:stream", out_props)
            res_data = buffer.getvalue()
            del buffer
            doc.dispose()
        finally:
            fh_odt.close()
            os.remove(odt_name)
        if not res_data:
            Exception('Error', 'Error converting to PDF')
        return res_data

    def format_lang(self, value, lang, digits=2, grouping=True, monetary=False,
            date=False, currency=None, symbol=True):
        lang_obj = self.pool.get('ir.lang')

        if date:
            if lang:
                locale_format = lang.date
                code = lang.code
            else:
                locale_format = lang_obj.default_date()
                code = lang_obj.default_code()
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
            return lang_obj.strftime(date, code, locale_format)
        if currency:
            return lang_obj.currency(lang, value, currency, grouping=grouping,
                    symbol=symbol)
        return lang_obj.format(lang, '%.' + str(digits) + 'f', value,
                grouping=grouping, monetary=monetary)
