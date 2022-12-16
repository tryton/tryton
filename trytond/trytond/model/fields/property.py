#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import copy
from trytond.model.fields.function import Function
from trytond.model.fields.field import Field
from trytond import backend


class Property(Function):
    '''
    Define a property field that is stored in ir.property (any).
    '''

    def __init__(self, field):
        '''
        :param field: The field of the function.
        '''
        super(Property, self).__init__(field, True, True, True)

    __init__.__doc__ += Field.__init__.__doc__

    def __copy__(self):
        return Property(copy.copy(self._field))

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


    def set(self, cursor, user, ids, model, name, value, context=None):
        '''
        Set the property.

        :param cursor: The database cursor.
        :param user: The user id.
        :param ids: A list of ids.
        :param model: The model.
        :param name: The name of the field.
        :param value: The value to set.
        :param context: The context.
        '''
        property_obj = model.pool.get('ir.property')
        return property_obj.set(cursor, user, name, model._name, ids,
                (value and getattr(self, 'model_name', '')  + ',' + str(value)) or
                False, context=context)


    def search(self, cursor, user, model, name, clause, context=None):
        '''
        :param cursor: The database cursor.
        :param user: The user id.
        :param model: The model.
        :param clause: The search domain clause. See ModelStorage.search
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

        property_query, property_val = rule_obj.domain_get(
            cursor, user, 'ir.property', context=context)

        #Fetch res ids that comply with the domain
        cursor.execute(
            'SELECT CAST(' \
                    'SPLIT_PART("' + property_obj._table + '".res,\',\',2) ' \
                    'AS INTEGER), '\
                '"' + property_obj._table + '".id '\
            'FROM "' + property_obj._table + '" '\
                'JOIN "' + field_obj._table + '" ON ' \
                    '("' + field_obj._table + '"'+ \
                        '.id = "' + property_obj._table + '".field) '\
                'JOIN "' + model_obj._table +'" ON ' \
                    '("' + model_obj._table + \
                        '".id = "' + field_obj._table + '".model) '\
            'WHERE '\
              'CASE WHEN "' +\
                model_obj._table + '".model = %s ' \
                'AND "' + field_obj._table + '".name = %s AND ' \
                + property_query + \
              ' THEN '  + \
                self.get_condition(sql_type, clause) + \
              ' ELSE '\
                '%s '\
              'END',
            [model._name, name] + property_val + \
                    self.get_condition_args(clause) + [False])

        props = cursor.fetchall()
        default = None
        for prop in props:
            if not prop[0]:
                default = prop[1]
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
    def get_condition(sql_type, clause):
        if clause[1] in ('in', 'not in'):
            return ("(cast(split_part(value,',',2) as %s) %s ("+ \
                ",".join(('%%s',) * len(clause[2])) + ")) ") % \
                (sql_type, clause[1])
        else:
            return "(cast(split_part(value,',',2) as %s) %s %%s) " % \
                (sql_type, clause[1])

    @staticmethod
    def get_condition_args(clause):
        res = []
        if clause[1] in ('in', 'not in'):
            res.extend(clause[2])
        else:
            res.append(clause[2])
        return res


