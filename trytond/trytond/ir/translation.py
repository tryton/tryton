#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import contextlib
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import zipfile
import polib
import xml.dom.minidom
from difflib import SequenceMatcher
import os
try:
    from hashlib import md5
except ImportError:
    from md5 import md5
from functools import reduce
from lxml import etree

from ..model import ModelView, ModelSQL, fields
from ..wizard import Wizard, StateView, StateTransition, StateAction, \
    Button
from ..tools import file_open, reduce_ids
from ..backend import TableHandler, FIELDS
from ..pyson import PYSONEncoder
from ..transaction import Transaction
from ..pool import Pool
from ..cache import Cache

__all__ = ['Translation',
    'TranslationSetStart', 'TranslationSetSucceed', 'TranslationSet',
    'TranslationCleanStart', 'TranslationCleanSucceed', 'TranslationClean',
    'TranslationUpdateStart', 'TranslationUpdate',
    'TranslationExportStart', 'TranslationExportResult', 'TranslationExport',
    ]

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


class Translation(ModelSQL, ModelView):
    "Translation"
    __name__ = "ir.translation"

    name = fields.Char('Field Name', required=True)
    res_id = fields.Integer('Resource ID', select=True)
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
    _translation_cache = Cache('ir.translation', size_limit=10240,
        context=False)

    @classmethod
    def __setup__(cls):
        super(Translation, cls).__setup__()
        cls._sql_constraints += [
            ('translation_md5_uniq',
                'UNIQUE (name, res_id, lang, type, src_md5, module)',
                'Translation must be unique'),
        ]

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)
        # Migration from 1.8: new field src_md5
        src_md5_exist = table.column_exist('src_md5')
        if not src_md5_exist:
            table.add_raw_column('src_md5',
                FIELDS[cls.src_md5._type].sql_type(cls.src_md5),
                FIELDS[cls.src_md5._type].sql_format, None,
                cls.src_md5.size, string=cls.src_md5.string)
        table.drop_constraint('translation_uniq')
        table.index_action(['lang', 'type', 'name', 'src'], 'remove')

        super(Translation, cls).__register__(module_name)

        # Migration from 1.8: fill new field src_md5
        if not src_md5_exist:
            offset = 0
            limit = cursor.IN_MAX
            translations = True
            while translations:
                translations = cls.search([], offset=offset, limit=limit)
                offset += limit
                for translation in translations:
                    src_md5 = cls.get_src_md5(translation.src)
                    cls.write([translation], {
                        'src_md5': src_md5,
                    })
            table = TableHandler(cursor, cls, module_name)
            table.not_null_action('src_md5', action='add')

        # Migration from 2.2
        cursor.execute("UPDATE " + cls._table + " "
            "SET res_id = %s "
            "WHERE res_id = %s",
            (None, 0))

        table = TableHandler(Transaction().cursor, cls, module_name)
        table.index_action(['lang', 'type', 'name'], 'add')

    @staticmethod
    def default_fuzzy():
        return False

    def get_model(self, name):
        return self.name.split(',')[0]

    @classmethod
    def search_rec_name(cls, name, clause):
        clause = tuple(clause)
        translations = cls.search(['OR',
                ('src',) + clause[1:],
                ('value',) + clause[1:],
                ])
        if translations:
            return [('id', 'in', [t.id for t in translations])]
        return [(cls._rec_name,) + clause[1:]]

    @classmethod
    def search_model(cls, name, clause):
        cursor = Transaction().cursor
        cursor.execute('SELECT id FROM "%s" '
            'WHERE SUBSTR(name, 1, '
            'CASE WHEN POSITION(\',\' IN name) > 0 '
                'THEN POSITION(\',\' IN name) - 1 '
                'ELSE 0 END) %s %%s' %
            (cls._table, clause[1]), (clause[2],))
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    @classmethod
    def get_language(cls):
        pool = Pool()
        Lang = pool.get('ir.lang')
        langs = Lang.search([])
        res = [(lang.code, lang.name) for lang in langs]
        return res

    @classmethod
    def get_src_md5(cls, src):
        return md5((src or '').encode('utf-8')).hexdigest()

    @classmethod
    def get_ids(cls, name, ttype, lang, ids):
        "Return translation for each id"
        pool = Pool()
        ModelFields = pool.get('ir.model.field')
        Model = pool.get('ir.model')

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
                    records = ModelFields.browse(ids)
                else:
                    ttype = u'model'
                    records = Model.browse(ids)

            trans_args = []
            for record in records:
                if ttype in ('field', 'help'):
                    name = record.model.model + ',' + record.name
                else:
                    name = record.model + ',' + field_name
                trans_args.append((name, ttype, lang, None))
            cls.get_sources(trans_args)

            for record in records:
                if ttype in ('field', 'help'):
                    name = record.model.model + ',' + record.name
                else:
                    name = record.model + ',' + field_name
                translations[record.id] = cls.get_source(name, ttype, lang)
            return translations
        # Don't use cache for fuzzy translation
        if not Transaction().context.get(
                'fuzzy_translation', False):
            for obj_id in ids:
                trans = cls._translation_cache.get((lang, ttype, name, obj_id),
                    -1)
                if trans != -1:
                    translations[obj_id] = trans
                else:
                    to_fetch.append(obj_id)
        else:
            to_fetch = ids
        if to_fetch:
            cursor = Transaction().cursor
            fuzzy_sql = 'AND fuzzy = %s '
            fuzzy = [False]
            if Transaction().context.get('fuzzy_translation', False):
                fuzzy_sql = ''
                fuzzy = []
            for i in range(0, len(to_fetch), cursor.IN_MAX):
                sub_to_fetch = to_fetch[i:i + cursor.IN_MAX]
                red_sql, red_ids = reduce_ids('res_id', sub_to_fetch)
                cursor.execute('SELECT res_id, value '
                    'FROM ir_translation '
                    'WHERE lang = %s '
                        'AND type = %s '
                        'AND name = %s '
                        'AND value != \'\' '
                        'AND value IS NOT NULL '
                        + fuzzy_sql +
                        'AND ' + red_sql,
                    [lang, ttype, name] + fuzzy + red_ids)
                for res_id, value in cursor.fetchall():
                    # Don't store fuzzy translation in cache
                    if not Transaction().context.get(
                            'fuzzy_translation', False):
                        cls._translation_cache.set((lang, ttype, name, res_id),
                            value)
                    translations[res_id] = value
        for res_id in ids:
            if res_id not in translations:
                cls._translation_cache.set((lang, ttype, name, res_id), False)
                translations[res_id] = False
        return translations

    @classmethod
    def set_ids(cls, name, ttype, lang, ids, value):
        "Set translation for each id"
        pool = Pool()
        ModelFields = pool.get('ir.model.field')
        Model = pool.get('ir.model')
        Config = pool.get('ir.configuration')

        model_name, field_name = name.split(',')
        if model_name in ('ir.model.field', 'ir.model'):
            if model_name == 'ir.model.field':
                if field_name == 'field_description':
                    ttype = 'field'
                else:
                    ttype = 'help'
                with Transaction().set_context(language='en_US'):
                    records = ModelFields.browse(ids)
            else:
                ttype = 'model'
                with Transaction().set_context(language='en_US'):
                    records = Model.browse(ids)
            for record in records:
                if ttype in ('field', 'help'):
                    name = record.model.model + ',' + record.name
                else:
                    name = record.model + ',' + field_name
                translation2 = cls.search([
                    ('lang', '=', lang),
                    ('type', '=', ttype),
                    ('name', '=', name),
                    ])
                with Transaction().set_user(0):
                    if not translation2:
                        cls.create([{
                                    'name': name,
                                    'lang': lang,
                                    'type': ttype,
                                    'src': getattr(record, field_name),
                                    'value': value,
                                    'fuzzy': False,
                                    }])
                    else:
                        cls.write(translation2, {
                            'src': getattr(record, field_name),
                            'value': value,
                            'fuzzy': False,
                            })
            return len(ids)
        Model = pool.get(model_name)
        with Transaction().set_context(language=Config.get_language()):
            records = Model.browse(ids)
        for record in records:
            translation2 = cls.search([
                ('lang', '=', lang),
                ('type', '=', ttype),
                ('name', '=', name),
                ('res_id', '=', record.id),
                ])
            with Transaction().set_user(0):
                if not translation2:
                    cls.create([{
                                'name': name,
                                'lang': lang,
                                'type': ttype,
                                'res_id': record.id,
                                'value': value,
                                'src': getattr(record, field_name),
                                'fuzzy': False,
                                }])
                else:
                    cls.write(translation2, {
                        'value': value,
                        'src': getattr(record, field_name),
                        'fuzzy': False,
                        })
                    if (lang == Config.get_language()
                            and Transaction().context.get('fuzzy_translation',
                                True)):
                        other_langs = cls.search([
                                ('lang', '!=', lang),
                                ('type', '=', ttype),
                                ('name', '=', name),
                                ('res_id', '=', record.id),
                                ])
                        cls.write(other_langs, {
                                'src': getattr(record, field_name),
                                'fuzzy': True,
                                })
        return len(ids)

    @classmethod
    def delete_ids(cls, model, ttype, ids):
        "Delete translation for each id"
        cursor = Transaction().cursor
        translations = []
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            translations += cls.search([
                    ('type', '=', ttype),
                    ('name', 'like', model + ',%'),
                    ('res_id', 'in', sub_ids),
                    ])
        with Transaction().set_user(0):
            cls.delete(translations)

    @classmethod
    def get_source(cls, name, ttype, lang, source=None):
        "Return translation for source"
        name = unicode(name)
        ttype = unicode(ttype)
        lang = unicode(lang)
        if source is not None:
            source = unicode(source)
        trans = cls._translation_cache.get((lang, ttype, name, source), -1)
        if trans != -1:
            return trans

        cursor = Transaction().cursor
        if source is not None:
            cursor.execute('SELECT value '
                    'FROM ir_translation '
                    'WHERE lang = %s '
                        'AND type = %s '
                        'AND name = %s '
                        'AND src = %s '
                        'AND value != \'\' '
                        'AND value IS NOT NULL '
                        'AND fuzzy = %s '
                        'AND res_id IS NULL',
                    (lang, ttype, name, source, False))
        else:
            cursor.execute('SELECT value '
                    'FROM ir_translation '
                    'WHERE lang = %s '
                        'AND type = %s '
                        'AND name = %s '
                        'AND value != \'\' '
                        'AND value IS NOT NULL '
                        'AND fuzzy = %s '
                        'AND res_id IS NULL',
                    (lang, ttype, name, False))
        res = cursor.fetchone()
        if res:
            cls._translation_cache.set((lang, ttype, name, source), res[0])
            return res[0]
        else:
            cls._translation_cache.set((lang, ttype, name, source), False)
            return None

    @classmethod
    def get_sources(cls, args):
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
                res.update(cls.get_sources(sub_args))
            return res
        for name, ttype, lang, source in args:
            name = unicode(name)
            ttype = unicode(ttype)
            lang = unicode(lang)
            if source is not None:
                source = unicode(source)
            trans = cls._translation_cache.get((lang, ttype, name, source), -1)
            if trans != -1:
                res[(name, ttype, lang, source)] = trans
            else:
                res[(name, ttype, lang, source)] = None
                cls._translation_cache.set((lang, ttype, name, source), None)
                if source is not None:
                    clause += [('(lang = %s '
                            'AND type = %s '
                            'AND name = %s '
                            'AND src = %s '
                            'AND value != \'\' '
                            'AND value IS NOT NULL '
                            'AND fuzzy = %s '
                            'AND res_id IS NULL)',
                            (lang, ttype, name, source, False))]
                else:
                    clause += [('(lang = %s '
                            'AND type = %s '
                            'AND name = %s '
                            'AND value != \'\' '
                            'AND value IS NOT NULL '
                            'AND fuzzy = %s '
                            'AND res_id IS NULL)',
                            (lang, ttype, name, False))]
        if clause:
            for i in range(0, len(clause), cursor.IN_MAX):
                sub_clause = clause[i:i + cursor.IN_MAX]
                cursor.execute('SELECT lang, type, name, src, value '
                    'FROM ir_translation '
                    'WHERE ' + ' OR '.join(x[0] for x in sub_clause),
                    reduce(lambda x, y: x + y, [x[1] for x in sub_clause]))
                for lang, ttype, name, source, value in cursor.fetchall():
                    if (name, ttype, lang, source) not in args:
                        source = None
                    res[(name, ttype, lang, source)] = value
                    cls._translation_cache.set((lang, ttype, name, source),
                        value)
        return res

    @classmethod
    def delete(cls, translations):
        cls._translation_cache.clear()
        ModelView._fields_view_get_cache.clear()
        return super(Translation, cls).delete(translations)

    @classmethod
    def create(cls, vlist):
        cls._translation_cache.clear()
        ModelView._fields_view_get_cache.clear()
        vlist = [x.copy() for x in vlist]

        cursor = Transaction().cursor
        for vals in vlist:
            if not vals.get('module'):
                if Transaction().context.get('module'):
                    vals['module'] = Transaction().context['module']
                elif vals.get('type', '') in ('odt', 'view', 'wizard_button',
                        'selection', 'error'):
                    cursor.execute('SELECT module FROM ir_translation '
                        'WHERE name = %s '
                            'AND res_id = %s '
                            'AND lang = %s '
                            'AND type = %s '
                            'AND src = %s ',
                        (vals.get('name') or '', vals.get('res_id') or 0,
                            'en_US', vals.get('type') or '', vals.get('src')
                            or ''))
                    fetchone = cursor.fetchone()
                    if fetchone:
                        vals['module'] = fetchone[0]
                else:
                    cursor.execute('SELECT module, src FROM ir_translation '
                        'WHERE name = %s '
                            'AND res_id = %s '
                            'AND lang = %s '
                            'AND type = %s',
                        (vals.get('name') or '', vals.get('res_id') or 0,
                            'en_US', vals.get('type') or ''))
                    fetchone = cursor.fetchone()
                    if fetchone:
                        vals['module'], vals['src'] = fetchone
            vals['src_md5'] = cls.get_src_md5(vals.get('src'))
        return super(Translation, cls).create(vlist)

    @classmethod
    def write(cls, translations, vals):
        cls._translation_cache.clear()
        ModelView._fields_view_get_cache.clear()
        if 'src' in vals:
            vals = vals.copy()
            vals['src_md5'] = cls.get_src_md5(vals.get('src'))
        return super(Translation, cls).write(translations, vals)

    @classmethod
    def extra_model_data(cls, model_data):
        "Yield extra model linked to the model data"
        if model_data.model in (
                'ir.action.report',
                'ir.action.act_window',
                'ir.action.wizard',
                'ir.action.url',
                ):
            yield 'ir.action'

    @classmethod
    def translation_import(cls, lang, module, po_path):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        models_data = ModelData.search([
                ('module', '=', module),
                ])
        fs_id2model_data = {}
        for model_data in models_data:
            fs_id2model_data.setdefault(model_data.model, {})
            fs_id2model_data[model_data.model][model_data.fs_id] = model_data
            for extra_model in cls.extra_model_data(model_data):
                fs_id2model_data.setdefault(extra_model, {})
                fs_id2model_data[extra_model][model_data.fs_id] = model_data

        translations = set()
        to_create = []
        pofile = polib.pofile(po_path)

        id2translation = {}
        key2ids = {}
        module_translations = cls.search([
                ('lang', '=', lang),
                ('module', '=', module),
                ],
            order=[
                ('type', 'DESC'),
                ('name', 'DESC'),
                ])
        for translation in module_translations:
            if translation.type in ('odt', 'view', 'wizard_button',
                    'selection', 'error'):
                key = (translation.name, translation.res_id, translation.type,
                    translation.src)
            elif translation.type in ('field', 'model', 'help'):
                key = (translation.name, translation.res_id, translation.type)
            else:
                raise Exception('Unknow translation type: %s'
                    % translation.type)
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

            if res_id:
                try:
                    res_id = int(res_id)
                except ValueError:
                    continue
            if not res_id:
                res_id = None

            if ttype in ('odt', 'view', 'wizard_button', 'selection', 'error'):
                key = (name, res_id, ttype, src)
            elif ttype in('field', 'model', 'help'):
                key = (name, res_id, ttype)
            else:
                raise Exception('Unknow translation type: %s' % ttype)
            ids = key2ids.get(key, [])

            with contextlib.nested(Transaction().set_user(0),
                    Transaction().set_context(module=module)):
                if not ids:
                    to_create.append({
                        'name': name,
                        'res_id': res_id,
                        'lang': lang,
                        'type': ttype,
                        'src': src,
                        'value': value,
                        'fuzzy': fuzzy,
                        'module': module,
                        })
                else:
                    translations2 = []
                    for translation_id in ids:
                        translation = id2translation[translation_id]
                        if translation.value != value \
                                or translation.fuzzy != fuzzy:
                            translations2.append(translation)
                    if translations2 and not noupdate:
                        cls.write(translations2, {
                            'value': value,
                            'fuzzy': fuzzy,
                            })
                    translations |= set(cls.browse(ids))

        if to_create:
            translations |= set(cls.create(to_create))

        if translations:
            all_translations = set(cls.search([
                        ('module', '=', module),
                        ('lang', '=', lang),
                        ]))
            translations_to_delete = all_translations - translations
            cls.delete(list(translations_to_delete))
        return len(translations)

    @classmethod
    def translation_export(cls, lang, module):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Config = pool.get('ir.configuration')

        models_data = ModelData.search([
                ('module', '=', module),
                ])
        db_id2fs_id = {}
        for model_data in models_data:
            db_id2fs_id.setdefault(model_data.model, {})
            db_id2fs_id[model_data.model][model_data.db_id] = model_data.fs_id
            for extra_model in cls.extra_model_data(model_data):
                db_id2fs_id.setdefault(extra_model, {})
                db_id2fs_id[extra_model][model_data.db_id] = model_data.fs_id

        pofile = TrytonPOFile(wrapwidth=78)
        pofile.metadata = {
            'Content-Type': 'text/plain; charset=utf-8',
            }

        with Transaction().set_context(language=Config.get_language()):
            translations = cls.search([
                ('lang', '=', lang),
                ('module', '=', module),
                ], order=[])
        for translation in translations:
            flags = [] if not translation.fuzzy else ['fuzzy']
            trans_ctxt = '%(type)s:%(name)s:' % {
                'type': translation.type,
                'name': translation.name,
                }
            res_id = translation.res_id
            if res_id:
                model, _ = translation.name.split(',')
                if model in db_id2fs_id:
                    res_id = db_id2fs_id[model].get(res_id)
                else:
                    continue
                trans_ctxt += '%s' % res_id
            entry = polib.POEntry(msgid=(translation.src or ''),
                msgstr=(translation.value or ''), msgctxt=trans_ctxt,
                flags=flags)
            pofile.append(entry)

        pofile.sort()
        return unicode(pofile).encode('utf-8')


