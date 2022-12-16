#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import contextlib
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import zipfile
import polib
import operator
from xml import dom
from xml.dom import minidom
from difflib import SequenceMatcher
import os
try:
    from hashlib import md5
except ImportError:
    from md5 import md5
from functools import reduce
from trytond.model import ModelView, ModelSQL, fields
from trytond.model.cacheable import Cacheable
from trytond.wizard import Wizard
from trytond import tools
from trytond.tools import file_open, reduce_ids
from trytond.backend import TableHandler, FIELDS
from trytond.pyson import PYSONEncoder
from trytond.transaction import Transaction
from trytond.pool import Pool

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


class TrytonPOFile(polib.POFile):

    def sort(self):
        return super(TrytonPOFile, self).sort(
            key=lambda x: (x.msgctxt, x.msgid))


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
    src_md5 = fields.Char('Source MD5', size=32, required=True)
    value = fields.Text('Translation Value')
    module = fields.Char('Module', readonly=True)
    fuzzy = fields.Boolean('Fuzzy')
    model = fields.Function(fields.Char('Model'), 'get_model',
            searcher='search_model')

    def __init__(self):
        super(Translation, self).__init__()
        self._sql_constraints += [
            ('translation_md5_uniq',
                'UNIQUE (name, res_id, lang, type, src_md5, module)',
                'Translation must be unique'),
        ]
        self._max_len = 10240

    def init(self, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, self, module_name)
        # Migration from 1.8: new field src_md5
        src_md5_exist = table.column_exist('src_md5')
        if not src_md5_exist:
            table.add_raw_column('src_md5',
                FIELDS[self.src_md5._type].sql_type(self.src_md5),
                FIELDS[self.src_md5._type].sql_format, None,
                self.src_md5.size, string=self.src_md5.string)
        table.drop_constraint('translation_uniq')
        table.index_action(['lang', 'type', 'name', 'src'], 'remove')

        super(Translation, self).init(module_name)

        # Migration from 1.8: fill new field src_md5
        if not src_md5_exist:
            offset = 0
            limit = cursor.IN_MAX
            translation_ids = True
            while translation_ids:
                translation_ids = self.search([], offset=offset, limit=limit)
                offset += limit
                for translation in self.browse(translation_ids):
                    src_md5 = self.get_src_md5(translation.src)
                    self.write(translation.id, {
                        'src_md5': src_md5,
                    })
            table = TableHandler(cursor, self, module_name)
            table.not_null_action('src_md5', action='add')

        table = TableHandler(Transaction().cursor, self, module_name)
        table.index_action(['lang', 'type', 'name'], 'add')

    def default_fuzzy(self):
        return False

    def get_model(self, ids, name):
        res = {}
        for translation in self.browse(ids):
            res[translation.id] = translation.name.split(',')[0]
        return res

    def search_model(self, name, clause):
        cursor = Transaction().cursor
        cursor.execute('SELECT id FROM "%s" '
            'WHERE split_part(name, \',\', 1) %s %%s' %
            (self._table, clause[1]), (clause[2],))
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    def get_language(self):
        pool = Pool()
        lang_obj = pool.get('ir.lang')
        lang_ids = lang_obj.search([])
        langs = lang_obj.browse(lang_ids)
        res = [(lang.code, lang.name) for lang in langs]
        return res

    def get_src_md5(self, src):
        return md5((src or '').encode('utf-8')).hexdigest()

    def _get_ids(self, name, ttype, lang, ids):
        pool = Pool()
        model_fields_obj = pool.get('ir.model.field')
        model_obj = pool.get('ir.model')

        translations, to_fetch = {}, []
        name = unicode(name)
        ttype = unicode(ttype)
        lang = unicode(lang)
        if name.split(',')[0] in ('ir.model.field', 'ir.model'):
            field_name = name.split(',')[1]
            with Transaction().set_user(0):
                if name.split(',')[0] == 'ir.model.field':
                    if field_name == 'field_description':
                        ttype = u'field'
                    else:
                        ttype = u'help'
                    records = model_fields_obj.browse(ids)
                else:
                    ttype = u'model'
                    records = model_obj.browse(ids)

            trans_args = []
            for record in records:
                if ttype in ('field', 'help'):
                    name = record.model.model + ',' + record.name
                else:
                    name = record.model + ',' + field_name
                trans_args.append((name, ttype, lang, None))
            self._get_sources(trans_args)

            for record in records:
                if ttype in ('field', 'help'):
                    name = record.model.model + ',' + record.name
                else:
                    name = record.model + ',' + field_name
                translations[record.id] = self._get_source(name, ttype, lang)
            return translations
        for obj_id in ids:
            trans = self.get((lang, ttype, name, obj_id))
            if trans is not None:
                translations[obj_id] = trans
            else:
                to_fetch.append(obj_id)
        if to_fetch:
            cursor = Transaction().cursor
            for i in range(0, len(to_fetch), cursor.IN_MAX):
                sub_to_fetch = to_fetch[i:i + cursor.IN_MAX]
                red_sql, red_ids = reduce_ids('res_id', sub_to_fetch)
                cursor.execute('SELECT res_id, value ' \
                        'FROM ir_translation ' \
                        'WHERE lang = %s ' \
                            'AND type = %s ' \
                            'AND name = %s ' \
                            'AND value != \'\' ' \
                            'AND value IS NOT NULL ' \
                            'AND fuzzy = %s ' \
                            'AND ' + red_sql,
                        [lang, ttype, name, False] + red_ids)
                for res_id, value in cursor.fetchall():
                    self.add((lang, ttype, name, res_id), value)
                    translations[res_id] = value
        for res_id in ids:
            if res_id not in translations:
                self.add((lang, ttype, name, res_id), False)
                translations[res_id] = False
        return translations

    def _set_ids(self, name, ttype, lang, ids, value):
        pool = Pool()
        model_fields_obj = pool.get('ir.model.field')
        model_obj = pool.get('ir.model')

        if lang == 'en_US':
            return 0

        model_name, field_name = name.split(',')
        if model_name in ('ir.model.field', 'ir.model'):
            if model_name == 'ir.model.field':
                if field_name == 'field_description':
                    ttype = 'field'
                else:
                    ttype = 'help'
                records = model_fields_obj.browse(ids)
            else:
                ttype = 'model'
                records = model_obj.browse(ids)
            for record in records:
                if ttype in ('field', 'help'):
                    name = record.model + ',' + record.name
                ids2 = self.search([
                    ('lang', '=', lang),
                    ('type', '=', ttype),
                    ('name', '=', name),
                    ])
                with Transaction().set_user(0):
                    if not ids2:
                        self.create({
                            'name': name,
                            'lang': lang,
                            'type': ttype,
                            'src': record[field_name],
                            'value': value,
                            'fuzzy': False,
                            })
                    else:
                        self.write(ids, {
                            'src': record[field_name],
                            'value': value,
                            'fuzzy': False,
                            })
            return len(ids)
        model_obj = pool.get(model_name)
        for record in model_obj.browse(ids):
            ids2 = self.search([
                ('lang', '=', lang),
                ('type', '=', ttype),
                ('name', '=', name),
                ('res_id', '=', record.id),
                ])
            with Transaction().set_user(0):
                if not ids2:
                    self.create({
                        'name': name,
                        'lang': lang,
                        'type': ttype,
                        'res_id': record.id,
                        'value': value,
                        'src': record[field_name],
                        'fuzzy': False,
                        })
                else:
                    self.write(ids2, {
                        'value': value,
                        'src': record[field_name],
                        'fuzzy': False,
                        })
        return len(ids)

    def _get_source(self, name, ttype, lang, source=None):
        name = unicode(name)
        ttype = unicode(ttype)
        lang = unicode(lang)
        if source is not None:
            source = unicode(source)
        trans = self.get((lang, ttype, name, source))
        if trans is not None:
            return trans

        cursor = Transaction().cursor
        if source:
            cursor.execute('SELECT value '
                    'FROM ir_translation '
                    'WHERE lang = %s '
                        'AND type = %s '
                        'AND name = %s '
                        'AND src = %s '
                        'AND value != \'\' '
                        'AND value IS NOT NULL '
                        'AND fuzzy = %s '
                        'AND res_id = 0',
                    (lang, ttype, str(name), source, False))
        else:
            cursor.execute('SELECT value '
                    'FROM ir_translation '
                    'WHERE lang = %s '
                        'AND type = %s '
                        'AND name = %s '
                        'AND value != \'\' '
                        'AND value IS NOT NULL '
                        'AND fuzzy = %s '
                        'AND res_id = 0',
                    (lang, ttype, str(name), False))
        res = cursor.fetchone()
        if res:
            self.add((lang, ttype, name, source), res[0])
            return res[0]
        else:
            self.add((lang, ttype, name, source), False)
            return False

    def _get_sources(self, args):
        '''
        Take a list of (name, ttype, lang, source).
        Add the translations to the cache.
        Return a dict with the translations.
        '''
        res = {}
        clause = []
        cursor = Transaction().cursor
        if len(args) > cursor.IN_MAX:
            for i in range(0, len(args), cursor.IN_MAX):
                sub_args = args[i:i + cursor.IN_MAX]
                res.update(self._get_sources(sub_args))
            return res
        for name, ttype, lang, source in args:
            name = unicode(name)
            ttype = unicode(ttype)
            lang = unicode(lang)
            if source is not None:
                source = unicode(source)
            trans = self.get((lang, ttype, name, source))
            if trans is not None:
                res[(name, ttype, lang, source)] = trans
            else:
                res[(name, ttype, lang, source)] = False
                self.add((lang, ttype, name, source), False)
                if source:
                    clause += [('(lang = %s ' \
                            'AND type = %s ' \
                            'AND name = %s ' \
                            'AND src = %s ' \
                            'AND value != \'\' ' \
                            'AND value IS NOT NULL ' \
                            'AND fuzzy = %s ' \
                            'AND res_id = 0)',
                            (lang, ttype, str(name), source, False))]
                else:
                    clause += [('(lang = %s ' \
                            'AND type = %s ' \
                            'AND name = %s ' \
                            'AND value != \'\' ' \
                            'AND value IS NOT NULL ' \
                            'AND fuzzy = %s ' \
                            'AND res_id = 0)',
                            (lang, ttype, str(name), False))]
        if clause:
            for i in range(0, len(clause), cursor.IN_MAX):
                sub_clause = clause[i:i + cursor.IN_MAX]
                cursor.execute('SELECT lang, type, name, src, value ' \
                        'FROM ir_translation ' \
                        'WHERE ' + ' OR '.join(x[0] for x in sub_clause),
                        reduce(lambda x, y: x + y, [x[1] for x in sub_clause]))
                for lang, ttype, name, source, value in cursor.fetchall():
                    if (name, ttype, lang, source) not in args:
                        source = None
                    res[(name, ttype, lang, source)] = value
                    self.add((lang, ttype, name, source), value)
        return res

    def delete(self, ids):
        self.clear()
        self.fields_view_get.reset()
        return super(Translation, self).delete(ids)

    def create(self, vals):
        self.clear()
        self.fields_view_get.reset()
        cursor = Transaction().cursor
        if not vals.get('module'):
            if vals.get('type', '') in ('odt', 'view', 'wizard_button',
                    'selection', 'error'):
                cursor.execute('SELECT module FROM ir_translation '
                    'WHERE name = %s '
                        'AND res_id = %s '
                        'AND lang = %s '
                        'AND type = %s '
                        'AND src = %s ',
                    (vals.get('name') or '', vals.get('res_id') or 0, 'en_US',
                        vals.get('type') or '', vals.get('src') or ''))
                fetchone = cursor.fetchone()
                if fetchone:
                    vals = vals.copy()
                    vals['module'] = fetchone[0]
            else:
                cursor.execute('SELECT module, src FROM ir_translation '
                    'WHERE name = %s '
                        'AND res_id = %s '
                        'AND lang = %s '
                        'AND type = %s',
                    (vals.get('name') or '', vals.get('res_id') or 0, 'en_US',
                        vals.get('type') or ''))
                fetchone = cursor.fetchone()
                if fetchone:
                    vals = vals.copy()
                    vals['module'], vals['src'] = fetchone
        vals = vals.copy()
        vals['src_md5'] = self.get_src_md5(vals.get('src'))
        return super(Translation, self).create(vals)

    def write(self, ids, vals):
        self.clear()
        self.fields_view_get.reset()
        if 'src' in vals:
            vals = vals.copy()
            vals['src_md5'] = self.get_src_md5(vals.get('src'))
        return super(Translation, self).write(ids, vals)

    def translation_import(self, lang, module, po_path):
        pool = Pool()
        model_data_obj = pool.get('ir.model.data')
        model_data_ids = model_data_obj.search([
            ('module', '=', module),
            ])
        fs_id2model_data = {}
        for model_data in model_data_obj.browse(model_data_ids):
            fs_id2model_data.setdefault(model_data.model, {})
            fs_id2model_data[model_data.model][model_data.fs_id] = model_data

        translation_ids = []
        pofile = polib.pofile(po_path)

        id2translation = {}
        key2ids = {}
        module_translation_ids = self.search([
            ('lang', '=', lang),
            ('module', '=', module),
            ])
        for translation in self.browse(module_translation_ids):
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

        for entry in pofile:
            ttype, name, res_id = entry.msgctxt.split(':')
            src = entry.msgid
            value = entry.msgstr
            fuzzy = 'fuzzy' in entry.flags
            noupdate = False

            model = name.split(',')[0]
            if model in fs_id2model_data and res_id in fs_id2model_data[model]:
                model_data = fs_id2model_data[model][res_id]
                res_id = model_data.db_id
                noupdate = model_data.noupdate

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

            with contextlib.nested(Transaction().set_user(0),
                    Transaction().set_context(module=module)):
                if not ids:
                    translation_ids.append(self.create({
                        'name': name,
                        'res_id': res_id,
                        'lang': lang,
                        'type': ttype,
                        'src': src,
                        'value': value,
                        'fuzzy': fuzzy,
                        'module': module,
                        }))
                else:
                    ids2 = []
                    for translation_id in ids:
                        translation = id2translation[translation_id]
                        if translation.value != value \
                                or translation.fuzzy != fuzzy:
                            ids2.append(translation.id)
                    if ids2 and not noupdate:
                        self.write(ids2, {
                            'value': value,
                            'fuzzy': fuzzy,
                            })
                    translation_ids += ids

        if translation_ids:
            all_translation_ids = self.search([
                ('module', '=', module),
                ('lang', '=', lang),
                ])
            translation_ids_to_delete = [x for x in all_translation_ids
                    if x not in translation_ids]
            self.delete(translation_ids_to_delete)
        return len(translation_ids)

    def translation_export(self, lang, module):
        pool = Pool()
        model_data_obj = pool.get('ir.model.data')

        model_data_ids = model_data_obj.search([
            ('module', '=', module),
            ])
        db_id2fs_id = {}
        for model_data in model_data_obj.browse(model_data_ids):
            db_id2fs_id.setdefault(model_data.model, {})
            db_id2fs_id[model_data.model][model_data.db_id] = model_data.fs_id

        pofile = TrytonPOFile(wrapwidth=78)
        pofile.metadata = {
            'Content-Type': 'text/plain; charset=utf-8',
            }

        with Transaction().set_context(language='en_US'):
            translation_ids = self.search([
                ('lang', '=', lang),
                ('module', '=', module),
                ], order=[])
        for translation in self.browse(translation_ids):
            flags = [] if not translation['fuzzy'] else ['fuzzy']
            trans_ctxt = '%(type)s:%(name)s' % translation
            res_id = translation['res_id']
            if res_id:
                model, _ = translation.name.split(',')
                if model in db_id2fs_id:
                    res_id = db_id2fs_id[model].get(res_id)
                else:
                    continue
            trans_ctxt += ':%s' % res_id
            entry = polib.POEntry(msgid=(translation.src or ''),
                msgstr=(translation.value or ''), msgctxt=trans_ctxt, flags=flags)
            pofile.append(entry)

        pofile.sort()
        return unicode(pofile).encode('utf-8')

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

    def _set_report_translation(self, data):
        pool = Pool()
        report_obj = pool.get('ir.action.report')
        translation_obj = pool.get('ir.translation')

        with Transaction().set_context(active_test=False):
            report_ids = report_obj.search([])

        if not report_ids:
            return {}

        reports = report_obj.browse(report_ids)
        cursor = Transaction().cursor
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
                with file_open(report.report.replace('/', os.sep),
                        mode='rb') as fp:
                    odt_content = fp.read()
            for content in (report.report_content_custom, odt_content):
                if not content:
                    continue

                content_io = StringIO.StringIO(content)
                try:
                    content_z = zipfile.ZipFile(content_io, mode='r')
                except zipfile.BadZipfile:
                    continue

                content_xml = content_z.read('content.xml')
                document = dom.minidom.parseString(content_xml)
                strings = self._translate_report(document.documentElement)

                style_xml = content_z.read('styles.xml')
                document = dom.minidom.parseString(style_xml)
                strings += self._translate_report(document.documentElement)

            if report.style_content:
                style_io = StringIO.StringIO(report.style_content)
                style_z = zipfile.ZipFile(style_io, mode='r')
                style_xml = style_z.read('styles.xml')

                document = dom.minidom.parseString(style_xml)

                strings += self._translate_report(document.documentElement)

            for string in {}.fromkeys(strings).keys():
                src_md5 = translation_obj.get_src_md5(string)
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
                                    'fuzzy = %s, ' \
                                    'src_md5 = %s ' \
                                'WHERE name = %s ' \
                                    'AND type = %s ' \
                                    'AND src = %s ' \
                                    'AND module = %s',
                                (string, True, src_md5, report.report_name,
                                    'odt', string_trans, report.module))
                        del trans_reports[string_trans]
                        done = True
                        break
                if not done:
                    cursor.execute('INSERT INTO ir_translation ' \
                            '(name, lang, type, src, value, module, fuzzy, '\
                             'src_md5)' \
                            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                            (report.report_name, 'en_US', 'odt', string, '',
                                report.module, False, src_md5))
            if strings:
                cursor.execute('DELETE FROM ir_translation ' \
                        'WHERE name = %s ' \
                            'AND type = %s ' \
                            'AND module = %s ' \
                            'AND src NOT IN ' \
                                '(' + ','.join(('%s',) * len(strings)) + ')',
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

    def _clean_field(self, translation):
        pool = Pool()
        try:
            model_name, field_name = translation.name.split(',', 1)
        except ValueError:
            return True
        if model_name not in pool.object_name_list():
            return True
        model_obj = pool.get(model_name)
        if field_name not in model_obj._columns:
            return True

    def _clean_model(self, translation):
        pool = Pool()
        try:
            model_name, field_name = translation.name.split(',', 1)
        except ValueError:
            return True
        if model_name not in pool.object_name_list():
            return True
        if translation.res_id:
            model_obj = pool.get(model_name)
            if field_name not in model_obj._columns:
                return True
            field = model_obj._columns[field_name]
            if (not hasattr(field, 'translate')
                    or not field.translate):
                return True
        elif field_name not in ('name'):
            return True

    def _clean_odt(self, translation):
        pool = Pool()
        report_obj = pool.get('ir.action.report')
        with Transaction().set_context(active_test=False):
            if not report_obj.search([
                        ('report_name', '=', translation.name),
                        ]):
                return True

    def _clean_selection(self, translation):
        pool = Pool()
        try:
            model_name, field_name = translation.name.split(',', 1)
        except ValueError:
            return True
        if model_name not in pool.object_name_list():
            return True
        model_obj = pool.get(model_name)
        if field_name not in model_obj._columns:
            return True
        field = model_obj._columns[field_name]
        if (not hasattr(field, 'selection')
                or not field.selection
                or not getattr(field, 'translate_selection', True)):
            return True
        if (isinstance(field.selection, (tuple, list))
                and translation.src not in dict(field.selection).values()):
            return True

    def _clean_view(self, translation):
        pool = Pool()
        model_name = translation.name
        if model_name not in pool.object_name_list():
            return True

    def _clean_wizard_button(self, translation):
        pool = Pool()
        try:
            wizard_name, state_name, button_name = \
                    translation.name.split(',', 2)
        except ValueError:
            return True
        if (wizard_name not in
                pool.object_name_list(type='wizard')):
            return True
        wizard = pool.get(wizard_name, type='wizard')
        if not wizard:
            return True
        state = wizard.states.get(state_name)
        if not state:
            return True
        for but in state['result']['state']:
            if but[0] == button_name:
                return False
        return True

    def _clean_help(self, translation):
        pool = Pool()
        try:
            model_name, field_name = translation.name.split(',', 1)
        except ValueError:
            return True
        if model_name not in pool.object_name_list():
            return True
        model_obj = pool.get(model_name)
        if field_name not in model_obj._columns:
            return True
        field = model_obj._columns[field_name]
        return not field.help

    def _clean_error(self, translation):
        pool = Pool()
        model_name = translation.name
        if model_name in (
                'delete_xml_record',
                'xml_record_desc',
                'write_xml_record',
                'not_found_in_selection',
                'relation_not_found',
                'too_many_relations_found',
                'xml_id_syntax_error',
                'reference_syntax_error',
                'delete_workflow_record',
                'domain_validation_record',
                'required_validation_record',
                'size_validation_record',
                'digits_validation_record',
                'access_error',
                'read_error',
                'write_error',
                'required_field',
                'foreign_model_missing',
                'foreign_model_exist',
                'search_function_missing',
                ):
            return False
        if model_name in pool.object_name_list():
            model_obj = pool.get(model_name)
            errors = model_obj._error_messages.values() + \
                    model_obj._sql_error_messages.values()
            for _, _, error in model_obj._sql_constraints:
                errors.append(error)
            if translation.src not in errors:
                return True
        elif model_name in pool.object_name_list(type='wizard'):
            wizard_obj = pool.get(model_name, type='wizard')
            errors = wizard_obj._error_messages.values()
            if translation.src not in errors:
                return True
        else:
            return True

    def _clean_translation(self, data):
        pool = Pool()
        translation_obj = pool.get('ir.translation')
        model_data_obj = pool.get('ir.model.data')

        to_delete = []
        keys = set()
        translation_ids = translation_obj.search([])
        for translation in translation_obj.browse(translation_ids):
            if getattr(self, '_clean_%s' % translation.type)(translation):
                to_delete.append(translation.id)
            elif translation.type in ('field', 'model', 'wizard_button',
                'help'):
                key = (translation.module, translation.lang, translation.type,
                    translation.name, translation.res_id)
                if key in keys:
                    to_delete.append(translation.id)
                else:
                    keys.add(key)
        # skip translation handled in ir.model.data
        mdata_ids = model_data_obj.search([
            ('db_id', 'in', to_delete),
            ('model', '=', 'ir.translation'),
            ])
        for mdata in model_data_obj.browse(mdata_ids):
            if mdata.db_id in to_delete:
                to_delete.remove(mdata.db_id)

        translation_obj.delete(to_delete)
        return {}

TranslationClean()


class TranslationUpdateInit(ModelView):
    "Update translation - language"
    _name = 'ir.translation.update.init'
    _description = __doc__
    lang = fields.Selection('get_language', string='Language',
        required=True)

    def default_lang(self):
        return Transaction().context.get('language', False)

    def get_language(self):
        pool = Pool()
        lang_obj = pool.get('ir.lang')
        lang_ids = lang_obj.search([('translatable', '=', True)])
        langs = lang_obj.browse(lang_ids)
        res = [(lang.code, lang.name) for lang in langs if lang.code != 'en_US']
        return res

TranslationUpdateInit()


class TranslationUpdate(Wizard):
    "Update translation"
    _name = "ir.translation.update"

    def _update_translation(self, data):
        pool = Pool()
        translation_obj = pool.get('ir.translation')
        cursor = Transaction().cursor
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
            with Transaction().set_user(0):
                translation_obj.create({
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
            with Transaction().set_user(0):
                translation_obj.create({
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
                    'SET fuzzy = %s, ' \
                        'src = %s ' \
                    'WHERE name = %s ' \
                        'AND res_id = %s ' \
                        'AND type = %s ' \
                        'AND lang = %s',
                    (True, row['src'], row['name'], row['res_id'], row['type'],
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
                    'SET fuzzy = %s, ' \
                        'value = %s ' \
                    'WHERE src = %s ' \
                        'AND (value = \'\' OR value IS NULL) ' \
                        'AND lang = %s', (True, row['value'], row['src'],
                            data['form']['lang']))

        cursor.execute('UPDATE ir_translation ' \
                'SET fuzzy = %s ' \
                'WHERE (value = \'\' OR value IS NULL) ' \
                    'AND lang = %s', (False, data['form']['lang'],))
        return {}

    def _action_translation_open(self, data):
        pool = Pool()
        model_data_obj = pool.get('ir.model.data')
        act_window_obj = pool.get('ir.action.act_window')

        model_data_ids = model_data_obj.search([
            ('fs_id', '=', 'act_translation_form'),
            ('module', '=', 'ir'),
            ('inherit', '=', False),
            ], limit=1)
        model_data = model_data_obj.browse(model_data_ids[0])
        res = act_window_obj.read(model_data.db_id)
        res['pyson_domain'] = PYSONEncoder().encode([
            ('module', '!=', False),
            ('lang', '=', data['form']['lang']),
        ])
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

    def default_lang(self):
        return Transaction().context.get('language', False)

    def get_language(self):
        pool = Pool()
        lang_obj = pool.get('ir.lang')
        lang_ids = lang_obj.search([
            ('translatable', '=', True),
            ])
        langs = lang_obj.browse(lang_ids)
        res = [(lang.code, lang.name) for lang in langs]
        return res

    def get_module(self):
        pool = Pool()
        module_obj = pool.get('ir.module.module')
        module_ids = module_obj.search([
            ('state', 'in', ['installed', 'to upgrade', 'to remove']),
            ])
        modules = module_obj.browse(module_ids)
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

    def _export_translation(self, data):
        pool = Pool()
        translation_obj = pool.get('ir.translation')
        file_data = translation_obj.translation_export(data['form']['lang'],
                data['form']['module'])
        return {
            'file': buffer(file_data),
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
