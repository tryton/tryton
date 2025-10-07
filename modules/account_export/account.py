# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import trytond.config as config
from trytond.i18n import gettext
from trytond.model import ModelSQL, ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

if config.getboolean('account_export', 'filestore', default=False):
    file_id = 'file_id'
    store_prefix = config.get('account_export', 'store_prefix', default=None)
else:
    file_id = store_prefix = None


class _ExportTypes:
    __slots__ = ()

    @classmethod
    def get_move_export_types(cls):
        pool = Pool()
        MoveExport = pool.get('account.move.export')
        return MoveExport.fields_get(['type'])['type']['selection']


class Configuration(_ExportTypes, metaclass=PoolMeta):
    __name__ = 'account.configuration'

    move_export_type = fields.MultiValue(fields.Selection(
            'get_move_export_types', "Move Export Type"))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'move_export_type':
            return pool.get('account.configuration.export')
        return super().multivalue_model(field)


class ConfigurationExport(_ExportTypes, ModelSQL, CompanyValueMixin):
    __name__ = 'account.configuration.export'

    move_export_type = fields.Selection(
        'get_move_export_types', "Move Export Type")


class Move(metaclass=PoolMeta):
    __name__ = 'account.move'

    export = fields.Many2One(
        'account.move.export', "Export", readonly=True, ondelete='RESTRICT',
        domain=[
            ('company', '=', Eval('company', -1)),
            ])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._check_modify_exclude.add('export')

    @classmethod
    def copy(cls, moves, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('export')
        return super().copy(moves, default=default)


class MoveExport(Workflow, ModelSQL, ModelView):
    __name__ = 'account.move.export'

    company = fields.Many2One('company.company', "Company", required=True)
    type = fields.Selection([
            (None, ""),
            ], "Type",
        states={
            'readonly': Eval('state') != 'draft',
            })
    moves = fields.One2Many(
        'account.move', 'export', "Moves", readonly=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ('state', '=', 'posted'),
            ],
        order=[
            ('id', 'ASC'),
            ])
    file = fields.Binary("File", filename='filename',
        file_id=file_id, store_prefix=store_prefix, readonly=True)
    file_id = fields.Char("File ID", readonly=True)
    filename = fields.Function(fields.Char("Filename"), 'get_filename')
    state = fields.Selection([
            ('draft', "Draft"),
            ('waiting', "Waiting"),
            ('done', "Done"),
            ], "State", readonly=True, sort=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions |= {
            ('draft', 'draft'),
            ('draft', 'waiting'),
            ('waiting', 'draft'),
            ('waiting', 'done'),
            }
        cls._buttons.update({
                'draft': {
                    'invisible': ~(
                        ((Eval('state') == 'draft') & Eval('moves'))
                        | (Eval('state') == 'waiting')),
                    'depends': ['state'],
                    },
                'select_moves': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'wait': {
                    'invisible': Eval('state') != 'draft',
                    'readonly': ~Eval('moves'),
                    'depends': ['state', 'moves'],
                    },
                'do': {
                    'invisible': Eval('state') != 'waiting',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @fields.depends('company')
    def on_change_company(self):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        if self.company:
            self.type = Configuration(1).get_multivalue(
                'move_export_type', company=self.company.id)
        else:
            self.type = None

    @classmethod
    def default_type(cls):
        pool = Pool()
        Configuration = pool.get('account.configuration')
        return Configuration(1).get_multivalue(
            'move_export_type', company=cls.default_company())

    def get_filename(self, name):
        pass

    @classmethod
    def default_state(cls):
        return 'draft'

    def get_rec_name(self, name):
        return f'{self.company.rec_name} ({self.id})'

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, exports):
        pool = Pool()
        Move = pool.get('account.move')
        moves = list(sum((e.moves for e in exports), ()))
        Move.write(moves, {'export': None})
        cls.write(exports, {'file': None})

    @classmethod
    @ModelView.button
    def select_moves(cls, exports):
        pool = Pool()
        Move = pool.get('account.move')
        exports = [e for e in exports if e.state == 'draft']
        moves = list(sum((e.moves for e in exports), ()))
        Move.write(moves, {'export': None})

        for export in exports:
            export.moves = Move.search([
                    ('export', '=', None),
                    ('company', '=', export.company.id),
                    ])
            export.file = None
        cls.save(exports)

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, exports):
        for export in exports:
            if export.type:
                getattr(export, f'_process_{export.type}')()
        cls.save(exports)

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, exports):
        pass

    @classmethod
    def copy(cls, exports, default=None):
        default = default.copy() if default is not None else {}
        default.setdefault('moves')
        return super().copy(exports, default=default)

    @classmethod
    def check_modification(cls, mode, exports, values=None, external=False):
        super().check_modification(
            mode, exports, values=values, external=external)
        if mode == 'delete':
            for export in exports:
                if export.state != 'draft':
                    raise AccessError(gettext(
                            'account_export.'
                            'msg_account_move_export_delete_draft',
                            export=export.rec_name))