class TranslationSetStart(ModelView):
    "Set Translation"
    __name__ = 'ir.translation.set.start'


class TranslationSetSucceed(ModelView):
    "Set Translation"
    __name__ = 'ir.translation.set.succeed'


class TranslationSet(Wizard):
    "Set Translation"
    __name__ = "ir.translation.set"

    start = StateView('ir.translation.set.start',
        'ir.translation_set_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Set', 'set_', 'tryton-ok', default=True),
            ])
    set_ = StateTransition()
    succeed = StateView('ir.translation.set.succeed',
        'ir.translation_set_succeed_view_form', [
            Button('Ok', 'end', 'tryton-ok', default=True),
            ])

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

    def set_report(self):
        pool = Pool()
        Report = pool.get('ir.action.report')
        Translation = pool.get('ir.translation')

        with Transaction().set_context(active_test=False):
            reports = Report.search([])

        if not reports:
            return

        cursor = Transaction().cursor
        for report in reports:
            cursor.execute('SELECT id, name, src FROM ir_translation '
                'WHERE lang = %s '
                    'AND type = %s '
                    'AND name = %s '
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
                document = xml.dom.minidom.parseString(content_xml)
                strings = self._translate_report(document.documentElement)

                style_xml = content_z.read('styles.xml')
                document = xml.dom.minidom.parseString(style_xml)
                strings += self._translate_report(document.documentElement)

            if report.style_content:
                style_io = StringIO.StringIO(report.style_content)
                style_z = zipfile.ZipFile(style_io, mode='r')
                style_xml = style_z.read('styles.xml')

                document = xml.dom.minidom.parseString(style_xml)

                strings += self._translate_report(document.documentElement)

            for string in {}.fromkeys(strings).keys():
                src_md5 = Translation.get_src_md5(string)
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
                        cursor.execute('UPDATE ir_translation '
                            'SET src = %s, '
                                'fuzzy = %s, '
                                'src_md5 = %s '
                            'WHERE name = %s '
                                'AND type = %s '
                                'AND src = %s '
                                'AND module = %s',
                            (string, True, src_md5, report.report_name,
                                'odt', string_trans, report.module))
                        del trans_reports[string_trans]
                        done = True
                        break
                if not done:
                    cursor.execute('INSERT INTO ir_translation '
                        '(name, lang, type, src, value, module, fuzzy, '
                            'src_md5)'
                        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                        (report.report_name, 'en_US', 'odt', string, '',
                            report.module, False, src_md5))
            if strings:
                cursor.execute('DELETE FROM ir_translation '
                    'WHERE name = %s '
                        'AND type = %s '
                        'AND module = %s '
                        'AND src NOT IN '
                            '(' + ','.join(('%s',) * len(strings)) + ')',
                    (report.report_name, 'odt', report.module) +
                    tuple(strings))

    def _translate_view(self, element):
        strings = []
        for attr in ('string', 'sum', 'confirm', 'help'):
            if element.get(attr):
                string = element.get(attr)
                if string:
                    strings.append(string)
        for child in element:
            strings.extend(self._translate_view(child))
        return strings

    def set_view(self):
        pool = Pool()
        View = pool.get('ir.ui.view')

        with Transaction().set_context(active_test=False):
            views = View.search([])

        if not views:
            return
        cursor = Transaction().cursor

        for view in views:
            cursor.execute('SELECT id, name, src FROM ir_translation '
                'WHERE lang = %s '
                    'AND type = %s '
                    'AND name = %s '
                    'AND module = %s',
                ('en_US', 'view', view.model, view.module))
            trans_views = {}
            for trans in cursor.dictfetchall():
                trans_views[trans['src']] = trans

            xml = (view.arch or '').strip()
            if not xml:
                continue
            tree = etree.fromstring(xml)
            root_element = tree.getroottree().getroot()
            strings = self._translate_view(root_element)
            with Transaction().set_context(active_test=False):
                views2 = View.search([
                    ('model', '=', view.model),
                    ('id', '!=', view.id),
                    ('module', '=', view.module),
                    ])
            for view2 in views2:
                xml2 = view2.arch.strip()
                if not xml2:
                    continue
                tree2 = etree.fromstring(xml2)
                root2_element = tree2.getroottree().getroot()
                strings += self._translate_view(root2_element)
            if not strings:
                continue
            for string in set(strings):
                done = False
                if string in trans_views:
                    del trans_views[string]
                    continue
                string_md5 = Translation.get_src_md5(string)
                for string_trans in trans_views:
                    if string_trans in strings:
                        continue
                    seqmatch = SequenceMatcher(lambda x: x == ' ',
                            string, string_trans)
                    if seqmatch.ratio() == 1.0:
                        del trans_views[string_trans]
                        done = True
                        break
                    if seqmatch.ratio() > 0.6:
                        cursor.execute('UPDATE ir_translation '
                            'SET src = %s, '
                                'src_md5 = %s, '
                                'fuzzy = %s '
                            'WHERE id = %s ',
                            (string, string_md5, True,
                                trans_views[string_trans]['id']))
                        del trans_views[string_trans]
                        done = True
                        break
                if not done:
                    cursor.execute('INSERT INTO ir_translation '
                        '(name, lang, type, src, src_md5, value, module, '
                            'fuzzy) '
                        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                        (view.model, 'en_US', 'view', string, string_md5, '',
                            view.module, False))
            if strings:
                cursor.execute('DELETE FROM ir_translation '
                    'WHERE name = %s '
                        'AND type = %s '
                        'AND module = %s '
                        'AND src NOT IN '
                        '(' + ','.join(('%s',) * len(strings)) + ')',
                    (view.model, 'view', view.module) + tuple(strings))

    def transition_set_(self):
        self.set_report()
        self.set_view()
        return 'succeed'


class TranslationCleanStart(ModelView):
    'Clean translation'
    __name__ = 'ir.translation.clean.start'


class TranslationCleanSucceed(ModelView):
    'Clean translation'
    __name__ = 'ir.translation.clean.succeed'


class TranslationClean(Wizard):
    "Clean translation"
    __name__ = 'ir.translation.clean'

    start = StateView('ir.translation.clean.start',
        'ir.translation_clean_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Clean', 'clean', 'tryton-ok', default=True),
            ])
    clean = StateTransition()
    succeed = StateView('ir.translation.clean.succeed',
        'ir.translation_clean_succeed_view_form', [
            Button('Ok', 'end', 'tryton-ok', default=True),
            ])

    @staticmethod
    def _clean_field(translation):
        pool = Pool()
        try:
            model_name, field_name = translation.name.split(',', 1)
        except ValueError:
            return True
        if model_name not in pool.object_name_list():
            return True
        Model = pool.get(model_name)
        if field_name not in Model._fields:
            return True

    @staticmethod
    def _clean_model(translation):
        pool = Pool()
        try:
            model_name, field_name = translation.name.split(',', 1)
        except ValueError:
            return True
        if model_name not in pool.object_name_list():
            return True
        if translation.res_id:
            Model = pool.get(model_name)
            if field_name not in Model._fields:
                return True
            field = Model._fields[field_name]
            if (not hasattr(field, 'translate')
                    or not field.translate):
                return True
        elif field_name not in ('name'):
            return True

    @staticmethod
    def _clean_odt(translation):
        pool = Pool()
        Report = pool.get('ir.action.report')
        with Transaction().set_context(active_test=False):
            if not Report.search([
                        ('report_name', '=', translation.name),
                        ]):
                return True

    @staticmethod
    def _clean_selection(translation):
        pool = Pool()
        try:
            model_name, field_name = translation.name.split(',', 1)
        except ValueError:
            return True
        if model_name not in pool.object_name_list():
            return True
        Model = pool.get(model_name)
        if field_name not in Model._fields:
            return True
        field = Model._fields[field_name]
        if (not hasattr(field, 'selection')
                or not field.selection
                or not getattr(field, 'translate_selection', True)):
            return True
        if (isinstance(field.selection, (tuple, list))
                and translation.src not in dict(field.selection).values()):
            return True

    @staticmethod
    def _clean_view(translation):
        pool = Pool()
        model_name = translation.name
        if model_name not in pool.object_name_list():
            return True

    @staticmethod
    def _clean_wizard_button(translation):
        pool = Pool()
        try:
            wizard_name, state_name, button_name = \
                translation.name.split(',', 2)
        except ValueError:
            return True
        if (wizard_name not in
                pool.object_name_list(type='wizard')):
            return True
        Wizard = pool.get(wizard_name, type='wizard')
        if not Wizard:
            return True
        state = Wizard.states.get(state_name)
        if not state or not hasattr(state, 'buttons'):
            return True
        if button_name in [b.state for b in state.buttons]:
            return False
        return True

    @staticmethod
    def _clean_help(translation):
        pool = Pool()
        try:
            model_name, field_name = translation.name.split(',', 1)
        except ValueError:
            return True
        if model_name not in pool.object_name_list():
            return True
        Model = pool.get(model_name)
        if field_name not in Model._fields:
            return True
        field = Model._fields[field_name]
        return not field.help

    @staticmethod
    def _clean_error(translation):
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
                'time_format_validation_record',
                'selection_value_notfound',
                'model_recusion_error',
                ):
            return False
        if model_name in pool.object_name_list():
            Model = pool.get(model_name)
            errors = (Model._error_messages.values()
                + Model._sql_error_messages.values())
            for _, _, error in Model._sql_constraints:
                errors.append(error)
            if translation.src not in errors:
                return True
        elif model_name in pool.object_name_list(type='wizard'):
            Wizard = pool.get(model_name, type='wizard')
            errors = Wizard._error_messages.values()
            if translation.src not in errors:
                return True
        else:
            return True

    def transition_clean(self):
        pool = Pool()
        Translation = pool.get('ir.translation')
        ModelData = pool.get('ir.model.data')

        to_delete = []
        keys = set()
        translations = Translation.search([])
        for translation in translations:
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
        models_data = ModelData.search([
            ('db_id', 'in', to_delete),
            ('model', '=', 'ir.translation'),
            ])
        for mdata in models_data:
            if mdata.db_id in to_delete:
                to_delete.remove(mdata.db_id)

        Translation.delete(Translation.browse(to_delete))
        return 'succeed'


