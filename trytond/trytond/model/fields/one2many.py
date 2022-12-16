# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import chain
from sql import Cast, Literal
from sql.functions import Substring, Position

from .field import Field, size_validate
from ...pool import Pool
from ...tools import grouped_slice


def add_remove_validate(value):
    if value:
        assert isinstance(value, list), 'add_remove must be a list'


class One2Many(Field):
    '''
    Define one2many field (``list``).
    '''
    _type = 'one2many'

    def __init__(self, model_name, field, string='', add_remove=None,
            order=None, datetime_field=None, size=None, help='',
            required=False, readonly=False, domain=None, states=None,
            on_change=None, on_change_with=None, depends=None,
            context=None, loading='lazy'):
        '''
        :param model_name: The name of the target model.
        :param field: The name of the field that handle the reverse many2one or
            reference.
        :param add_remove: A list that defines a domain on add/remove.
            See domain on ModelStorage.search.
        :param order:  a list of tuples that are constructed like this:
            ``('field name', 'DESC|ASC')``
            allowing to specify the order of result.
        :param datetime_field: The name of the field that contains the datetime
            value to read the target records.
        '''
        if datetime_field:
            if depends:
                depends.append(datetime_field)
            else:
                depends = [datetime_field]
        super(One2Many, self).__init__(string=string, help=help,
            required=required, readonly=readonly, domain=domain, states=states,
            on_change=on_change, on_change_with=on_change_with,
            depends=depends, context=context, loading=loading)
        self.model_name = model_name
        self.field = field
        self.__add_remove = None
        self.add_remove = add_remove
        self.order = order
        self.datetime_field = datetime_field
        self.__size = None
        self.size = size

    __init__.__doc__ += Field.__init__.__doc__

    def _get_add_remove(self):
        return self.__add_remove

    def _set_add_remove(self, value):
        add_remove_validate(value)
        self.__add_remove = value

    add_remove = property(_get_add_remove, _set_add_remove)

    def _get_size(self):
        return self.__size

    def _set_size(self, value):
        size_validate(value)
        self.__size = value

    size = property(_get_size, _set_size)

    def get(self, ids, model, name, values=None):
        '''
        Return target records ordered.
        '''
        pool = Pool()
        Relation = pool.get(self.model_name)
        field = Relation._fields[self.field]
        res = {}
        for i in ids:
            res[i] = []

        targets = []
        for sub_ids in grouped_slice(ids):
            if field._type == 'reference':
                references = ['%s,%s' % (model.__name__, x) for x in sub_ids]
                clause = [(self.field, 'in', references)]
            else:
                clause = [(self.field, 'in', list(sub_ids))]
            targets.append(Relation.search(clause, order=self.order))
        targets = list(chain(*targets))

        for target in targets:
            origin_id = getattr(target, self.field).id
            res[origin_id].append(target.id)
        return dict((key, tuple(value)) for key, value in res.iteritems())

    def set(self, Model, name, ids, values, *args):
        '''
        Set the values.
        values: A list of tuples:
            (``create``, ``[{<field name>: value}, ...]``),
            (``write``, [``<ids>``, ``{<field name>: value}``, ...]),
            (``delete``, ``<ids>``),
            (``add``, ``<ids>``),
            (``remove``, ``<ids>``),
            (``copy``, ``<ids>``, ``[{<field name>: value}, ...]``)
        '''
        Target = self.get_target()
        field = Target._fields[self.field]
        to_create = []
        to_write = []
        to_delete = []

        def search_clause(ids):
            if field._type == 'reference':
                references = ['%s,%s' % (Model.__name__, x) for x in ids]
                return (self.field, 'in', references)
            else:
                return (self.field, 'in', ids)

        def field_value(record_id):
            if field._type == 'reference':
                return '%s,%s' % (Model.__name__, record_id)
            else:
                return record_id

        def create(ids, vlist):
            for record_id in ids:
                value = field_value(record_id)
                for values in vlist:
                    values = values.copy()
                    values[self.field] = value
                    to_create.append(values)

        def write(_, *args):
            actions = iter(args)
            to_write.extend(sum(((Target.browse(ids), values)
                        for ids, values in zip(actions, actions)), ()))

        def delete(_, target_ids):
            to_delete.extend(Target.browse(target_ids))

        def add(ids, target_ids):
            target_ids = map(int, target_ids)
            if not target_ids:
                return
            targets = Target.browse(target_ids)
            for record_id in ids:
                to_write.extend((targets, {
                            self.field: field_value(record_id),
                            }))

        def remove(ids, target_ids):
            target_ids = map(int, target_ids)
            if not target_ids:
                return
            for sub_ids in grouped_slice(target_ids):
                targets = Target.search([
                        search_clause(ids),
                        ('id', 'in', list(sub_ids)),
                        ])
                to_write.extend((targets, {
                            self.field: None,
                            }))

        def copy(ids, copy_ids, default=None):
            copy_ids = map(int, copy_ids)

            if default is None:
                default = {}
            default = default.copy()
            copies = Target.browse(copy_ids)
            for record_id in ids:
                default[self.field] = field_value(record_id)
                Target.copy(copies, default=default)

        actions = {
            'create': create,
            'write': write,
            'delete': delete,
            'add': add,
            'remove': remove,
            'copy': copy,
            }
        args = iter((ids, values) + args)
        for ids, values in zip(args, args):
            if not values:
                continue
            for value in values:
                action = value[0]
                args = value[1:]
                actions[action](ids, *args)
        if to_create:
            Target.create(to_create)
        if to_write:
            Target.write(*to_write)
        if to_delete:
            Target.delete(to_delete)

    def get_target(self):
        'Return the target Model'
        return Pool().get(self.model_name)

    def __set__(self, inst, value):
        Target = self.get_target()

        def instance(data):
            if isinstance(data, Target):
                return data
            elif isinstance(data, dict):
                return Target(**data)
            else:
                return Target(data)
        value = tuple(instance(x) for x in (value or []))
        super(One2Many, self).__set__(inst, value)

    def convert_domain(self, domain, tables, Model):
        Target = self.get_target()
        target = Target.__table__()
        table, _ = tables[None]
        name, operator, value = domain[:3]

        origin_field = Target._fields[self.field]
        origin = getattr(Target, self.field).sql_column(target)
        origin_where = None
        if origin_field._type == 'reference':
            origin_where = origin.like(Model.__name__ + ',%')
            origin = Cast(Substring(origin,
                    Position(',', origin) + Literal(1)),
                Target.id.sql_type().base)

        if '.' not in name:
            if value is None:
                where = origin != value
                if origin_where:
                    where &= origin_where
                query = target.select(origin, where=where)
                expression = ~table.id.in_(query)
                if operator == '!=':
                    return ~expression
                return expression
            else:
                if isinstance(value, basestring):
                    target_name = 'rec_name'
                else:
                    target_name = 'id'
        else:
            _, target_name = name.split('.', 1)
        target_domain = [(target_name,) + tuple(domain[1:])]
        query = Target.search(target_domain, order=[], query=True)
        where = target.id.in_(query)
        if origin_where:
            where &= origin_where
        query = target.select(origin, where=where)
        return table.id.in_(query)
