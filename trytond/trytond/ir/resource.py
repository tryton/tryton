# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import defaultdict

from sql.conditionals import Coalesce

from trytond.i18n import lazy_gettext
from trytond.model import (
    Index, Model, ModelSQL, ModelStorage, ModelView, fields)
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.tools import grouped_slice
from trytond.transaction import Transaction, without_check_access

__all__ = ['ResourceAccessMixin', 'ResourceMixin', 'resource_copy']


class ResourceAccessMixin(ModelStorage):

    resource = fields.Reference(
        "Resource", selection='get_models', required=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        if issubclass(cls, ModelSQL):
            table = cls.__table__()
            cls._sql_indexes.add(
                Index(table, (table.resource, Index.Similarity(begin=True))))

    @classmethod
    def default_resource(cls):
        return Transaction().context.get('resource')

    @staticmethod
    def get_models():
        pool = Pool()
        Model = pool.get('ir.model')
        ModelAccess = pool.get('ir.model.access')
        models = Model.get_name_items()
        if Transaction().check_access:
            access = ModelAccess.get_access([m for m, _ in models])
            models = [(m, n) for m, n in models if access[m]['read']]
        return models

    @classmethod
    def check_access(cls, ids, mode='read'):
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        transaction = Transaction()
        if transaction.user == 0 or not transaction.check_access:
            return
        model_names = set()
        with without_check_access():
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
    def search(
            cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        transaction = Transaction()
        result = super().search(
            domain, offset=offset, limit=limit, order=order,
            count=False if not query else count, query=query)
        if not query and transaction.user and transaction.check_access:
            records = result
            resources = defaultdict(set)
            allowed = set()
            with without_check_access():
                records = cls.browse(records)
            for record in records:
                if isinstance(record.resource, Model):
                    resources[record.resource.__class__].add(
                        record.resource.id)

            for RModel, ids in resources.items():
                for sub_ids in grouped_slice(ids):
                    allowed.update(RModel.search([
                                ('id', 'in', list(sub_ids)),
                                ]))

            records = [
                r for r in records
                if not r.resource or r.resource in allowed]
            if count:
                result = len(records)
            else:
                # re-browse to have same context
                result = cls.browse(records)
        return result

    @classmethod
    def read(cls, ids, fields_names):
        cls.check_access(ids, mode='read')
        return super().read(ids, fields_names)

    @classmethod
    def delete(cls, records):
        cls.check_access([a.id for a in records], mode='delete')
        super().delete(records)

    @classmethod
    def write(cls, records, values, *args):
        all_records = []
        actions = iter((records, values) + args)
        for other_records, _ in zip(actions, actions):
            all_records += other_records
        cls.check_access([a.id for a in all_records], mode='write')
        super().write(records, values, *args)
        cls.check_access(all_records, mode='write')

    @classmethod
    def create(cls, vlist):
        records = super().create(vlist)
        cls.check_access([r.id for r in records], mode='create')
        return records


class ResourceMixin(ResourceAccessMixin, ModelStorage, ModelView):

    copy_to_resources = fields.MultiSelection(
        'get_copy_to_resources', "Copy to Resources",
        states={
            'invisible': ~Eval('copy_to_resources_visible'),
            },
        depends=['copy_to_resources_visible'])
    copy_to_resources_visible = fields.Function(
        fields.Boolean("Copy to Resources Visible"),
        'on_change_with_copy_to_resources_visible')
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
        cls.resource.required = True

    @fields.depends('resource')
    def get_copy_to_resources(self):
        pool = Pool()
        Model = pool.get('ir.model')
        resources = []
        if isinstance(self.resource, ResourceCopyMixin):
            models = self.resource.get_resources_to_copy(self.__name__)
            resources.extend((m, Model.get_name(m)) for m in models)
        return resources

    @fields.depends(methods=['get_copy_to_resources'])
    def on_change_with_copy_to_resources_visible(self, name=None):
        return bool(self.get_copy_to_resources())

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


class ResourceCopyMixin(ModelStorage):

    @classmethod
    def get_resources_to_copy(cls, name):
        return set()


def resource_copy(resource, name, string):

    class _ResourceCopyMixin(ResourceCopyMixin):

        @classmethod
        def copy(cls, records, default=None):
            if default is None:
                default = {}
            else:
                default = default.copy()
            default.setdefault(name, None)
            return super().copy(records, default=default)

        def copy_resources_to(self, target):
            pool = Pool()
            Resource = pool.get(resource)

            try:
                super().copy_resources_to(target)
            except AttributeError:
                pass

            to_copy = []
            for record in getattr(self, name):
                if (record.copy_to_resources
                        and target.__name__ in record.copy_to_resources):
                    to_copy.append(record)
            if to_copy:
                return Resource.copy(to_copy, default={
                        'resource': str(target),
                        'copy_to_resources': None,
                        })

    setattr(_ResourceCopyMixin, name, fields.One2Many(
            resource, 'resource', string,
            help=lazy_gettext('ir.msg_resource_copy_help')))
    return _ResourceCopyMixin
