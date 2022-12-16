#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
"Translation"
import base64
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import zipfile
from xml import dom
from xml.dom import minidom
from difflib import SequenceMatcher
import csv
from trytond.model import ModelView, ModelSQL, fields
from trytond.model.cacheable import Cacheable
from trytond.wizard import Wizard
from trytond import tools
from trytond.tools import file_open
from trytond.backend import TableHandler
import os

TRANSLATION_TYPE = [
    ('field', 'Field'),
    ('model', 'Model'),
    ('odt', 'ODT'),
    ('selection', 'Selection'),
    ('view', 'View'),
    ('wizard_button', 'Wizard Button'),
    ('help', 'Help'),
    ('error', 'Error'),
]

HEADER = ['type', 'name', 'res_id', 'src', 'value', 'fuzzy']


class TRYTON(csv.excel):
    lineterminator = '\n'

csv.register_dialect("TRYTON", TRYTON)


class Translation(ModelSQL, ModelView, Cacheable):
    "Translation"
    _name = "ir.translation"
    _description = __doc__
    name = fields.Char('Field Name', required=True)
    res_id = fields.Integer('Resource ID', select=1)
    lang = fields.Selection('get_language', string='Language')
    type = fields.Selection(TRANSLATION_TYPE, string='Type',
       required=True)
    src = fields.Text('Source')
    value = fields.Text('Translation Value')
    module = fields.Char('Module', readonly=True)
    fuzzy = fields.Boolean('Fuzzy')
    model = fields.Function('get_model', fnct_search='model_search',
       type='char', string='Model')

    def __init__(self):
        super(Translation, self).__init__()
        self._sql_constraints += [
            ('translation_uniq',
                'UNIQUE (name, res_id, lang, type, src, module)',
                'Translation must be unique'),
        ]
        self._max_len = 10240

    def init(self, cursor, module_name):
        super(Translation, self).init(cursor, module_name)

        table = TableHandler(cursor, self, module_name)
        table.index_action(['lang', 'type', 'name'], 'add')
        table.index_action(['lang', 'type', 'name', 'src'], 'add')

    def default_fuzzy(self, cursor, user, context=None):
        return False

    def get_model(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for translation in self.browse(cursor, user, ids, context=context):
            res[translation.id] = translation.name.split(',')[0]
        return res

    def model_search(self, cursor, user, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            cursor.execute('SELECT id FROM ir_translation ' \
                    'WHERE split_part(name, \',\', 1) ' + args[i][1] + ' %s',
                    (args[i][2],))
            args2.append(('id', 'in', [x[0] for x in cursor.fetchall()]))
            i += 1
        return args2

    def get_language(self, cursor, user, context):
        lang_obj = self.pool.get('ir.lang')
        lang_ids = lang_obj.search(cursor, user, [], context=context)
        langs = lang_obj.browse(cursor, user, lang_ids, context=context)
        res = [(lang.code, lang.name) for lang in langs]
        return res

    def _get_ids(self, cursor, name, ttype, lang, ids):
        model_fields_obj = self.pool.get('ir.model.field')
        model_obj = self.pool.get('ir.model')

        translations, to_fetch = {}, []
        name = unicode(name)
        ttype = unicode(ttype)
        lang = unicode(lang)
        if name.split(',')[0] in ('ir.model.field', 'ir.model'):
            field_name = name.split(',')[1]
            if name.split(',')[0] == 'ir.model.field':
                if field_name == 'field_description':
                    ttype = u'field'
                else:
                    ttype = u'help'
                records = model_fields_obj.browse(cursor, 0, ids)
            else:
                ttype = u'model'
                records = model_obj.browse(cursor, 0, ids)

            trans_args = []
            for record in records:
                if ttype in ('field', 'help'):
                    name = record.model.model + ',' + record.name
                else:
                    name = record.model + ',' + field_name
                trans_args.append((name, ttype, lang, None))
            self._get_sources(cursor, trans_args)

            for record in records:
                if ttype in ('field', 'help'):
                    name = record.model.model + ',' + record.name
                else:
                    name = record.model + ',' + field_name
                translations[record.id] = self._get_source(cursor,
                        name, ttype, lang)
            return translations
        for obj_id in ids:
            trans = self.get(cursor, (lang, ttype, name, obj_id))
            if trans is not None:
                translations[obj_id] = trans
            else:
                to_fetch.append(obj_id)
        if to_fetch:
            for i in range(0, len(to_fetch), cursor.IN_MAX):
                sub_to_fetch = to_fetch[i:i + cursor.IN_MAX]
                cursor.execute('SELECT res_id, value ' \
                        'FROM ir_translation ' \
                        'WHERE lang = %s ' \
                            'AND type = %s ' \
                            'AND name = %s ' \
                            'AND value != \'\' ' \
                            'AND value IS NOT NULL ' \
                            'AND fuzzy = false ' \
                            'AND res_id in (' + \
                                ','.join([str(x) for x in sub_to_fetch]) + ')',
                        (lang, ttype, name))
                for res_id, value in cursor.fetchall():
                    self.add(cursor, (lang, ttype, name, res_id), value)
                    translations[res_id] = value
        for res_id in ids:
            if res_id not in translations:
                self.add(cursor, (lang, ttype, name, res_id), False)
                translations[res_id] = False
        return translations

    def _set_ids(self, cursor, user, name, ttype, lang, ids, value):
        model_fields_obj = self.pool.get('ir.model.field')
        model_obj = self.pool.get('ir.model')

        model_name, field_name = name.split(',')
        if model_name in ('ir.model.field', 'ir.model'):
            if model_name == 'ir.model.field':
                if field_name == 'field_description':
                    ttype = 'field'
                else:
                    ttype = 'help'
                records = model_fields_obj.browse(cursor, user, ids)
            else:
                ttype = 'model'
                records = model_obj.browse(cursor, user, ids)
            for record in records:
                if ttype in ('field', 'help'):
                    name = record.model + ',' + record.name
                ids2 = self.search(cursor, user, [
                    ('lang', '=', lang),
                    ('type', '=', ttype),
                    ('name', '=', name),
                    ])
                if not ids2:
                    self.create(cursor, 0, {
                        'name': name,
                        'lang': lang,
                        'type': ttype,
                        'src': record[field_name],
                        'value': value,
                        'fuzzy': False,
                        })
                else:
                    self.write(cursor, 0, ids, {
                        'src': record[field_name],
                        'value': value,
                        'fuzzy': False,
                        })
            return len(ids)
        model_obj = self.pool.get(model_name)
        for record in model_obj.browse(cursor, user, ids):
            ids2 = self.search(cursor, user, [
                ('lang', '=', lang),
                ('type', '=', ttype),
                ('name', '=', name),
                ('res_id', '=', record.id),
                ])
            if not ids2:
                self.create(cursor, 0, {
                    'name': name,
                    'lang': lang,
                    'type': ttype,
                    'res_id': record.id,
                    'value': value,
                    'src': record[field_name],
                    'fuzzy': False,
                    })
            else:
                self.write(cursor, 0, ids2, {
                    'value': value,
                    'src': record[field_name],
                    'fuzzy': False,
                    })
        return len(ids)

    def _get_source(self, cursor, name, ttype, lang, source=None):
        name = unicode(name)
        ttype = unicode(ttype)
        lang = unicode(lang)
        if source is not None:
            source = unicode(source)
        trans = self.get(cursor, (lang, ttype, name, source))
        if trans is not None:
            return trans

        if source:
            cursor.execute('SELECT value ' \
                    'FROM ir_translation ' \
                    'WHERE lang = %s ' \
                        'AND type = %s ' \
                        'AND name = %s ' \
                        'AND src = %s ' \
                        'AND value != \'\' ' \
                        'AND value IS NOT NULL ' \
                        'AND fuzzy = false ' \
                        'AND res_id = 0',
                    (lang, ttype, str(name), source))
        else:
            cursor.execute('SELECT value ' \
                    'FROM ir_translation ' \
                    'WHERE lang = %s ' \
                        'AND type = %s ' \
                        'AND name = %s ' \
                        'AND value != \'\' ' \
                        'AND value IS NOT NULL ' \
                        'AND fuzzy = false ' \
                        'AND res_id = 0',
                    (lang, ttype, str(name)))
        res = cursor.fetchone()
        if res:
            self.add(cursor, (lang, ttype, name, source), res[0])
            return res[0]
        else:
            self.add(cursor, (lang, ttype, name, source), False)
            return False

    def _get_sources(self, cursor, args):
        '''
        Take a list of (name, ttype, lang, source).
        Add the translations to the cache.
        Return a dict with the translations.
        '''
        res = {}
        clause = []
        if len(args) > cursor.IN_MAX:
            for i in range(0, len(args), cursor.IN_MAX):
                sub_args = args[i:i + cursor.IN_MAX]
                res.update(self._get_sources(cursor, sub_args))
            return res
        for name, ttype, lang, source in args:
            name = unicode(name)
            ttype = unicode(ttype)
            lang = unicode(lang)
            if source is not None:
                source = unicode(source)
            trans = self.get(cursor, (lang, ttype, name, source))
            if trans is not None:
                res[(name, ttype, lang, source)] = trans
            else:
                res[(name, ttype, lang, source)] = False
                self.add(cursor, (lang, ttype, name, source), False)
                if source:
                    clause += [('(lang = %s ' \
                            'AND type = %s ' \
                            'AND name = %s ' \
                            'AND src = %s ' \
                            'AND value != \'\' ' \
                            'AND value IS NOT NULL ' \
                            'AND fuzzy = false ' \
                            'AND res_id = 0)',
                            (lang, ttype, str(name), source))]
                else:
                    clause += [('(lang = %s ' \
                            'AND type = %s ' \
                            'AND name = %s ' \
                            'AND value != \'\' ' \
                            'AND value IS NOT NULL ' \
                            'AND fuzzy = false ' \
                            'AND res_id = 0)',
                            (lang, ttype, str(name)))]
        if clause:
            for i in range(0, len(clause), cursor.IN_MAX):
                sub_clause = clause[i:i + cursor.IN_MAX]
                cursor.execute('SELECT lang, type, name, src, value ' \
                        'FROM ir_translation ' \
                        'WHERE ' + ' OR '.join([x[0] for x in sub_clause]),
                        reduce(lambda x, y: x + y, [x[1] for x in sub_clause]))
                for lang, ttype, name, source, value in cursor.fetchall():
                    if (name, ttype, lang, source) not in args:
                        source = None
                    res[(name, ttype, lang, source)] = value
                    self.add(cursor, (lang, ttype, name, source), value)
        return res

    def delete(self, cursor, user, ids, context=None):
        self.clear(cursor)
        self.fields_view_get(cursor.dbname)
        return super(Translation, self).delete(cursor, user, ids,
                context=context)

    def create(self, cursor, user, vals, context=None):
        self.clear(cursor)
        self.fields_view_get(cursor.dbname)
        if not vals.get('module'):
            if vals.get('type', '') in ('odt', 'view', 'wizard_button',
                    'selection', 'error'):
                cursor.execute('SELECT module FROM ir_translation ' \
                        'WHERE name = %s ' \
                            'AND res_id = %s ' \
                            'AND lang = %s ' \
                            'AND type = %s ' \
                            'AND src = %s ',
                        (vals.get('name', ''), vals.get('res_id', 0), 'en_US',
                            vals.get('type', ''), vals.get('src', '')))
                if cursor.rowcount:
                    vals = vals.copy()
                    vals['module'] = cursor.fetchone()[0]
            else:
                cursor.execute('SELECT module, src FROM ir_translation ' \
                        'WHERE name = %s ' \
                            'AND res_id = %s ' \
                            'AND lang = %s ' \
                            'AND type = %s',
                        (vals.get('name', ''), vals.get('res_id', 0), 'en_US',
                            vals.get('type', '')))
                if cursor.rowcount:
                    vals = vals.copy()
                    vals['module'], vals['src'] = cursor.fetchone()
        return super(Translation, self).create(cursor, user, vals,
                context=context)

    def write(self, cursor, user, ids, vals, context=None):
        self.clear(cursor)
        self.fields_view_get(cursor.dbname)
        return super(Translation, self).write(cursor, user, ids, vals,
                context=context)

    def translation_import(self, cursor, user, lang, module, datas,
            context=None):
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['module'] = module
        model_data_obj = self.pool.get('ir.model.data')
        model_data_ids = model_data_obj.search(cursor, user, [
            ('module', '=', module),
            ], context=context)
        fs_id2db_id = {}
        for model_data in model_data_obj.browse(cursor, user, model_data_ids,
                context=context):
            fs_id2db_id.setdefault(model_data.model, {})
            fs_id2db_id[model_data.model][model_data.fs_id] = model_data.db_id

        translation_ids = []
        reader = csv.reader(datas)
        for row in reader:
            break

        id2translation = {}
        key2ids = {}
        module_translation_ids = self.search(cursor, user, [
            ('lang', '=', lang),
            ('module', '=', module),
            ], context=context)
        for translation in self.browse(cursor, user, module_translation_ids,
                context=context):
            if translation.type in ('odt', 'view', 'wizard_button',
                    'selection', 'error'):
                key = (translation.name, translation.res_id, translation.type,
                        translation.src)
            elif translation.type in ('field', 'model','help'):
                key = (translation.name, translation.res_id, translation.type)
            else:
                raise Exception('Unknow translation type: %s' % translation.type)
            key2ids.setdefault(key, []).append(translation.id)
            id2translation[translation.id] = translation

        for row in reader:
            ttype = row[0].decode('utf-8')
            name = row[1].decode('utf-8')
            res_id = row[2].decode('utf-8')
            src = row[3].decode('utf-8')
            value = row[4].decode('utf-8')
            fuzzy = bool(int(row[5]))

            model = name.split(',')[0]
            if model in fs_id2db_id:
                res_id = fs_id2db_id[model].get(res_id, res_id)

            try:
                res_id = int(res_id)
            except ValueError:
                continue

            if ttype in ('odt', 'view', 'wizard_button', 'selection', 'error'):
                key = (name, res_id, ttype, src)
            elif ttype in('field', 'model','help'):
                key = (name, res_id, ttype)
            else:
                raise Exception('Unknow translation type: %s' % ttype)
            ids = key2ids.get(key, [])

            if not ids:
                translation_ids.append(self.create(cursor, 0, {
                    'name': name,
                    'res_id': res_id,
                    'lang': lang,
                    'type': ttype,
                    'src': src,
                    'value': value,
                    'fuzzy': fuzzy,
                    'module': module,
                    }, context=ctx))
            else:
                ids2 = []
                for translation_id in ids:
                    translation = id2translation[translation_id]
                    if translation.value != value \
                            or translation.fuzzy != fuzzy:
                        ids2.append(translation.id)
                if ids2:
                    self.write(cursor, 0, ids2, {
                        'value': value,
                        'fuzzy': fuzzy,
                        }, context=ctx)
                translation_ids += ids

        if translation_ids:
            all_translation_ids = self.search(cursor, user, [
                ('module', '=', module),
                ('lang', '=', lang),
                ], context=context)
            translation_ids_to_delete = [x for x in all_translation_ids
                    if x not in translation_ids]
            self.delete(cursor, user, translation_ids_to_delete,
                    context=context)
        return len(translation_ids)

    def translation_export(self, cursor, user, lang, module, context=None):
        model_data_obj = self.pool.get('ir.model.data')

        if context is None:
            context = {}

        model_data_ids = model_data_obj.search(cursor, user, [
            ('module', '=', module),
            ], context=context)
        db_id2fs_id = {}
        for model_data in model_data_obj.browse(cursor, user, model_data_ids,
                context=context):
            db_id2fs_id.setdefault(model_data.model, {})
            db_id2fs_id[model_data.model][model_data.db_id] = model_data.fs_id

        buf = StringIO.StringIO()
        writer = csv.writer(buf, 'TRYTON')
        writer.writerow(HEADER)

        ctx = context.copy()
        ctx['language'] = 'en_US'
        translation_ids = self.search(cursor, user, [
            ('lang', '=', lang),
            ('module', '=', module),
            ], order=[
                ('type', 'ASC'),
                ('name', 'ASC'),
                ('src', 'ASC'),
                ('res_id', 'ASC'),
            ], context=ctx)
        for translation in self.browse(cursor, user, translation_ids,
                context=context):
            row = []
            for field in HEADER:
                if field == 'res_id':
                    res_id = translation[field]
                    if res_id:
                        model = translation.name.split(',')[0]
                        if model in db_id2fs_id:
                            res_id = db_id2fs_id[model].get(res_id)
                    try:
                        val = int(res_id)
                        if val != 0:
                            continue
                    except (ValueError, TypeError):
                        pass
                    row.append(res_id)
                elif field == 'fuzzy':
                    row.append(int(translation[field]))
                else:
                    value = translation[field] or ''
                    value = value.encode('utf-8')
                    row.append(value)
            if len(row) == len(HEADER):
                writer.writerow(row)

        file_data = buf.getvalue()
        buf.close()
        return file_data

Translation()


class ReportTranslationSetInit(ModelView):
    "Update Report Translation"
    _name = 'ir.translation.set_report.init'
    _description = __doc__

ReportTranslationSetInit()


class ReportTranslationSetStart(ModelView):
    "Update Report Translation"
    _name = 'ir.translation.set_report.start'
    _description = __doc__

ReportTranslationSetStart()


class ReportTranslationSet(Wizard):
    "Update report translation"
    _name = "ir.translation.set_report"

    states = {
        'init': {
            'actions': [],
            'result': {
                'type': 'form',
                'object': 'ir.translation.set_report.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('start', 'Start Update', 'tryton-ok', True),
                ],
            },
        },
        'start': {
            'actions': ['_set_report_translation'],
            'result': {
                'type': 'form',
                'object': 'ir.translation.set_report.start',
                'state': [
                    ('end', 'Ok', 'tryton-ok', True),
                ],
            },
        },
    }

    def _translate_report(self, node):
        strings = []

        if node.nodeType in (node.CDATA_SECTION_NODE, node.TEXT_NODE):
            if node.parentNode \
                    and node.parentNode.tagName in ('text:placeholder',
                            'text:page-number', 'text:page-count'):
                return strings

            if node.nodeValue:
                txt = node.nodeValue.strip()
                if txt:
                    strings.append(txt)

        for child in [x for x in node.childNodes]:
            strings.extend(self._translate_report(child))
        return strings

    def _set_report_translation(self, cursor, user, data, context):
        report_obj = self.pool.get('ir.action.report')

        ctx = context.copy()
        ctx['active_test'] = False

        report_ids = report_obj.search(cursor, user, [], context=ctx)

        if not report_ids:
            return {}

        reports = report_obj.browse(cursor, user, report_ids, context=context)

        for report in reports:
            cursor.execute('SELECT id, name, src FROM ir_translation ' \
                    'WHERE lang = %s ' \
                        'AND type = %s ' \
                        'AND name = %s ' \
                        'AND module = %s',
                    ('en_US', 'odt', report.report_name, report.module or ''))
            trans_reports = {}
            for trans in cursor.dictfetchall():
                trans_reports[trans['src']] = trans

            strings = []

            odt_content = ''
            if report.report:
                odt_content = file_open(report.report.replace('/', os.sep),
                        mode='rb').read()
            for content in (report.report_content_data, odt_content):
                if not content:
                    continue

                content_io = StringIO.StringIO(content)
                content_z = zipfile.ZipFile(content_io, mode='r')

                content_xml = content_z.read('content.xml')
                document = dom.minidom.parseString(content_xml)
                strings = self._translate_report(document.documentElement)

                style_xml = content_z.read('styles.xml')
                document = dom.minidom.parseString(style_xml)
                strings += self._translate_report(document.documentElement)

            style_content = None
            try:
                style_content = base64.decodestring(report.style_content)
            except:
                pass

            if style_content:
                style_io = StringIO.StringIO(style_content)
                style_z = zipfile.ZipFile(style_io, mode='r')
                style_xml = style_z.read('styles.xml')

                document = dom.minidom.parseString(style_xml)

                strings += self._translate_report(document.documentElement)

            for string in {}.fromkeys(strings).keys():
                done = False
                if string in trans_reports:
                    del trans_reports[string]
                    continue
                for string_trans in trans_reports:
                    if string_trans in strings:
                        continue
                    seqmatch = SequenceMatcher(lambda x: x == ' ',
                            string, string_trans)
                    if seqmatch.ratio() == 1.0:
                        del trans_reports[report.report_name][string_trans]
                        done = True
                        break
                    if seqmatch.ratio() > 0.6:
                        cursor.execute('UPDATE ir_translation ' \
                                'SET src = %s, ' \
                                    'fuzzy = True ' \
                                'WHERE name = %s ' \
                                    'AND type = %s ' \
                                    'AND src = %s ' \
                                    'AND module = %s',
                                (string, report.report_name, 'odt', string_trans,
                                    report.module))
                        del trans_reports[string_trans]
                        done = True
                        break
                if not done:
                    cursor.execute('INSERT INTO ir_translation ' \
                            '(name, lang, type, src, value, module, fuzzy)' \
                            'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                            (report.report_name, 'en_US', 'odt', string, '',
                                report.module, False))
            if strings:
                cursor.execute('DELETE FROM ir_translation ' \
                        'WHERE name = %s ' \
                            'AND type = %s ' \
                            'AND module = %s ' \
                            'AND src NOT IN ' \
                                '(' + ','.join(['%s' for x in strings]) + ')',
                        (report.report_name, 'odt', report.module) + \
                                tuple(strings))
        return {}

