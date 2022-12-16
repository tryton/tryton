#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field
from itertools import chain

def add_remove_validate(value):
    if value:
        assert isinstance(value, list), 'add_remove must be a list'


class One2Many(Field):
    '''
    Define one2many field (``list``).
    '''
    _type = 'one2many'

    def __init__(self, model_name, field, string='', add_remove=None,
            order=None, datetime_field=None, help='', required=False,
            readonly=False, domain=None, states=None, priority=0,
            change_default=False, select=0, on_change=None,
            on_change_with=None, depends=None, order_field=None, context=None):
        '''
        :param model_name: The name of the target model.
        :param field: The name of the field that handle the reverse many2one.
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
                required=required, readonly=readonly, domain=domain,
                states=states, priority=priority,
                change_default=change_default, select=select,
                on_change=on_change, on_change_with=on_change_with,
                depends=depends, order_field=order_field, context=context)
        self.model_name = model_name
        self.field = field
        self.__add_remove = None
        self.add_remove = add_remove
        self.order = order
        self.datetime_field = datetime_field

    __init__.__doc__ += Field.__init__.__doc__

    def _get_add_remove(self):
        return self.__add_remove

    def _set_add_remove(self, value):
        add_remove_validate(value)
        self.__add_remove = value

    add_remove = property(_get_add_remove, _set_add_remove)

    def get(self, cursor, user, ids, model, name, values=None, context=None):
        '''
        Return target records ordered.

        :param cursor: the database cursor
        :param user: the user id
        :param ids: a list of ids
        :param model: a string with the name of the model
        :param name: a string with the name of the field
        :param values: a dictionary with the read values
        :param context: the context
        :return: a dictionary with ids as key and values as value
        '''
        if context is None:
            context = {}

        res = {}
        for i in ids:
            res[i] = []
        ids2 = []
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            ids2.append(model.pool.get(self.model_name).search(cursor, user,
                    [(self.field, 'in', sub_ids)], order=self.order,
                    context=context))

        cache = cursor.get_cache(context)
        cache.setdefault(self.model_name, {})
        ids3 = []
        for i in chain(*ids2):
            if i in cache[self.model_name] \
                    and self.field in cache[self.model_name][i]:
                res[cache[self.model_name][i][self.field].id].append(i)
            else:
                ids3.append(i)

        if ids3:
            for i in model.pool.get(self.model_name).read(cursor, user, ids3,
                    [self.field], context=context):
                res[i[self.field]].append(i['id'])

        index_of_ids2 = dict((i, index) for index, i in enumerate(chain(*ids2)))
        for val in res.values():
            val.sort(lambda x, y: cmp(index_of_ids2[x], index_of_ids2[y]))
        return res

    def set(self, cursor, user, ids, model, name, values, context=None):
        '''
        Set the values.

        :param cursor: The database cursor
        :param user: The user id
        :param ids: A list of ids
        :param model: A string with the name of the model
        :param name: A string with the name of the field
        :param values: A list of tuples:
            (``create``, ``{<field name>: value}``),
            (``write``, ``<ids>``, ``{<field name>: value}``),
            (``delete``, ``<ids>``),
            (``delete_all``),
            (``unlink``, ``<ids>``),
            (``add``, ``<ids>``),
            (``unlink_all``),
            (``set``, ``<ids>``)
        :param context: The context
        '''
        if not values:
            return
        model = model.pool.get(self.model_name)
        for act in values:
            if act[0] == 'create':
                for record_id in ids:
                    act[1][self.field] = record_id
                    model.create(cursor, user, act[1], context=context)
            elif act[0] == 'write':
                model.write(cursor, user, act[1] , act[2], context=context)
            elif act[0] == 'delete':
                model.delete(cursor, user, act[1], context=context)
            elif act[0] == 'delete_all':
                target_ids = model.search(cursor, user, [
                    (self.field, 'in', ids),
                    ], context=context)
                model.delete(cursor, user, target_ids, context=context)
            elif act[0] == 'unlink':
                if isinstance(act[1], (int, long)):
                    target_ids = [act[1]]
                else:
                    target_ids = list(act[1])
                if not target_ids:
                    continue
                target_ids = model.search(cursor, user, [
                    (self.field, 'in', ids),
                    ('id', 'in', target_ids),
                    ], context=context)
                model.write(cursor, user, target_ids, {
                    self.field: False,
                    }, context=context)
            elif act[0] == 'add':
                if isinstance(act[1], (int, long)):
                    target_ids = [act[1]]
                else:
                    target_ids = list(act[1])
                if not target_ids:
                    continue
                for record_id in ids:
                    model.write(cursor, user, target_ids, {
                        self.field: record_id,
                        }, context=context)
            elif act[0] == 'unlink_all':
                target_ids = model.search(cursor, user, [
                    (self.field, 'in', ids),
                    ], context=context)
                model.write(cursor, user, target_ids, {
                    self.field: False,
                    }, context=context)
            elif act[0] == 'set':
                if not act[1]:
                    target_ids = [0]
                else:
                    target_ids = list(act[1])
                for record_id in ids:
                    target_ids2 = model.search(cursor, user, [
                        (self.field, '=', record_id),
                        ('id', 'not in', target_ids),
                        ], context=context)
                    model.write(cursor, user, target_ids2, {
                        self.field: False,
                        }, context=context)
                    if act[1]:
                        model.write(cursor, user, target_ids, {
                            self.field: record_id,
                            }, context=context)
            else:
                raise Exception('Bad arguments')
