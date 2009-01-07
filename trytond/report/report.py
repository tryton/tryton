#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Report"
from trytond.netsvc import Service
from trytond import pooler
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
import md5
from base64 import decodestring

import warnings
warnings.simplefilter("ignore")
import relatorio.reporting
warnings.resetwarnings()

import tempfile
from genshi.filters import Translator
import traceback
from trytond.config import CONFIG
from trytond.sql_db import IntegrityError
import inspect
import mx.DateTime
import logging

MODULE_LIST = []
MODULE_CLASS_LIST = {}


class ReportService(Service):

    def __init__(self):
        self.object_name_pool = {}
        self.module_obj_list = {}
        Service.__init__(self, 'report_proxy')
        Service.join_group(self, 'web-service')
        Service.export_method(self, self.execute)

    def execute_cr(self, cursor, user, report_name, ids, datas, context=None):
        try:
            report = pooler.get_pool_report(cursor.dbname).get(report_name)
            if not report:
                report = Report.create_instance(self, 'report', pooler.get_pool(cursor.dbname))
                report._name = report_name
                self.add(report._name, report)
            res = report.execute(cursor, user, ids, datas, context)
            return res
        except Exception, exception:
            if CONFIG['verbose'] or (exception.args \
                    and str(exception.args[0]) not in \
                    ('NotLogged', 'ConcurrencyException', 'UserError')):
                tb_s = reduce(lambda x, y: x+y,
                        traceback.format_exception(*sys.exc_info()))
                logging.getLogger("web-service").error(
                    'Exception in call: ' + tb_s)
            if isinstance(exception, IntegrityError):
                pool = pooler.get_pool(cursor.dbname)
                for key in pool._sql_errors.keys():
                    if key in exception[0]:
                        msg = pool._sql_errors[key]
                        cursor2 = pooler.get_db(cursor.dbname).cursor()
                        if context is None:
                            context = {}
                        try:
                            cursor2.execute('SELECT value ' \
                                    'FROM ir_translation ' \
                                    'WHERE lang=%s ' \
                                        'AND type=%s ' \
                                        'AND src=%s',
                                    (context.get('language', 'en_US'), 'error',
                                        msg))
                            if cursor2.rowcount:
                                res = cursor2.fetchone()[0]
                                if res:
                                    msg = res
                        finally:
                            cursor2.close()
                        raise Exception('UserError', 'Constraint Error',
                                msg)
            raise

    def execute(self, dbname, user, report_name, ids, datas, context=None):
        cursor = pooler.get_db(dbname).cursor()
        pool = pooler.get_pool_report(dbname)
        try:
            try:
                res = pool.execute_cr(cursor, user, report_name, ids, datas, context)
                cursor.commit()
            except Exception:
                cursor.rollback()
                raise
        finally:
            cursor.close()
        return res

    def add(self, name, object_name_inst):
        """
        adds a new obj instance to the obj pool.
        if it already existed, the instance is replaced
        """
        if self.object_name_pool.has_key(name):
            del self.object_name_pool[name]
        self.object_name_pool[name] = object_name_inst

        module = str(object_name_inst.__class__)[6:]
        module = module[:len(module)-1]
        module = module.split('.')[0][2:]
        self.module_obj_list.setdefault(module, []).append(object_name_inst)

    def get(self, name):
        return self.object_name_pool.get(name, None)

    def instanciate(self, module, pool_obj):
        res = []
        class_list = MODULE_CLASS_LIST.get(module, [])
        for klass in class_list:
            res.append(klass.create_instance(self, module, pool_obj))
        return res

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

    def __init__(self, cursor, report_name, language, translation):
        self.cursor = cursor
        self.report_name = report_name
        self.language = language
        self.translation = translation

    def __call__(self, text):
        res = self.translation._get_source(self.cursor,
                self.report_name, 'odt', self.language, text)
        if res:
            return res
        return text

    def set_language(self, language):
        self.language = language


