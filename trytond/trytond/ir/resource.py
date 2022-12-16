# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.conditionals import Coalesce

from ..model import ModelSQL, ModelView, fields
from ..pool import Pool
from ..transaction import Transaction
from ..pyson import Eval

__all__ = ['ResourceMixin']


class ResourceMixin(ModelSQL, ModelView):

    resource = fields.Reference('Resource', selection='get_models',
        required=True, select=True)
    last_user = fields.Function(fields.Char('Last User',
            states={
                'invisible': ~Eval('last_user'),
                }),
        'get_last_user')
    last_modification = fields.Function(fields.DateTime('Last Modification',
            states={
                'invisible': ~Eval('last_modification'),
                }),
        'get_last_modification')

    @classmethod
    def __setup__(cls):
        super(ResourceMixin, cls).__setup__()
        cls._order.insert(0, ('last_modification', 'DESC'))

    @staticmethod
    def default_resource():
        return Transaction().context.get('resource')

    @staticmethod
    def get_models():
        pool = Pool()
        Model = pool.get('ir.model')
        ModelAccess = pool.get('ir.model.access')
        models = Model.search([])
        access = ModelAccess.get_access([m.model for m in models])
        return [(m.model, m.name) for m in models if access[m.model]['read']]

    def get_last_user(self, name):
        return (self.write_uid.rec_name if self.write_uid
            else self.create_uid.rec_name)

    def get_last_modification(self, name):
        return (self.write_date if self.write_date else self.create_date
            ).replace(microsecond=0)

    @staticmethod
    def order_last_modification(tables):
        table, _ = tables[None]
        return [Coalesce(table.write_date, table.create_date)]

    @classmethod
    def check_access(cls, ids, mode='read'):
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        if ((Transaction().user == 0)
                or not Transaction().context.get('_check_access')):
            return
        model_names = set()
        with Transaction().set_context(_check_access=False):
            for record in cls.browse(ids):
                if record.resource:
                    model_names.add(str(record.resource).split(',')[0])
        for model_name in model_names:
            checks = cls._convert_check_access(model_name, mode)
            for model, check_mode in checks:
                ModelAccess.check(model, mode=check_mode)

    @classmethod
    def _convert_check_access(cls, model, mode):
        return [
            (model, {'create': 'write', 'delete': 'write'}.get(mode, mode))]

    @classmethod
    def read(cls, ids, fields_names):
        cls.check_access(ids, mode='read')
        return super(ResourceMixin, cls).read(ids, fields_names)

    @classmethod
    def delete(cls, records):
        cls.check_access([a.id for a in records], mode='delete')
        super(ResourceMixin, cls).delete(records)

    @classmethod
    def write(cls, records, values, *args):
        all_records = []
        actions = iter((records, values) + args)
        for other_records, _ in zip(actions, actions):
            all_records += other_records
        cls.check_access([a.id for a in all_records], mode='write')
        super(ResourceMixin, cls).write(records, values, *args)
        cls.check_access(all_records, mode='write')

    @classmethod
    def create(cls, vlist):
        records = super(ResourceMixin, cls).create(vlist)
        cls.check_access([r.id for r in records], mode='create')
        return records
