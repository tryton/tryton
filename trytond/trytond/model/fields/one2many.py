#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from itertools import chain
from trytond.model.fields.field import Field, size_validate
from trytond.transaction import Transaction
from trytond.pool import Pool


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
            order_field=None, context=None, loading='lazy'):
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
            depends=depends, order_field=order_field, context=context,
            loading=loading)
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
        if self.field in Relation._fields:
            field = Relation._fields[self.field]
        else:
            field = Relation._inherit_fields[self.field][2]
        res = {}
        for i in ids:
            res[i] = []
        ids2 = []
        for i in range(0, len(ids), Transaction().cursor.IN_MAX):
            sub_ids = ids[i:i + Transaction().cursor.IN_MAX]
            if field._type == 'reference':
                references = ['%s,%s' % (model.__name__, x) for x in sub_ids]
                clause = [(self.field, 'in', references)]
            else:
                clause = [(self.field, 'in', sub_ids)]
            ids2.append(map(int, Relation.search(clause, order=self.order)))

        cache = Transaction().cursor.get_cache(Transaction().context)
        cache.setdefault(self.model_name, {})
        ids3 = []
        for i in chain(*ids2):
            if i in cache[self.model_name] \
                    and self.field in cache[self.model_name][i]:
                if field._type == 'reference':
                    _, id_ = cache[self.model_name][i][self.field].split(',')
                    id_ = int(id_)
                else:
                    id_ = cache[self.model_name][i][self.field]
                res[id_].append(i)
            else:
                ids3.append(i)

        if ids3:
            for i in Relation.read(ids3, [self.field]):
                if field._type == 'reference':
                    _, id_ = i[self.field].split(',')
                    id_ = int(id_)
                else:
                    id_ = i[self.field]
                res[id_].append(i['id'])

        index_of_ids2 = dict((i, index)
            for index, i in enumerate(chain(*ids2)))
        for id_, val in res.iteritems():
            res[id_] = tuple(sorted(val, key=lambda x: index_of_ids2[x]))
        return res

    def set(self, ids, model, name, values):
        '''
        Set the values.
        values: A list of tuples:
            (``create``, ``{<field name>: value}``),
            (``write``, ``<ids>``, ``{<field name>: value}``),
            (``delete``, ``<ids>``),
            (``delete_all``),
            (``unlink``, ``<ids>``),
            (``add``, ``<ids>``),
            (``unlink_all``),
            (``set``, ``<ids>``)
        '''
        if not values:
            return
        Target = self.get_target()
        if self.field in Target._fields:
            field = Target._fields[self.field]
        else:
            field = Target._inherit_fields[self.field][2]

        def search_clause(ids):
            if field._type == 'reference':
                references = ['%s,%s' % (model.__name__, x) for x in ids]
                return (self.field, 'in', references)
            else:
                return (self.field, 'in', ids)

        def field_value(record_id):
            if field._type == 'reference':
                return '%s,%s' % (model.__name__, record_id)
            else:
                return record_id

        for act in values:
            if act[0] == 'create':
                for record_id in ids:
                    act[1][self.field] = field_value(record_id)
                    Target.create(act[1])
            elif act[0] == 'write':
                Target.write(Target.browse(act[1]), act[2])
            elif act[0] == 'delete':
                Target.delete(Target.browse(act[1]))
            elif act[0] == 'delete_all':
                targets = Target.search([
                        search_clause(ids),
                        ])
                Target.delete(targets)
            elif act[0] == 'unlink':
                target_ids = map(int, act[1])
                if not target_ids:
                    continue
                targets = Target.search([
                        search_clause(ids),
                        ('id', 'in', target_ids),
                        ])
                Target.write(targets, {
                        self.field: None,
                        })
            elif act[0] == 'add':
                target_ids = map(int, act[1])
                if not target_ids:
                    continue
                for record_id in ids:
                    Target.write(Target.browse(target_ids), {
                            self.field: field_value(record_id),
                            })
            elif act[0] == 'unlink_all':
                targets = Target.search([
                        search_clause(ids),
                        ])
                Target.write(targets, {
                        self.field: None,
                        })
            elif act[0] == 'set':
                if not act[1]:
                    target_ids = [-1]
                else:
                    target_ids = map(int, act[1])
                for record_id in ids:
                    targets = Target.search([
                            search_clause([record_id]),
                            ('id', 'not in', target_ids),
                            ])
                    Target.write(targets, {
                            self.field: None,
                            })
                    if act[1]:
                        Target.write(Target.browse(target_ids), {
                                self.field: field_value(record_id),
                                })
            else:
                raise Exception('Bad arguments')

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
        value = [instance(x) for x in (value or [])]
        super(One2Many, self).__set__(inst, value)