class Report(object):
    _name = ""

    def __new__(cls):
        for module in cls.__module__.split('.'):
            if module != 'trytond' and module != 'modules':
                break
        if not hasattr(cls, '_module'):
            cls._module = module
        MODULE_CLASS_LIST.setdefault(cls._module, []).append(cls)
        if module not in MODULE_LIST:
            MODULE_LIST.append(cls._module)
        return None

    def create_instance(cls, pool, module, pool_obj):
        """
        try to apply inheritancy at the instanciation level and
        put objs in the pool var
        """
        if pool.get(cls._name):
            parent_class = pool.get(cls._name).__class__
            cls = type(cls._name, (cls, parent_class), {})

        obj = object.__new__(cls)
        obj.__init__(pool, pool_obj)
        return obj

    create_instance = classmethod(create_instance)

    def __init__(self, pool, pool_obj):
        if self._name:
            pool.add(self._name, self)
        self.pool = pool_obj
        super(Report, self).__init__()

    def execute(self, cursor, user, ids, datas, context=None):
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
        return (type, base64.encodestring(data), action_report.direct_print)

    def _get_objects(self, cursor, user, ids, model, datas, context):
        model_obj = self.pool.get(model)
        return model_obj.browse(cursor, user, ids, context=context)

    def parse(self, cursor, user, report, objects, datas, context):
        localcontext = {}
        localcontext['datas'] = datas
        localcontext['user'] = self.pool.get('res.user').\
                browse(cursor, user, user)
        localcontext['formatLang'] = self.format_lang
        localcontext['decodestring'] = decodestring
        localcontext['StringIO'] = StringIO.StringIO
        localcontext['time'] = time
        localcontext['datetime'] = datetime
        localcontext.update(context)

        translate = TranslateFactory(cursor, self._name,
                context.get('language', 'en_US'),
                self.pool.get('ir.translation'))
        localcontext['setLang'] = lambda language: translate.set_language(language)

        if not report.report_content:
            raise Exception('Error', 'Missing report file!')

        fd, path = tempfile.mkstemp(suffix='.odt', prefix='trytond')
        outzip = zipfile.ZipFile(path, mode='w')

        content_io = StringIO.StringIO()
        content_io.write(report.report_content)
        content_z = zipfile.ZipFile(content_io, mode='r')

        style_info = None
        style_xml = None
        for f in content_z.infolist():
            if f.filename == 'styles.xml' and report.style_content:
                style_info = f
                style_xml = content_z.read(f.filename)
                continue
            outzip.writestr(f, content_z.read(f.filename))

        if report.style_content:
            pictures = []
            dom_style = xml.dom.minidom.parseString(style_xml)
            node_style = dom_style.documentElement

            #cStringIO difference:
            #calling StringIO() with a string parameter creates a read-only object
            style2_io = StringIO.StringIO()
            style2_io.write(report.style_content)
            style2_z = zipfile.ZipFile(style2_io, mode='r')
            style2_xml = style2_z.read('styles.xml')
            for file in style2_z.namelist():
                if file.startswith('Pictures'):
                    picture = style2_z.read(file)
                    pictures.append((file, picture))
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

        content_z.close()
        content_io.close()
        outzip.close()

        translator = Translator(translate)

        rel_report = relatorio.reporting.Report(path, 'application/vnd.oasis.opendocument.text',
                ReportFactory(), relatorio.reporting.MIMETemplateLoader())
        rel_report.filters.insert(0, translator)
        #Test compatibility with old relatorio version <= 0.3.0
        if len(inspect.getargspec(rel_report.__call__)[0]) == 2:
            data = rel_report(objects, **localcontext).render().getvalue()
        else:
            localcontext['objects'] = objects
            data = rel_report(**localcontext).render()
            if hasattr(data, 'getvalue'):
                data = data.getvalue()
        os.remove(path)
        output_format = report.output_format.format
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

    def format_lang(self, value, lang, digits=2, grouping=True, monetary=False,
            date=False, currency=None):
        lang_obj = self.pool.get('ir.lang')

        if date:
            if lang:
                locale_format = lang.date
            else:
                locale_format = lang_obj.default_date(None, None)
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
                date = mx.DateTime.strptime(str(value), string_pattern)
            else:
                date = mx.DateTime.DateTime(*(value.timetuple()[:6]))
            return date.strftime(locale_format)
        if currency:
            return lang_obj.currency(lang, value, currency, grouping=grouping)
        return lang_obj.format(lang, '%.' + str(digits) + 'f', value,
                grouping=grouping, monetary=monetary)