class TranslationUpdateStart(ModelView):
    "Update translation"
    __name__ = 'ir.translation.update.start'

    language = fields.Many2One('ir.lang', 'Language', required=True,
        domain=[('translatable', '=', True)])

    @staticmethod
    def default_language():
        Lang = Pool().get('ir.lang')
        code = Transaction().context.get('language', False)
        try:
            lang, = Lang.search([
                    ('code', '=', code),
                    ('translatable', '=', True),
                    ], limit=1)
            return lang.id
        except ValueError:
            return None


class TranslationUpdate(Wizard):
    "Update translation"
    __name__ = "ir.translation.update"

    start = StateView('ir.translation.update.start',
        'ir.translation_update_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Update', 'update', 'tryton-ok', default=True),
            ])
    update = StateAction('ir.act_translation_form')

    @staticmethod
    def transition_update():
        return 'end'

    def do_update(self, action):
        pool = Pool()
        Translation = pool.get('ir.translation')
        cursor = Transaction().cursor
        lang = self.start.language.code
        cursor.execute('SELECT name, res_id, type, src, module '
            'FROM ir_translation '
            'WHERE lang=\'en_US\' '
                'AND type in (\'odt\', \'view\', \'wizard_button\', '
                ' \'selection\', \'error\') '
            'EXCEPT SELECT name, res_id, type, src, module '
            'FROM ir_translation '
            'WHERE lang=%s '
                'AND type in (\'odt\', \'view\', \'wizard_button\', '
                ' \'selection\', \'error\')',
            (lang,))
        to_create = []
        for row in cursor.dictfetchall():
            to_create.append({
                'name': row['name'],
                'res_id': row['res_id'],
                'lang': lang,
                'type': row['type'],
                'src': row['src'],
                'module': row['module'],
                })
        if to_create:
            with Transaction().set_user(0):
                Translation.create(to_create)
        cursor.execute('SELECT name, res_id, type, module '
            'FROM ir_translation '
            'WHERE lang=\'en_US\' '
                'AND type in (\'field\', \'model\', \'help\') '
            'EXCEPT SELECT name, res_id, type, module '
            'FROM ir_translation '
            'WHERE lang=%s '
                'AND type in (\'field\', \'model\', \'help\')',
            (lang,))
        to_create = []
        for row in cursor.dictfetchall():
            to_create.append({
                'name': row['name'],
                'res_id': row['res_id'],
                'lang': lang,
                'type': row['type'],
                'module': row['module'],
                })
        if to_create:
            with Transaction().set_user(0):
                Translation.create(to_create)
        cursor.execute('SELECT name, res_id, type, src '
            'FROM ir_translation '
            'WHERE lang=\'en_US\' '
                'AND type in (\'field\', \'model\', \'selection\', '
                    '\'help\') '
            'EXCEPT SELECT name, res_id, type, src '
            'FROM ir_translation '
            'WHERE lang=%s '
                'AND type in (\'field\', \'model\', \'selection\', '
                    '\'help\')',
            (lang,))
        for row in cursor.dictfetchall():
            cursor.execute('UPDATE ir_translation '
                'SET fuzzy = %s, '
                    'src = %s '
                'WHERE name = %s '
                    'AND type = %s '
                    'AND lang = %s '
                    + ('AND res_id = %s' if row['res_id']
                    else 'AND res_id is NULL'),
                (True, row['src'], row['name'], row['type'], lang)
                + ((row['res_id'],) if row['res_id'] else ()))

        cursor.execute('SELECT src, MAX(value) AS value FROM ir_translation '
            'WHERE lang = %s '
                'AND src IN ('
                    'SELECT src FROM ir_translation '
                    'WHERE (value = \'\' OR value IS NULL) '
                        'AND lang = %s) '
                'AND value != \'\' AND value IS NOT NULL '
            'GROUP BY src', (lang, lang))

        for row in cursor.dictfetchall():
            cursor.execute('UPDATE ir_translation '
                'SET fuzzy = %s, '
                    'value = %s '
                'WHERE src = %s '
                    'AND (value = \'\' OR value IS NULL) '
                    'AND lang = %s',
                (True, row['value'], row['src'], lang))

        cursor.execute('UPDATE ir_translation '
            'SET fuzzy = %s '
            'WHERE (value = \'\' OR value IS NULL) '
                'AND lang = %s', (False, lang,))

        action['pyson_domain'] = PYSONEncoder().encode([
            ('module', '!=', False),
            ('lang', '=', lang),
        ])
        return action, {}