ReportTranslationSet()


class TranslationCleanInit(ModelView):
    'Clean translation init'
    _name = 'ir.translation.clean.init'
    _description = __doc__

TranslationCleanInit()


class TranslationCleanStart(ModelView):
    'Clean translation start'
    _name = 'ir.translation.clean.start'
    _description = __doc__

TranslationCleanStart()


class TranslationClean(Wizard):
    "Clean translation"
    _name = 'ir.translation.clean'

    states = {
        'init': {
            'actions': [],
            'result': {
                'type': 'form',
                'object': 'ir.translation.clean.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('start', 'Start', 'tryton-ok', True),
                ],
            },
        },
        'start': {
            'actions': ['_clean_translation'],
            'result': {
                'type': 'form',
                'object': 'ir.translation.clean.start',
                'state': [
                    ('end', 'Ok', 'tryton-ok', True),
                ],
            },
        },
    }

    def _clean_translation(self, cursor, user, data, context):
        translation_obj = self.pool.get('ir.translation')
        model_data_obj = self.pool.get('ir.model.data')
        report_obj = self.pool.get('ir.action.report')

        ctx = context.copy()
        ctx['active_test'] = False

        offset = 0
        limit = cursor.IN_MAX
        while True:
            to_delete = []
            translation_ids = translation_obj.search(cursor, user, [],
                    offset=offset, limit=limit, context=context)
            if not translation_ids:
                break
            offset += limit
            for translation in translation_obj.browse(cursor, user,
                    translation_ids, context=context):
                if translation.type == 'field':
                    try:
                        model_name, field_name = translation.name.split(',', 1)
                    except ValueError:
                        to_delete.append(translation.id)
                        continue
                    if model_name not in self.pool.object_name_list():
                        to_delete.append(translation.id)
                        continue
                    model_obj = self.pool.get(model_name)
                    if field_name not in model_obj._columns:
                        to_delete.append(translation.id)
                        continue
                elif translation.type == 'model':
                    try:
                        model_name, field_name = translation.name.split(',', 1)
                    except ValueError:
                        to_delete.append(translation.id)
                        continue
                    if model_name not in self.pool.object_name_list():
                        to_delete.append(translation.id)
                        continue
                    if translation.res_id:
                        model_obj = self.pool.get(model_name)
                        if field_name not in model_obj._columns:
                            to_delete.append(translation.id)
                            continue
                        field = model_obj._columns[field_name]
                        if not hasattr(field, 'translate') or \
                                not field.translate:
                            to_delete.append(translation.id)
                            continue
                    elif field_name not in ('name'):
                        to_delete.append(translation.id)
                        continue
                elif translation.type == 'odt':
                    if not report_obj.search(cursor, user, [
                        ('report_name', '=', translation.name),
                        ], context=ctx):
                        to_delete.append(translation.id)
                        continue
                elif translation.type == 'selection':
                    try:
                        model_name, field_name = translation.name.split(',', 1)
                    except ValueError:
                        to_delete.append(translation.id)
                        continue
                    if model_name not in self.pool.object_name_list():
                        to_delete.append(translation.id)
                        continue
                    model_obj = self.pool.get(model_name)
                    if field_name not in model_obj._columns:
                        to_delete.append(translation.id)
                        continue
                    field = model_obj._columns[field_name]
                    if not hasattr(field, 'selection') or not field.selection \
                            or not ((hasattr(field, 'translate_selection') and \
                            field.translate_selection) or True):
                        to_delete.append(translation.id)
                        continue
                    if isinstance(field.selection, (tuple, list)) \
                            and translation.src not in \
                            dict(field.selection).values():
                        to_delete.append(translation.id)
                        continue
                elif translation.type == 'view':
                    model_name = translation.name
                    if model_name not in self.pool.object_name_list():
                        to_delete.append(translation.id)
                        continue
                elif translation.type == 'wizard_button':
                    try:
                        wizard_name, state_name, button_name = \
                                translation.name.split(',', 2)
                    except ValueError:
                        to_delete.append(translation.id)
                        continue
                    if wizard_name not in \
                            self.pool.object_name_list(type='wizard'):
                        to_delete.append(translation.id)
                        continue
                    wizard = self.pool.get(wizard_name, type='wizard')
                    if not wizard:
                        to_delete.append(translation.id)
                        continue
                    state = wizard.states.get(state_name)
                    if not state:
                        to_delete.append(translation.id)
                        continue
                    find = False
                    for but in state['result']['state']:
                        if but[0] == button_name:
                            find = True
                    if not find:
                        to_delete.append(translation.id)
                        continue
                elif translation.type == 'help':
                    try:
                        model_name, field_name = translation.name.split(',', 1)
                    except ValueError:
                        to_delete.append(translation.id)
                        continue
                    if model_name not in self.pool.object_name_list():
                        to_delete.append(translation.id)
                        continue
                    model_obj = self.pool.get(model_name)
                    if field_name not in model_obj._columns:
                        to_delete.append(translation.id)
                        continue
                    field = model_obj._columns[field_name]
                    if not field.help:
                        to_delete.append(translation.id)
                        continue
                elif translation.type == 'error':
                    model_name = translation.name
                    if model_name in (
                            'delete_xml_record',
                            'xml_record_desc',
                            'write_xml_record',
                            'delete_workflow_record',
                            'domain_validation_record',
                            'required_validation_record',
                            'access_error',
                            'read_error',
                            'write_error',
                            'required_field',
                            'foreign_model_missing',
                            'foreign_model_exist',
                            ):
                        continue
                    if model_name in self.pool.object_name_list():
                        model_obj = self.pool.get(model_name)
                        errors = model_obj._error_messages.values() + \
                                model_obj._sql_error_messages.values()
                        for _, _, error in model_obj._sql_constraints:
                            errors.append(error)
                        if translation.src not in errors:
                            to_delete.append(translation.id)
                            continue
                    elif model_name in self.pool.object_name_list(type='wizard'):
                        wizard_obj = self.pool.get(model_name, type='wizard')
                        errors = wizard_obj._error_messages.values()
                        if translation.src not in errors:
                            to_delete.append(translation.id)
                            continue
                    else:
                        to_delete.append(translation.id)
                        continue
            # skip translation handled in ir.model.data
            mdata_ids = model_data_obj.search(
                cursor, user,
                [('db_id', 'in', to_delete), ('model', '=', 'ir.translation')],
                context=context)
            for mdata in model_data_obj.browse(cursor, user, mdata_ids,
                                               context=context):
                if mdata.db_id in to_delete:
                    to_delete.remove(mdata.db_id)

            translation_obj.delete(cursor, user, to_delete, context=context)
        return {}

