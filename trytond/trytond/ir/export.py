# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Exports"
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.transaction import Transaction


class _ClearCache(ModelSQL):
    @classmethod
    def create(cls, vlist):
        ModelView._view_toolbar_get_cache.clear()
        return super().create(vlist)

    @classmethod
    def write(cls, *args):
        ModelView._view_toolbar_get_cache.clear()
        super().write(*args)

    @classmethod
    def delete(cls, records):
        ModelView._view_toolbar_get_cache.clear()
        super().delete(records)


class Export(_ClearCache, ModelSQL, ModelView):
    "Export"
    __name__ = "ir.export"
    name = fields.Char('Name')
    resource = fields.Char('Resource')
    user = fields.Many2One(
        'res.user', "User", required=True, ondelete='CASCADE')
    header = fields.Boolean(
        "Header",
        help="Check to include field names on the export.")
    records = fields.Selection([
            ('selected', "Selected"),
            ('listed', "Listed"),
            ], "Records",
        help="The records on which the export runs.")
    export_fields = fields.One2Many('ir.export.line', 'export',
       'Fields')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update(
            get=RPC(check_access=False),
            set=RPC(check_access=False, readonly=False),
            update=RPC(check_access=False, readonly=False),
            unset=RPC(check_access=False, readonly=False),
            )

    @classmethod
    def __register__(cls, module):
        table_h = cls.__table_handler__(module)
        table = cls.__table__()
        cursor = Transaction().connection.cursor()

        user_exists = table_h.column_exist('user')

        super().__register__(module)

        # Migration from 6.8: add user
        if not user_exists:
            cursor.execute(*table.update([table.user], [table.create_uid]))

    @classmethod
    def default_header(cls):
        return False

    @classmethod
    def default_records(cls):
        return 'selected'

    @classmethod
    def get(cls, resource, fields_names):
        pool = Pool()
        User = pool.get('res.user')
        return cls.search_read([
                ('resource', '=', resource),
                ['OR',
                    ('groups', 'in', User.get_groups()),
                    ('user', '=', Transaction().user),
                    ],
                ],
                fields_names=fields_names)

    @classmethod
    def set(cls, values):
        export = cls(**values)
        export.user = Transaction().user
        export.save()
        return export.id

    @classmethod
    def update(cls, id, values, fields):
        pool = Pool()
        User = pool.get('res.user')
        exports = cls.search([
                ('id', '=', id),
                ['OR',
                    ('write_groups', 'in', User.get_groups()),
                    ('user', '=', Transaction().user),
                    ],
                ])
        try:
            export, = exports
        except ValueError:
            return
        for name, value in values.items():
            setattr(export, name, value)
        lines = []
        for name in fields:
            lines.append({'name': name})
        export.export_fields = lines
        export.save()

    @classmethod
    def unset(cls, id):
        pool = Pool()
        User = pool.get('res.user')
        cls.delete(cls.search([
                    ('id', '=', id),
                    ['OR',
                        ('write_groups', 'in', User.get_groups()),
                        ('user', '=', Transaction().user),
                        ],
                    ]))


class ExportLine(_ClearCache, ModelSQL, ModelView):
    "Export line"
    __name__ = 'ir.export.line'
    name = fields.Char('Name')
    export = fields.Many2One('ir.export', 'Export', required=True,
        ondelete='CASCADE')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__access__.add('export')