class TranslationExportStart(ModelView):
    "Export translation"
    __name__ = 'ir.translation.export.start'

    language = fields.Many2One('ir.lang', 'Language', required=True,
        domain=[
            ('translatable', '=', True),
            ('code', '!=', 'en_US'),
            ])
    module = fields.Many2One('ir.module.module', 'Module', required=True,
        domain=[
            ('state', 'in', ['installed', 'to upgrade', 'to remove']),
            ])

    @staticmethod
    def default_language():
        Lang = Pool().get('ir.lang')
        code = Transaction().context.get('language', False)
        try:
            lang, = Lang.search([
                    ('code', '=', code),
                    ('translatable', '=', True),
                    ], limit=1)
            return lang.id
        except ValueError:
            return None


class TranslationExportResult(ModelView):
    "Export translation"
    __name__ = 'ir.translation.export.result'

    file = fields.Binary('File', readonly=True)


class TranslationExport(Wizard):
    "Export translation"
    __name__ = "ir.translation.export"

    start = StateView('ir.translation.export.start',
        'ir.translation_export_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Export', 'export', 'tryton-ok', default=True),
            ])
    export = StateTransition()
    result = StateView('ir.translation.export.result',
        'ir.translation_export_result_view_form', [
            Button('Close', 'end', 'tryton-close'),
            ])

    def transition_export(self):
        pool = Pool()
        Translation = pool.get('ir.translation')
        file_data = Translation.translation_export(
            self.start.language.code, self.start.module.name)
        self.result.file = buffer(file_data)
        return 'result'

    def default_result(self, fields):
        file_ = self.result.file
        self.result.file = False  # No need to store it in session
        return {
            'file': file_,
            }