TranslationClean()


class TranslationUpdateInit(ModelView):
    "Update translation - language"
    _name = 'ir.translation.update.init'
    _description = __doc__
    lang = fields.Selection('get_language', string='Language',
        required=True)

    def get_language(self, cursor, user, context):
        lang_obj = self.pool.get('ir.lang')
        lang_ids = lang_obj.search(cursor, user, [('translatable', '=', True)],
                context=context)
        langs = lang_obj.browse(cursor, user, lang_ids, context=context)
        res = [(lang.code, lang.name) for lang in langs if lang.code != 'en_US']
        return res

TranslationUpdateInit()


class TranslationUpdate(Wizard):
    "Update translation"
    _name = "ir.translation.update"

    def _update_translation(self, cursor, user, data, context):
        translation_obj = self.pool.get('ir.translation')
        cursor.execute('SELECT name, res_id, type, src, module ' \
                'FROM ir_translation ' \
                'WHERE lang=\'en_US\' ' \
                    'AND type in (\'odt\', \'view\', \'wizard_button\', ' \
                    ' \'selection\', \'error\') ' \
                'EXCEPT SELECT name, res_id, type, src, module ' \
                'FROM ir_translation ' \
                'WHERE lang=%s ' \
                    'AND type in (\'odt\', \'view\', \'wizard_button\', ' \
                    ' \'selection\', \'error\')',
                (data['form']['lang'],))
        for row in cursor.dictfetchall():
            translation_obj.create(cursor, 0, {
                'name': row['name'],
                'res_id': row['res_id'],
                'lang': data['form']['lang'],
                'type': row['type'],
                'src': row['src'],
                'module': row['module'],
                })
        cursor.execute('SELECT name, res_id, type, module ' \
                'FROM ir_translation ' \
                'WHERE lang=\'en_US\' ' \
                    'AND type in (\'field\', \'model\', \'help\') ' \
                'EXCEPT SELECT name, res_id, type, module ' \
                'FROM ir_translation ' \
                'WHERE lang=%s ' \
                    'AND type in (\'field\', \'model\', \'help\')',
                (data['form']['lang'],))
        for row in cursor.dictfetchall():
            translation_obj.create(cursor, 0, {
                'name': row['name'],
                'res_id': row['res_id'],
                'lang': data['form']['lang'],
                'type': row['type'],
                'module': row['module'],
                })
        cursor.execute('SELECT name, res_id, type, src ' \
                'FROM ir_translation ' \
                'WHERE lang=\'en_US\' ' \
                    'AND type in (\'field\', \'model\', \'selection\', ' \
                        '\'help\') ' \
                'EXCEPT SELECT name, res_id, type, src ' \
                'FROM ir_translation ' \
                'WHERE lang=%s ' \
                    'AND type in (\'field\', \'model\', \'selection\', ' \
                        '\'help\')',
                (data['form']['lang'],))
        for row in cursor.dictfetchall():
            cursor.execute('UPDATE ir_translation ' \
                    'SET fuzzy = True, ' \
                        'src = %s ' \
                    'WHERE name = %s ' \
                        'AND res_id = %s ' \
                        'AND type = %s ' \
                        'AND lang = %s',
                    (row['src'], row['name'], row['res_id'], row['type'],
                        data['form']['lang']))

        cursor.execute('SELECT src, MAX(value) AS value FROM ir_translation ' \
                'WHERE lang = %s ' \
                    'AND src IN (' \
                        'SELECT src FROM ir_translation ' \
                        'WHERE (value = \'\' OR value IS NULL) ' \
                            'AND lang = %s) ' \
                    'AND value != \'\' AND value IS NOT NULL ' \
                'GROUP BY src', (data['form']['lang'], data['form']['lang']))

        for row in cursor.dictfetchall():
            cursor.execute('UPDATE ir_translation ' \
                    'SET fuzzy = True, ' \
                        'value = %s ' \
                    'WHERE src = %s ' \
                        'AND (value = \'\' OR value IS NULL) ' \
                        'AND lang = %s', (row['value'], row['src'],
                            data['form']['lang']))

        cursor.execute('UPDATE ir_translation ' \
                'SET fuzzy = False ' \
                'WHERE (value = \'\' OR value IS NULL) ' \
                    'AND lang = %s', (data['form']['lang'],))
        return {}

    def _action_translation_open(self, cursor, user, data, context):
        model_data_obj = self.pool.get('ir.model.data')
        act_window_obj = self.pool.get('ir.action.act_window')

        model_data_ids = model_data_obj.search(cursor, user, [
            ('fs_id', '=', 'act_translation_form'),
            ('module', '=', 'ir'),
            ('inherit', '=', False),
            ], limit=1, context=context)
        model_data = model_data_obj.browse(cursor, user, model_data_ids[0],
                context=context)
        res = act_window_obj.read(cursor, user, model_data.db_id, context=context)
        res['domain'] = res['domain'][:-1] + ',' + \
                str(('lang', '=', data['form']['lang'])) + res['domain'][-1:]
        return res

    states = {
        'init': {
            'actions': [],
            'result': {
                'type': 'form',
                'object': 'ir.translation.update.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('start', 'Start Update','tryton-ok', True),
                ],
            },
        },
        'start': {
            'actions': ['_update_translation'],
            'result': {
                'type': 'action',
                'action': '_action_translation_open',
                'state': 'end',
            },
        },
    }

