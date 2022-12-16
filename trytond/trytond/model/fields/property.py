#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.model.fields.function import Function
from trytond.model.fields.field import Field
from trytond import backend


class Property(Function):
    '''
    Define a property field that is stored in ir.property (any).
    '''

    def __init__(self, type='float', model_name=None, selection=None,
            digits=None, relation=None, add_remove=None, string='', help='',
            required=False, readonly=False, domain=None, states=None, priority=0,
            change_default=False, translate=False, select=0, on_change=None,
            on_change_with=None, depends=None, order_field=None, context=None):
        '''
        :param type: The type of the field.
        :param fnct_search: The name of the search function.
        :param model_name: See Many2One.
        :param selection: See Selection.
        :param digits: See Float.
        :param relation: Like model_name.
        :param add_remove: See Many2One.
        '''
        super(Property, self).__init__('', type=type, model_name=model_name,
                selection=selection, digits=digits, relation=relation,
                add_remove=add_remove, string=string, help=help,
                required=required, readonly=readonly, domain=domain,
                states=states, priority=priority, change_default=change_default,
                translate=translate, select=select, on_change=on_change,
                on_change_with=on_change_with, depends=depends,
                order_field=order_field, context=context)
        self.readonly = False
    __init__.__doc__ += Field.__init__.__doc__

    def get(self, cursor, user, ids, model, name, values=None, context=None):
        '''
        Retreive the property.

        :param cursor: The database cursor.
        :param user: The user id.
        :param ids: A list of ids.
        :param model: The model.
        :param name: The name of the field or a list of name field.
        :param values:
        :param context: The contest.
        :return: a dictionary with ids as key and values as value
        '''
        property_obj = model.pool.get('ir.property')
        res = property_obj.get(cursor, user, name, model._name, ids,
                context=context)
        return res


    def set(self, cursor, user, record_id, model, name, value, context=None):
        '''
        Set the property.

        :param cursor: The database cursor.
        :param user: The user id.
        :param record_id: The record id.
        :param model: The model.
        :param name: The name of the field.
        :param value: The value to set.
        :param context: The context.
        '''
        property_obj = model.pool.get('ir.property')
        return property_obj.set(cursor, user, name, model._name, record_id,
                (value and (self.model_name or '')  + ',' + str(value)) or False,
                context=context)


    def search(self, cursor, user, model, name, args, context=None):
        '''
        :param cursor: The database cursor.
        :param user: The user id.
        :param model: The model.
        :param args: The search domain. See ModelStorage.search
        :param context: The context.
        :return: New list of domain.
        '''
        rule_obj = model.pool.get('ir.rule')
        property_obj = model.pool.get('ir.property')
        model_obj = model.pool.get('ir.model')
        field_obj = model.pool.get('ir.model.field')

        field_class = backend.FIELDS[self._type]
        if not field_class:
            return []
        sql_type = field_class.sql_type(model._columns[name])
        if not sql_type:
            return []
        sql_type = sql_type[0]


        conditions = "AND ".join(
            self.get_condition(sql_type, arg) for arg in args)
        cond_args = self.get_condition_args(args)


        property_query, property_val = rule_obj.domain_get(
            cursor, user, 'ir.property', context=context)

        #Fetch res ids that comply with the domain
        cursor.execute(
            'SELECT cast(split_part("' + property_obj._table + '".res,\',\',2) as integer), ' + \
                '"' + property_obj._table + '".id '\
            'FROM "' + property_obj._table + '" '\
                'JOIN "' + field_obj._table + '" on ("' + field_obj._table + '"'+ \
                      '.id = "' + property_obj._table + '".field) '\
                'JOIN "' + model_obj._table +'" on ("' + model_obj._table + \
                      '".id = "' + field_obj._table + '".model) '\
            'WHERE '\
              'CASE WHEN "' +\
                model_obj._table + '".model = %s AND "' + field_obj._table + '".name = %s AND ' \
                + property_query + \
              ' THEN '  + \
                conditions + \
              ' ELSE '\
                '%s '\
              'END',
            [model._name, name] + property_val + cond_args + [False])

        props = cursor.fetchall()
        default = None
        for x in props:
            if not x[0]:
                default = x[1]
                break

        if not default:
            return [('id', 'in', [x[0] for x in props])]

        #Fetch the res ids that doesn't use the default value
        cursor.execute(
            "SELECT cast(split_part(res,',',2) as integer) "\
            'FROM "' + property_obj._table +'"'\
            'WHERE ' \
              + property_query + ' AND res is not null',
            property_val)

        fetchall = cursor.fetchall()
        if not fetchall:
            return [('id', 'in', [x[0] for x in props])]

        else:
            other_ids = [x[0] for x in cursor.fetchall()]

            res_ids = model.search(
                cursor, user,
                ['OR', ('id', 'in', [x[0] for x in props]),
                 ('id', 'not in', other_ids)],
                context=context)

            return [('id', 'in', res_ids)]

    @staticmethod
    def get_condition(sql_type, arg):
        if arg[1] in ('in', 'not in'):
            return ("(cast(split_part(value,',',2) as %s) %s ("+ \
                ",".join(('%%s',) * len(arg[2])) + ")) ") % (sql_type, arg[1])
        else:
            return "(cast(split_part(value,',',2) as %s) %s %%s) " % \
                (sql_type, arg[1])

    @staticmethod
    def get_condition_args(args):
        res = []
        for arg in args:
            if arg[1] in ('in', 'not in'):
                res.extend(arg[2])
            else:
                res.append(arg[2])
        return res


