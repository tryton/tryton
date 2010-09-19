#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import copy
import xml
from xml import dom
from xml.dom import minidom
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

import warnings
warnings.simplefilter("ignore")
import relatorio.reporting
warnings.resetwarnings()
try:
    from relatorio.templates.opendocument import Manifest, MANIFEST
except ImportError:
    Manifest = None

import tempfile
from genshi.filters import Translator
import traceback
from trytond.config import CONFIG
from trytond.backend import DatabaseIntegrityError
import inspect
import logging

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

    def __init__(self, cursor, user, report_name, language, translation):
        self.cursor = cursor
        self.user = user
        self.report_name = report_name
        self.language = language
        self.translation = translation
        self.cache = {}

    def __call__(self, text):
        if self.language not in self.cache:
            self.cache[self.language] = {}
            translation_ids = self.translation.search(self.cursor, self.user, [
                ('lang', '=', self.language),
                ('type', '=', 'odt'),
                ('name', '=', self.report_name),
                ('value', '!=', ''),
                ('value', '!=', False),
                ('fuzzy', '=', False),
                ('res_id', '=', 0),
                ])
            for translation in self.translation.browse(self.cursor, self.user,
                    translation_ids):
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

    def init(self, cursor, module_name):
        pass

    def execute(self, cursor, user, ids, datas, context=None):
        '''
        Execute the report.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of record ids on which execute report
        :param datas: a dictionary with datas that will be set in
            local context of the report
        :param context: the context
        :return: a tuple with:
            report type,
            base64 encoded data,
            a boolean to direct print,
            the report name
        '''
        if context is None:
            context = {}
        action_report_obj = self.pool.get('ir.action.report')
        action_report_ids = action_report_obj.search(cursor, user, [
            ('report_name', '=', self._name)
            ], context=context)
        if not action_report_ids:
            raise Exception('Error', 'Report (%s) not find!' % self._name)
        action_report = action_report_obj.browse(cursor, user,
                action_report_ids[0], context=context)
        objects = None
        if action_report.model:
            objects = self._get_objects(cursor, user, ids, action_report.model,
                    datas, context)
        type, data = self.parse(cursor, user, action_report,
                objects, datas, context)
        return (type, base64.encodestring(data), action_report.direct_print,
                action_report.name)

    def _get_objects(self, cursor, user, ids, model, datas, context):
        model_obj = self.pool.get(model)
        return model_obj.browse(cursor, user, ids, context=context)

    def parse(self, cursor, user, report, objects, datas, context):
        localcontext = {}
        localcontext['datas'] = datas
        localcontext['user'] = self.pool.get('res.user').\
                browse(cursor, user, user, context=context)
        localcontext['formatLang'] = lambda *args, **kargs: \
                self.format_lang(*((cursor, user) + args), **kargs)
        localcontext['decodestring'] = decodestring
        localcontext['StringIO'] = StringIO.StringIO
        localcontext['time'] = time
        localcontext['datetime'] = datetime
        localcontext.update(context)

        translate = TranslateFactory(cursor, user, self._name,
                context.get('language', 'en_US'),
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
            dom_style = xml.dom.minidom.parseString(style_xml)
            node_style = dom_style.documentElement

            #cStringIO difference:
            #calling StringIO() with a string parameter creates a read-only object
            style2_io = StringIO.StringIO()
            style2_io.write(base64.decodestring(report.style_content))
            style2_z = zipfile.ZipFile(style2_io, mode='r')
            style2_xml = style2_z.read('styles.xml')
            for file in style2_z.namelist():
                if file.startswith('Pictures'):
                    picture = style2_z.read(file)
                    pictures.append((file, picture))
                    if manifest:
                        manifest.add_file_entry(file)
            style2_z.close()
            style2_io.close()
            dom_style2 = xml.dom.minidom.parseString(style2_xml)
            node_style2 = dom_style2.documentElement
            style_header_node2 = self.find(node_style2, 'master-styles')
            style_header_node = self.find(node_style, 'master-styles')
            style_header_node.parentNode.replaceChild(style_header_node2,
                    style_header_node)
            style_header_node2 = self.find(node_style2, 'automatic-styles')
            style_header_node = self.find(node_style, 'automatic-styles')
            style_header_node.parentNode.replaceChild(style_header_node2,
                    style_header_node)

            outzip.writestr(style_info,
                    '<?xml version="1.0" encoding="UTF-8"?>' + \
                            dom_style.documentElement.toxml('utf-8'))

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

    def find(self, tnode, tag):
        for node in tnode.childNodes:
            if node.nodeType == node.ELEMENT_NODE \
                    and node.localName == tag:
                return node
            res = self.find(node, tag)
            if res is not None:
                return res
        return None

    def format_lang(self, cursor, user, value, lang, digits=2, grouping=True,
            monetary=False, date=False, currency=None, symbol=True):
        lang_obj = self.pool.get('ir.lang')

        if date:
            if lang:
                locale_format = lang.date
                code = lang.code
            else:
                locale_format = lang_obj.default_date(cursor, user)
                code = lang_obj.default_code(cursor, user)
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