TranslationUpdate()


class TranslationExportInit(ModelView):
    "Export translation - language and module"
    _name = 'ir.translation.export.init'
    _description = __doc__
    lang = fields.Selection('get_language', string='Language',
       required=True)
    module = fields.Selection('get_module', string='Module',
       required=True)

    def get_language(self, cursor, user, context):
        lang_obj = self.pool.get('ir.lang')
        lang_ids = lang_obj.search(cursor, user, [
            ('translatable', '=', True),
            ], context=context)
        langs = lang_obj.browse(cursor, user, lang_ids, context=context)
        res = [(lang.code, lang.name) for lang in langs]
        return res

    def get_module(self, cursor, user, context):
        module_obj = self.pool.get('ir.module.module')
        module_ids = module_obj.search(cursor, user, [
            ('state', 'in', ['installed', 'to upgrade', 'to remove']),
            ], context=context)
        modules = module_obj.browse(cursor, user, module_ids, context=context)
        res =  [(module.name, module.name) for module in modules]
        return res

TranslationExportInit()


class TranslationExportStart(ModelView):
    "Export translation - file"
    _description = __doc__
    _name = 'ir.translation.export.start'
    file = fields.Binary('File', readonly=True)

TranslationExportStart()


class TranslationExport(Wizard):
    "Export translation"
    _name = "ir.translation.export"

    def _export_translation(self, cursor, user, data, context):
        translation_obj = self.pool.get('ir.translation')
        file_data = translation_obj.translation_export(cursor, user,
                data['form']['lang'], data['form']['module'], context=context)
        return {
            'file': base64.encodestring(file_data),
        }

    states = {
        'init': {
            'actions': [],
            'result': {
                'type': 'form',
                'object': 'ir.translation.export.init',
                'state': [
                    ('end', 'Cancel', 'tryton-cancel'),
                    ('start', 'Start Export', 'tryton-ok', True),
                ],
            },
        },
        'start': {
            'actions': ['_export_translation'],
            'result': {
                'type': 'form',
                'object': 'ir.translation.export.start',
                'state': [
                    ('end', 'Close', 'tryton-close'),
                ],
            },
        },
    }

TranslationExport()
