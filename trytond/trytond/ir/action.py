# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
from collections import defaultdict
from functools import partial
from operator import itemgetter

from genshi.template.text import TextTemplate

from trytond.cache import Cache, MemoryCache
from trytond.i18n import gettext
from trytond.model import (
    DeactivableMixin, Index, ModelSingleton, ModelSQL, ModelStorage, ModelView,
    fields, sequence_ordered)
from trytond.model.exceptions import ValidationError
from trytond.pool import Pool
from trytond.pyson import PYSON, Eval, PYSONDecoder, PYSONEncoder
from trytond.rpc import RPC
from trytond.tools import file_open
from trytond.transaction import (
    Transaction, inactive_records, without_check_access)


class WizardModelError(ValidationError):
    pass


class EmailError(ValidationError):
    pass


class ViewError(ValidationError):
    pass


class DomainError(ValidationError):
    pass


class ContextError(ValidationError):
    pass


ACTION_SELECTION = [
    ('ir.action.report', "Report"),
    ('ir.action.act_window', "Window"),
    ('ir.action.wizard', "Wizard"),
    ('ir.action.url', "URL"),
    ]


class Action(DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'ir.action'
    name = fields.Char('Name', required=True, translate=True)
    type = fields.Selection(
        ACTION_SELECTION, "Type", required=True, readonly=True)
    action = fields.Function(
        fields.Reference("Action", selection=ACTION_SELECTION),
        'get_action')
    records = fields.Selection([
            ('selected', "Selected"),
            ('listed', "Listed"),
            ], "Records",
        help="The records on which the action runs.")
    usage = fields.Char('Usage')
    keywords = fields.One2Many('ir.action.keyword', 'action',
            'Keywords')
    icon = fields.Many2One('ir.ui.icon', 'Icon')
    groups = fields.Many2Many(
        'ir.action-res.group', 'action', 'group', "Groups")
    _groups_cache = Cache('ir.action.get_groups', context=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update({
                'get_action_value': RPC(instantiate=0, cache=dict(days=1)),
                })

    def get_action(self, name):
        return f'{self.type},{self.id}'

    @classmethod
    def default_records(cls):
        return 'selected'

    @staticmethod
    def default_usage():
        return None

    @classmethod
    def on_modification(cls, mode, actions, field_names=None):
        pool = Pool()
        ActionKeyword = pool.get('ir.action.keyword')
        super().on_modification(mode, actions, field_names=field_names)
        ActionKeyword._get_keyword_cache.clear()

    @classmethod
    @inactive_records
    @without_check_access
    def get_action_id(cls, action_id):
        pool = Pool()
        if cls.search([
                    ('id', '=', action_id),
                    ]):
            return action_id
        for action_type in (
                'ir.action.report',
                'ir.action.act_window',
                'ir.action.wizard',
                'ir.action.url',
                ):
            Action = pool.get(action_type)
            actions = Action.search([
                ('id', '=', action_id),
                ])
            if actions:
                action, = actions
                return action.action.id

    @classmethod
    def get_action_values(cls, type_, action_ids, columns=None):
        pool = Pool()
        Action = pool.get(type_)
        if columns is None:
            columns = []
        columns += ['id', 'name', 'type', 'records', 'icon.rec_name']
        if type_ == 'ir.action.report':
            columns += ['report_name', 'direct_print']
        elif type_ == 'ir.action.act_window':
            columns += [
                'views', 'domains', 'res_model', 'limit',
                'context_model', 'context_domain',
                'pyson_domain', 'pyson_context', 'pyson_order',
                'pyson_search_value']
        elif type_ == 'ir.action.wizard':
            columns += ['wiz_name', 'window']
        elif type_ == 'ir.action.url':
            columns += ['url']
        actions = Action.read(action_ids, columns)
        if type_ == 'ir.action.act_window':
            for values in actions:
                if (values['res_model']
                        and issubclass(
                            pool.get(values['res_model']), ModelSingleton)):
                    values['res_id'] = 1
        return actions

    def get_action_value(self):
        action_id = self.get_action_id(self.id)
        if action_id is not None:
            return self.get_action_values(self.type, [action_id])[0]


class ActionGroup(ModelSQL):
    __name__ = 'ir.action-res.group'
    action = fields.Many2One(
        'ir.action', "Action", ondelete='CASCADE', required=True)
    group = fields.Many2One(
        'res.group', "Group", ondelete='CASCADE', required=True)

    @classmethod
    def preprocess_values(cls, mode, values):
        pool = Pool()
        Action = pool.get('ir.action')
        values = super().preprocess_values(mode, values)
        if values.get('action') is not None:
            values['action'] = Action.get_action_id(values['action'])
        return values

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        pool = Pool()
        Action = pool.get('ir.action')
        super().on_modification(mode, records, field_names=field_names)
        Action._groups_cache.clear()


class ActionKeyword(ModelSQL, ModelView):
    __name__ = 'ir.action.keyword'
    keyword = fields.Selection([
            ('tree_open', 'Open tree'),
            ('form_print', 'Print form'),
            ('form_action', 'Action form'),
            ('form_relate', 'Form relate'),
            ('graph_open', 'Open Graph'),
            ], string='Keyword', required=True)
    model = fields.Reference('Model', selection='models_get')
    action = fields.Many2One('ir.action', 'Action',
        ondelete='CASCADE')
    groups = fields.Function(
        fields.One2Many('res.group', None, "Groups"),
        'get_groups', searcher='search_groups')

    _get_keyword_cache = Cache(
        'ir_action_keyword.get_keyword', context=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('action')
        table = cls.__table__()

        cls.__rpc__.update({
                'get_keyword': RPC(cache=dict(days=1)),
                })
        cls._sql_indexes.add(
            Index(
                table,
                (table.keyword, Index.Equality()),
                (table.model, Index.Equality())))

    @classmethod
    def validate_fields(cls, actions, field_names):
        super().validate_fields(actions, field_names)
        cls.check_wizard_model(actions, field_names)

    @classmethod
    def check_wizard_model(cls, actions, field_names=None):
        pool = Pool()
        ActionWizard = pool.get('ir.action.wizard')
        if field_names and not (field_names & {'action', 'model'}):
            return
        for action in actions:
            if action.action.type == 'ir.action.wizard':
                action_wizards = ActionWizard.search([
                    ('action', '=', action.action.id),
                    ], limit=1)
                # could be empty when copying an action
                if action_wizards:
                    action_wizard, = action_wizards
                    if action_wizard.model:
                        if not str(action.model).startswith(
                                '%s,' % action_wizard.model):
                            raise WizardModelError(
                                gettext('ir.msg_action_wrong_wizard_model',
                                    name=action_wizard.rec_name))

    @classmethod
    def preprocess_values(cls, mode, values):
        pool = Pool()
        Action = pool.get('ir.action')
        values = super().preprocess_values(mode, values)
        if values.get('action') is not None:
            values['action'] = Action.get_action_id(values['action'])
        return values

    @classmethod
    def on_modification(cls, mode, keywords, field_names=None):
        super().on_modification(mode, keywords, field_names=field_names)
        ModelView._view_toolbar_get_cache.clear()
        cls._get_keyword_cache.clear()

    @staticmethod
    def models_get():
        pool = Pool()
        Model = pool.get('ir.model')
        return [(None, '')] + Model.get_name_items(ModelView)

    def get_groups(self, name):
        return [g.id for g in self.action.groups]

    @classmethod
    def search_groups(cls, name, clause):
        return [('action.' + clause[0],) + tuple(clause[1:])]

    @classmethod
    def get_keyword(cls, keyword, value):
        pool = Pool()
        Action = pool.get('ir.action')
        Menu = pool.get('ir.ui.menu')
        ModelAccess = pool.get('ir.model.access')
        User = pool.get('res.user')
        groups = User.get_groups()
        key = (Transaction().language, groups, keyword, tuple(value))
        keywords = cls._get_keyword_cache.get(key)
        if keywords is not None:
            return keywords
        keywords = []
        model, record_id = value

        clause = [
            ('keyword', '=', keyword),
            ['OR',
                ('model', '=', model + ',-1'),
                ('model', '=', None),
                ],
            ]
        if record_id is not None and record_id >= 0:
            clause = ['OR',
                clause,
                [
                    ('keyword', '=', keyword),
                    ('model', '=', model + ',' + str(record_id)),
                    ],
                ]
        clause = [clause, ('action.active', '=', True)]
        action_keywords = cls.search(clause, order=[])
        types = defaultdict(list)
        for action_keyword in action_keywords:
            type_ = action_keyword.action.type
            types[type_].append(action_keyword.action.id)
        for type_, action_ids in types.items():
            for value in Action.get_action_values(type_, action_ids):
                if (type_ == 'ir.action.act_window'
                        and value['res_model']
                        and not ModelAccess.check(
                            value['res_model'], raise_exception=False)):
                    continue
                value['keyword'] = keyword
                keywords.append(value)
        if (record_id is not None
                and keyword == 'tree_open' and model == Menu.__name__):
            menu = Menu(record_id)
            for value in keywords:
                if value['type'] == 'ir.action.act_window':
                    if len(keywords) == 1:
                        value['name'] = menu.name
                    if menu.parent:
                        parent = menu.parent
                        if parent.name == value['name']:
                            parent = parent.parent
                        if parent:
                            value['name'] = (
                                parent.rec_name + ' / ' + value['name'])
        keywords.sort(key=itemgetter('name'))
        cls._get_keyword_cache.set(key, keywords)
        return keywords


class ActionMixin(ModelSQL):
    _order_name = 'action'
    _action_name = 'name'

    action = fields.Many2One(
        'ir.action', "Action",
        required=True, readonly=True, ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        pool = Pool()
        super().__setup__()
        cls.__access__.add('action')
        cls.action.domain = [
            ('type', '=', cls.__name__),
            ]
        Action = pool.get('ir.action')
        for name in dir(Action):
            field = getattr(Action, name)
            if (isinstance(field, fields.Field)
                    and not getattr(cls, name, None)):
                setattr(cls, name, fields.Function(field, 'get_action',
                        setter='set_action', searcher='search_action'))
                default_func = 'default_' + name
                if getattr(Action, default_func, None):
                    setattr(cls, default_func,
                        partial(ActionMixin._default_action, name))

    @staticmethod
    def _default_action(name):
        pool = Pool()
        Action = pool.get('ir.action')
        return getattr(Action, 'default_' + name, None)()

    @classmethod
    def get_action(cls, ids, names):
        def identical(v):
            return v

        def list_int(v):
            return list(map(int, v))
        records = cls.browse(ids)
        result = {}
        for name in names:
            result[name] = values = {}
            for record in records:
                value = getattr(record, 'action')
                convert = identical
                if value is not None:
                    value = getattr(value, name)
                    if isinstance(value, ModelStorage):
                        if cls._fields[name]._type == 'reference':
                            convert = str
                        else:
                            convert = int
                    elif isinstance(value, (list, tuple)):
                        convert = list_int
                values[record.id] = convert(value)
        return result

    @classmethod
    def set_action(cls, records, name, value):
        pool = Pool()
        Action = pool.get('ir.action')
        Action.write([r.action for r in records], {
                name: value,
                })

    @classmethod
    def search_action(cls, name, clause):
        return [('action.' + clause[0],) + tuple(clause[1:])]

    @classmethod
    @without_check_access
    def get_groups(cls, name, action_id=None):
        pool = Pool()
        Action = pool.get('ir.action')

        key = (name, action_id)
        groups = Action._groups_cache.get(key)
        if groups is not None:
            return set(groups)

        domain = [
            (cls._action_name, '=', name),
            ]
        if action_id:
            domain.append(('id', '=', action_id))
        actions = cls.search(domain)
        groups = {g.id for a in actions for g in a.groups}
        Action._groups_cache.set(key, list(groups))
        return groups

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        pool = Pool()
        Action = pool.get('ir.action')
        ActionKeyword = pool.get('ir.action.keyword')
        super().on_modification(mode, records, field_names=field_names)
        ModelView._view_toolbar_get_cache.clear()
        ActionKeyword._get_keyword_cache.clear()
        if mode == 'delete':
            actions = [x.action for x in records]
            Action.delete(actions)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Action = pool.get('ir.action')
        ir_action = cls.__table__()
        new_records = []
        to_write = []
        for values in vlist:
            later = {}
            action_values = {}
            values = values.copy()
            for field in values:
                if field in Action._fields:
                    action_values[field] = values[field]
                if hasattr(getattr(cls, field), 'set'):
                    later[field] = values[field]
            for field in later:
                del values[field]
            action_values['type'] = cls.default_type()
            transaction = Transaction()
            database = transaction.database
            cursor = transaction.connection.cursor()
            if database.nextid(transaction.connection, cls._table):
                database.setnextid(transaction.connection, cls._table,
                    database.currid(transaction.connection, Action._table))
            if 'action' not in values:
                action, = Action.create([action_values])
                values['action'] = action.id
            else:
                action = Action(values['action'])
            record, = super().create([values])
            cursor.execute(*ir_action.update(
                    [ir_action.id], [action.id],
                    where=ir_action.id == record.id))
            record = cls(action.id)
            new_records.append(record)
            to_write.extend(([record], later))
        if to_write:
            cls.write(*to_write)
        return new_records

    @classmethod
    def copy(cls, records, default=None):
        pool = Pool()
        Action = pool.get('ir.action')
        if default is None:
            default = {}
        default = default.copy()
        new_records = []
        for record in records:
            default['action'] = Action.copy([record.action])[0].id
            new_records.extend(super().copy([record],
                    default=default))
        return new_records

    @classmethod
    def fetch_action(cls, action_id):
        fields = list(cls._fields.keys())
        return cls.search_read(
            [('action', '=', action_id)], fields_names=fields, limit=1)


class ActionReport(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,name', "Model",
            ondelete='CASCADE'),
        fields.fmany2one(
            'module_ref', 'module', 'ir.module,name', "Module",
            readonly=True, ondelete='CASCADE'),
        ActionMixin, ModelSQL, ModelView):
    __name__ = 'ir.action.report'
    _action_name = 'report_name'
    model = fields.Char('Model')
    report_name = fields.Char('Internal Name', required=True)
    report = fields.Char(
        "Path",
        states={
            'invisible': Eval('is_custom', False),
            },
        depends=['is_custom'])
    report_content_custom = fields.Binary('Content')
    is_custom = fields.Function(fields.Boolean("Is Custom"), 'get_is_custom')
    report_content = fields.Function(fields.Binary('Content',
            filename='report_content_name'),
        'get_report_content', setter='set_report_content')
    report_content_name = fields.Function(fields.Char('Content Name'),
        'on_change_with_report_content_name')
    report_content_html = fields.Function(fields.Binary(
            "Content HTML",
            states={
                'invisible': ~Eval('template_extension').in_(
                    ['html', 'xhtml']),
                },
            depends=['template_extension']),
        'get_report_content_html', setter='set_report_content_html')
    direct_print = fields.Boolean('Direct Print')
    single = fields.Boolean("Single",
        help="Check if the template works only for one record.")
    translatable = fields.Boolean("Translatable",
        help="Uncheck to disable translations for this report.")
    template_extension = fields.Selection([
            ('odt', 'OpenDocument Text'),
            ('odp', 'OpenDocument Presentation'),
            ('ods', 'OpenDocument Spreadsheet'),
            ('odg', 'OpenDocument Graphics'),
            ('txt', 'Plain Text'),
            ('xml', 'XML'),
            ('html', 'HTML'),
            ('xhtml', 'XHTML'),
            ], string='Template Extension', required=True,
        translate=False)
    extension = fields.Selection([
            ('', ''),
            ('bib', 'BibTex'),
            ('bmp', 'Windows Bitmap'),
            ('csv', 'Text CSV'),
            ('dbf', 'dBase'),
            ('dif', 'Data Interchange Format'),
            ('doc', 'Microsoft Word 97/2000/XP'),
            ('doc6', 'Microsoft Word 6.0'),
            ('doc95', 'Microsoft Word 95'),
            ('docbook', 'DocBook'),
            ('docx', 'Microsoft Office Open XML Text'),
            ('docx7', 'Microsoft Word 2007 XML'),
            ('emf', 'Enhanced Metafile'),
            ('eps', 'Encapsulated PostScript'),
            ('gif', 'Graphics Interchange Format'),
            ('html', 'HTML Document'),
            ('jpg', 'Joint Photographic Experts Group'),
            ('met', 'OS/2 Metafile'),
            ('ooxml', 'Microsoft Office Open XML'),
            ('pbm', 'Portable Bitmap'),
            ('pct', 'Mac Pict'),
            ('pdb', 'AportisDoc (Palm)'),
            ('pdf', 'Portable Document Format'),
            ('pgm', 'Portable Graymap'),
            ('png', 'Portable Network Graphic'),
            ('ppm', 'Portable Pixelmap'),
            ('ppt', 'Microsoft PowerPoint 97/2000/XP'),
            ('psw', 'Pocket Word'),
            ('pwp', 'PlaceWare'),
            ('pxl', 'Pocket Excel'),
            ('ras', 'Sun Raster Image'),
            ('rtf', 'Rich Text Format'),
            ('latex', 'LaTeX 2e'),
            ('sda', 'StarDraw 5.0 (OpenOffice.org Impress)'),
            ('sdc', 'StarCalc 5.0'),
            ('sdc4', 'StarCalc 4.0'),
            ('sdc3', 'StarCalc 3.0'),
            ('sdd', 'StarImpress 5.0'),
            ('sdd3', 'StarDraw 3.0 (OpenOffice.org Impress)'),
            ('sdd4', 'StarImpress 4.0'),
            ('sdw', 'StarWriter 5.0'),
            ('sdw4', 'StarWriter 4.0'),
            ('sdw3', 'StarWriter 3.0'),
            ('slk', 'SYLK'),
            ('svg', 'Scalable Vector Graphics'),
            ('svm', 'StarView Metafile'),
            ('swf', 'Macromedia Flash (SWF)'),
            ('sxc', 'OpenOffice.org 1.0 Spreadsheet'),
            ('sxi', 'OpenOffice.org 1.0 Presentation'),
            ('sxd', 'OpenOffice.org 1.0 Drawing'),
            ('sxd3', 'StarDraw 3.0'),
            ('sxd5', 'StarDraw 5.0'),
            ('sxw', 'Open Office.org 1.0 Text Document'),
            ('text', 'Text Encoded'),
            ('tiff', 'Tagged Image File Format'),
            ('txt', 'Plain Text'),
            ('wmf', 'Windows Metafile'),
            ('xhtml', 'XHTML Document'),
            ('xls', 'Microsoft Excel 97/2000/XP'),
            ('xls5', 'Microsoft Excel 5.0'),
            ('xls95', 'Microsoft Excel 95'),
            ('xlsx', 'Microsoft Excel 2007/2010 XML'),
            ('xpm', 'X PixMap'),
            ], translate=False,
        string='Extension', help='Leave empty for the same as template, '
        'see LibreOffice documentation for compatible format.')
    record_name = fields.Char(
        "Record Name", translate=True,
        help="A Genshi expression to compute the name using 'record'.\n"
        "Leave empty for the default name.",)
    module = fields.Char('Module', readonly=True)
    _template_cache = MemoryCache('ir.action.report.template', context=False)

    @staticmethod
    def default_type():
        return 'ir.action.report'

    @staticmethod
    def default_report_content():
        return None

    @staticmethod
    def default_direct_print():
        return False

    @classmethod
    def default_single(cls):
        return False

    @classmethod
    def default_translatable(cls):
        return True

    @staticmethod
    def default_template_extension():
        return 'odt'

    @staticmethod
    def default_extension():
        return ''

    @staticmethod
    def default_module():
        return Transaction().context.get('module')

    def get_is_custom(self, name):
        return bool(self.report_content_custom)

    @classmethod
    def get_report_content(cls, reports, name):
        contents = {}
        converter = fields.Binary.cast
        default = None
        format_ = Transaction().context.get(
            '%s.%s' % (cls.__name__, name), '')
        if format_ == 'size':
            converter = len
            default = 0
        for report in reports:
            data = getattr(report, name + '_custom')
            if not data and getattr(report, name[:-8]):
                try:
                    with file_open(
                            getattr(report, name[:-8]).replace('/', os.sep),
                            mode='rb') as fp:
                        data = fp.read()
                except Exception:
                    data = None
            contents[report.id] = converter(data) if data else default
        return contents

    @classmethod
    def set_report_content(cls, records, name, value):
        cls.write(records, {'%s_custom' % name: value})

    @classmethod
    def get_report_content_html(cls, reports, name):
        return cls.get_report_content(reports, name[:-5])

    @classmethod
    def set_report_content_html(cls, reports, name, value):
        if value is not None:
            value = value.encode('utf-8')
        cls.set_report_content(reports, name[:-5], value)

    @fields.depends('name', 'template_extension')
    def on_change_with_report_content_name(self, name=None):
        return ''.join(
            filter(None, [self.name, os.extsep, self.template_extension]))

    @classmethod
    def get_pyson(cls, reports, name):
        pysons = {}
        field = name[6:]
        defaults = {}
        for report in reports:
            pysons[report.id] = (getattr(report, field)
                or defaults.get(field, 'null'))
        return pysons

    @classmethod
    def copy(cls, reports, default=None):
        if default is None:
            default = {}
        default = default.copy()
        default.setdefault('module', None)
        default.setdefault(
            'report_content_custom',
            lambda o: None if o['report'] else o['report_content_custom'])
        return super().copy(reports, default=default)

    @classmethod
    def preprocess_values(cls, mode, values):
        context = Transaction().context
        values = super().preprocess_values(mode, values)
        if 'module' in context and not values.get('module'):
            values['module'] = context['module']
        return values

    @classmethod
    def on_modification(cls, mode, reports, field_names=None):
        super().on_modification(mode, reports, field_names=field_names)
        if mode == 'write':
            cls._template_cache.clear()

    def get_template_cached(self):
        return self._template_cache.get(self.id)

    def set_template_cached(self, template):
        self._template_cache.set(self.id, template)

    @classmethod
    def validate_fields(cls, reports, field_names):
        super().validate_fields(reports, field_names)
        cls.check_record_name(reports, field_names)

    @classmethod
    def check_record_name(cls, reports, field_names=None):
        if field_names and 'record_name' not in field_names:
            return
        for report in reports:
            if not report.record_name:
                return
            try:
                TextTemplate(report.record_name)
            except Exception as exception:
                raise ValidationError(gettext(
                        'ir.msg_report_invalid_record_name',
                        report=report.rec_name,
                        exception=exception)) from exception


class ActionActWindow(
        fields.fmany2one(
            'res_model_ref', 'res_model', 'ir.model,name', "Model",
            ondelete='CASCADE'),
        fields.fmany2one(
            'context_model_ref', 'context_model', 'ir.model,name',
            "Context Model", ondelete='CASCADE'),
        ActionMixin, ModelSQL, ModelView):
    __name__ = 'ir.action.act_window'
    domain = fields.Char('Domain Value')
    context = fields.Char('Context Value')
    order = fields.Char('Order Value')
    res_model = fields.Char('Model')
    context_model = fields.Char('Context Model')
    context_domain = fields.Char(
        "Context Domain",
        help="Part of the domain that will be evaluated on each refresh.")
    act_window_views = fields.One2Many('ir.action.act_window.view',
            'act_window', 'Views')
    views = fields.Function(fields.Field('Views'), 'get_views')
    act_window_domains = fields.One2Many('ir.action.act_window.domain',
        'act_window', 'Domains')
    domains = fields.Function(fields.Field('Domains'), 'get_domains')
    limit = fields.Integer('Limit', help='Default limit for the list view.')
    search_value = fields.Char('Search Criteria',
            help='Default search criteria for the list view.')
    pyson_domain = fields.Function(fields.Char('PySON Domain'), 'get_pyson')
    pyson_context = fields.Function(fields.Char('PySON Context'),
            'get_pyson')
    pyson_order = fields.Function(fields.Char('PySON Order'), 'get_pyson')
    pyson_search_value = fields.Function(fields.Char(
        'PySON Search Criteria'), 'get_pyson')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update({
                'get': RPC(cache=dict(days=1)),
                })

    @staticmethod
    def default_type():
        return 'ir.action.act_window'

    @staticmethod
    def default_context():
        return '{}'

    @staticmethod
    def default_search_value():
        return '[]'

    @classmethod
    def validate(cls, actions):
        super().validate(actions)
        cls.check_views(actions)

    @classmethod
    def validate_fields(cls, actions, field_names):
        super().validate_fields(actions, field_names)
        cls.check_domain(actions, field_names)
        cls.check_context(actions, field_names)

    @classmethod
    def check_views(cls, actions):
        "Check views"
        for action in actions:
            if action.res_model:
                for act_window_view in action.act_window_views:
                    view = act_window_view.view
                    if view.model != action.res_model:
                        raise ViewError(
                            gettext('ir.msg_action_invalid_views',
                                view=view.rec_name,
                                action=action.rec_name))
                    if view.type == 'board':
                        raise ViewError(
                            gettext('ir.msg_action_invalid_views',
                                view=view.rec_name,
                                action=action.rec_name))
            else:
                for act_window_view in action.act_window_views:
                    view = act_window_view.view
                    if view.model:
                        raise ViewError(
                            gettext('ir.msg_action_invalid_views',
                                view=view.rec_name,
                                action=action.rec_name))
                    if view.type != 'board':
                        raise ViewError(
                            gettext('ir.msg_action_invalid_views',
                                view=view.rec_name,
                                action=action.rec_name))

    @classmethod
    def check_domain(cls, actions, field_names=None):
        "Check domain and search_value"
        if field_names and not (field_names & {'domain', 'search_value'}):
            return
        for action in actions:
            for domain in (action.domain, action.search_value):
                if not domain:
                    continue
                try:
                    value = PYSONDecoder().decode(domain)
                except Exception as exception:
                    raise DomainError(
                        gettext('ir.msg_action_invalid_domain',
                            domain=domain,
                            action=action.rec_name)) from exception
                if isinstance(value, PYSON):
                    if not value.types() == set([list]):
                        raise DomainError(
                            gettext('ir.msg_action_invalid_domain',
                                domain=domain,
                                action=action.rec_name))
                elif not isinstance(value, list):
                    raise DomainError(
                        gettext('ir.msg_action_invalid_domain',
                            domain=domain,
                            action=action.rec_name))
                else:
                    try:
                        fields.domain_validate(value)
                    except Exception as exception:
                        raise DomainError(
                            gettext('ir.msg_action_invalid_domain',
                                domain=domain,
                                action=action.rec_name)) from exception

    @classmethod
    def check_context(cls, actions, field_names=None):
        "Check context"
        if field_names and 'context' not in field_names:
            return
        for action in actions:
            if action.context:
                try:
                    value = PYSONDecoder().decode(action.context)
                except Exception as exception:
                    raise ContextError(
                        gettext('ir.msg_action_invalid_context',
                            context=action.context,
                            action=action.rec_name)) from exception
                if isinstance(value, PYSON):
                    if not value.types() == set([dict]):
                        raise ContextError(
                            gettext('ir.msg_action_invalid_context',
                                context=action.context,
                                action=action.rec_name))
                elif not isinstance(value, dict):
                    raise ContextError(
                        gettext('ir.msg_action_invalid_context',
                            context=action.context,
                            action=action.rec_name))
                else:
                    try:
                        fields.context_validate(value)
                    except Exception as exception:
                        raise ContextError(
                            gettext('ir.msg_action_invalid_context',
                                context=action.context,
                                action=action.rec_name)) from exception

    def get_views(self, name):
        return [(view.view.id, view.view.rng_type)
            for view in self.act_window_views]

    def get_domains(self, name):
        return [(domain.name, domain.domain or '[]', domain.count)
            for domain in self.act_window_domains]

    @classmethod
    def get_pyson(cls, windows, name):
        pool = Pool()
        encoder = PYSONEncoder()
        pysons = {}
        field = name[6:]
        defaults = {
            'domain': '[]',
            'context': '{}',
            'search_value': '[]',
            }
        for window in windows:
            if not window.order and field == 'order':
                if window.res_model:
                    defaults['order'] = encoder.encode(
                        getattr(pool.get(window.res_model), '_order', 'null'))
                else:
                    defaults['order'] = 'null'
            pysons[window.id] = (getattr(window, field)
                or defaults.get(field, 'null'))
        return pysons

    @classmethod
    def get(cls, xml_id):
        'Get values from XML id or id'
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Action = pool.get('ir.action')
        if '.' in xml_id:
            action_id = ModelData.get_id(*xml_id.split('.'))
        else:
            action_id = int(xml_id)
        return Action(action_id).get_action_value()


class ActionActWindowView(
        sequence_ordered(), DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'ir.action.act_window.view'
    view = fields.Many2One(
        'ir.ui.view', "View", required=True, ondelete='CASCADE',
        domain=[
            ('model', '=', Eval('model', None)),
            ])
    act_window = fields.Many2One('ir.action.act_window', 'Action',
            ondelete='CASCADE')
    model = fields.Function(fields.Char("Model"), 'on_change_with_model')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('act_window')

    @fields.depends('act_window', '_parent_act_window.res_model')
    def on_change_with_model(self, name=None):
        if self.act_window:
            return self.act_window.res_model

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        pool = Pool()
        Keyword = pool.get('ir.action.keyword')
        super().on_modification(mode, records, field_names=field_names)
        Keyword._get_keyword_cache.clear()


class ActionActWindowDomain(
        sequence_ordered(), DeactivableMixin, ModelSQL, ModelView):
    __name__ = 'ir.action.act_window.domain'
    name = fields.Char('Name', translate=True)
    domain = fields.Char('Domain')
    count = fields.Boolean('Count')
    act_window = fields.Many2One('ir.action.act_window', 'Action',
        required=True, ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('act_window')

    @classmethod
    def default_count(cls):
        return False

    @classmethod
    def validate_fields(cls, actions, field_names):
        super().validate_fields(actions, field_names)
        cls.check_domain(actions, field_names)

    @classmethod
    def check_domain(cls, actions, field_names=None):
        if field_names and 'domain' not in field_names:
            return
        for action in actions:
            if not action.domain:
                continue
            try:
                value = PYSONDecoder().decode(action.domain)
            except Exception as exception:
                raise DomainError(gettext(
                        'ir.msg_action_invalid_domain',
                        domain=action.domain,
                        action=action.rec_name)) from exception
            if isinstance(value, PYSON):
                if not value.types() == set([list]):
                    raise DomainError(gettext(
                            'ir.msg_action_invalid_domain',
                            domain=action.domain,
                            action=action.rec_name))
            elif not isinstance(value, list):
                raise DomainError(gettext(
                        'ir.msg_action_invalid_domain',
                        domain=action.domain,
                        action=action.rec_name))
            else:
                try:
                    fields.domain_validate(value)
                except Exception as exception:
                    raise DomainError(gettext(
                            'ir.msg_action_invalid_domain',
                            domain=action.domain,
                            action=action.rec_name)) from exception

    @classmethod
    def on_modification(cls, mode, records, field_names=None):
        pool = Pool()
        Keyword = pool.get('ir.action.keyword')
        super().on_modification(mode, records, field_names=field_names)
        Keyword._get_keyword_cache.clear()


class ActionWizard(
        fields.fmany2one(
            'model_ref', 'model', 'ir.model,name', "Model",
            ondelete='CASCADE'),
        ActionMixin, ModelSQL, ModelView):
    __name__ = 'ir.action.wizard'
    _action_name = 'wiz_name'
    wiz_name = fields.Char('Wizard name', required=True)
    model = fields.Char('Model')
    window = fields.Boolean('Window', help='Run wizard in a new window.')

    @staticmethod
    def default_type():
        return 'ir.action.wizard'

    @classmethod
    def get_models(cls, name, action_id=None):
        # TODO add cache
        domain = [
            (cls._action_name, '=', name),
            ]
        if action_id:
            domain.append(('id', '=', action_id))
        actions = cls.search(domain)
        return {a.model for a in actions if a.model}

    @classmethod
    def get_name(cls, name, model):
        # TODO add cache
        actions = cls.search([
                (cls._action_name, '=', name),
                ('model', '=', model),
                ], limit=1)
        if actions:
            action, = actions
            return action.name
        return name


class ActionURL(ActionMixin, ModelSQL, ModelView):
    __name__ = 'ir.action.url'
    url = fields.Char('Action Url', required=True)

    @staticmethod
    def default_type():
        return 'ir.action.url'
