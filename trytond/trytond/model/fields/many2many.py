#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.field import Field
from itertools import chain


class Many2Many(Field):
    '''
    Define many2many field (``list``).
    '''
    _type = 'many2many'

    def __init__(self, relation_name, origin, target, string='', order=None,
            datetime_field=None, help='', required=False, readonly=False,
            domain=None, states=None, priority=0, change_default=False,
            select=0, on_change=None, on_change_with=None, depends=None,
            order_field=None, context=None):
        '''
        :param relation_name: The name of the relation model
            or the name of the target model for ModelView only.
        :param origin: The name of the field to store origin ids.
        :param target: The name of the field to store target ids.
        :param order:  a list of tuples that are constructed like this:
            ``('field name', 'DESC|ASC')``
            allowing to specify the order of result
        :param datetime_field: The name of the field that contains the datetime
            value to read the target records.
        '''
        if datetime_field:
            if depends:
                depends.append(datetime_field)
            else:
                depends = [datetime_field]
        super(Many2Many, self).__init__(string=string, help=help,
                required=required, readonly=readonly, domain=domain,
                states=states, priority=priority,
                change_default=change_default, select=select,
                on_change=on_change, on_change_with=on_change_with,
                depends=depends, order_field=order_field, context=context)
        self.relation_name = relation_name
        self.origin = origin
        self.target = target
        self.order = order
        self.datetime_field = datetime_field
    __init__.__doc__ += Field.__init__.__doc__

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
        if values is None:
            values = {}
        res = {}
        if not ids:
            return res
        for i in ids:
            res[i] = []

        relation_obj = model.pool.get(self.relation_name)

        relation_ids = []
        for i in range(0, len(ids), cursor.IN_MAX):
            sub_ids = ids[i:i + cursor.IN_MAX]
            relation_ids.append(relation_obj.search(cursor, user, [
                (self.origin, 'in', sub_ids),
                (self.target + '.id', '!=', False),
                ], order=self.order, context=context))
        relation_ids = list(chain(*relation_ids))

        for relation in relation_obj.read(cursor, user, relation_ids,
                [self.origin, self.target], context=context):
            res[relation[self.origin]].append(relation[self.target])
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
            (``unlink``, ``<ids>``),
            (``add``, ``<ids>``),
            (``unlink_all``),
            (``set``, ``<ids>``)
        :param context: The context
        '''
        if not values:
            return
        relation_obj = model.pool.get(self.relation_name)
        target_obj = self.get_target(model.pool)
        for act in values:
            if act[0] == 'create':
                for record_id in ids:
                    relation_obj.create(cursor, user, {
                        self.origin: record_id,
                        self.target: target_obj.create(cursor, user, act[1],
                            context=context),
                        }, context=context)
            elif act[0] == 'write':
                target_obj.write(cursor, user, act[1] , act[2], context=context)
            elif act[0] == 'delete':
                target_obj.delete(cursor, user, act[1], context=context)
            elif act[0] == 'unlink':
                if isinstance(act[1], (int, long)):
                    target_ids = [act[1]]
                else:
                    target_ids = list(act[1])
                if not target_ids:
                    continue
                relation_ids = []
                for i in range(0, len(target_ids), cursor.IN_MAX):
                    sub_ids = target_ids[i:i + cursor.IN_MAX]
                    relation_ids += relation_obj.search(cursor, user, [
                        (self.origin, 'in', ids),
                        (self.target, 'in', sub_ids),
                        ], context=context)
                relation_obj.delete(cursor, user, relation_ids, context=context)
            elif act[0] == 'add':
                if isinstance(act[1], (int, long)):
                    target_ids = [act[1]]
                else:
                    target_ids = list(act[1])
                if not target_ids:
                    continue
                existing_ids = []
                for i in range(0, len(target_ids), cursor.IN_MAX):
                    sub_ids = target_ids[i:i + cursor.IN_MAX]
                    relation_ids = relation_obj.search(cursor, user, [
                        (self.origin, 'in', ids),
                        (self.target, 'in', sub_ids),
                        ], context=context)
                    for relation in relation_obj.browse(cursor, user,
                            relation_ids, context=context):
                        existing_ids.append(relation[self.target].id)
                for new_id in (x for x in target_ids if x not in existing_ids):
                    for record_id in ids:
                        relation_obj.create(cursor, user, {
                            self.origin: record_id,
                            self.target: new_id,
                            }, context=context)
            elif act[0] == 'unlink_all':
                target_ids = relation_obj.search(cursor, user, [
                    (self.origin, 'in', ids),
                    (self.target + '.id', '!=', False),
                    ], context=context)
                relation_obj.delete(cursor, user, target_ids, context=context)
            elif act[0] == 'set':
                if not act[1]:
                    target_ids = []
                else:
                    target_ids = list(act[1])
                target_ids2 = relation_obj.search(cursor, user, [
                    (self.origin, 'in', ids),
                    (self.target + '.id', '!=', False),
                    ], context=context)
                relation_obj.delete(cursor, user, target_ids2, context=context)

                for new_id in target_ids:
                    for record_id in ids:
                        relation_obj.create(cursor, user, {
                            self.origin: record_id,
                            self.target: new_id,
                            }, context=context)
            else:
                raise Exception('Bad arguments')

    def get_target(self, pool):
        '''
        Return the target model.

        :param pool: The pool
        :return: A Model
        '''
        relation_obj = pool.get(self.relation_name)
        if not self.target:
            return relation_obj
        if self.target in relation_obj._columns:
            target_obj = pool.get(
                    relation_obj._columns[self.target].model_name)
        else:
            target_obj = pool.get(
                    relation_obj._inherit_fields[self.target][2].model_name)
        return target_obj
