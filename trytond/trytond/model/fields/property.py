#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import copy
from trytond.model.fields.function import Function
from trytond.model.fields.field import Field
from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import Pool


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

    def __deepcopy__(self, memo):
        return Property(copy.deepcopy(self._field))

    def get(self, ids, model, name, values=None):
        '''
        Retreive the property.

        :param ids: A list of ids.
        :param model: The model.
        :param name: The name of the field or a list of name field.
        :param values:
        :return: a dictionary with ids as key and values as value
        '''
        pool = Pool()
        Property = pool.get('ir.property')
        return Property.get(name, model.__name__, ids)

    def set(self, ids, model, name, value):
        '''
        Set the property.

        :param ids: A list of ids.
        :param model: The model.
        :param name: The name of the field.
        :param value: The value to set.
        '''
        pool = Pool()
        Property = pool.get('ir.property')
        if value is not None:
            prop_value = '%s,%s' % (getattr(self, 'model_name', ''),
                str(value))
        else:
            prop_value = None
        Property.set(name, model.__name__, ids, prop_value)

    def search(self, model, name, clause):
        '''
        :param model: The model.
        :param clause: The search domain clause. See ModelStorage.search
        :return: New list of domain.
        '''
        pool = Pool()
        Rule = pool.get('ir.rule')
        Property = pool.get('ir.property')
        Model = pool.get('ir.model')
        Field = pool.get('ir.model.field')
        cursor = Transaction().cursor

        field_class = backend.FIELDS[self._type]
        if not field_class:
            return []
        sql_type = field_class.sql_type(model._fields[name])
        if not sql_type:
            return []
        sql_type = sql_type[0]

        property_query, property_val = Rule.domain_get('ir.property')

        property_clause = ''
        if property_query:
            property_clause = 'AND ' + property_query

        #Fetch res ids that comply with the domain
        cursor.execute(
            'SELECT CAST('
                'SPLIT_PART("' + Property._table + '".res,\',\',2) '
                    'AS INTEGER), '
                '"' + Property._table + '".id '
            'FROM "' + Property._table + '" '
                'JOIN "' + Field._table + '" ON '
                    '("' + Field._table + '"' +
                        '.id = "' + Property._table + '".field) '
                'JOIN "' + Model._table + '" ON '
                    '("' + Model._table +
                        '".id = "' + Field._table + '".model) '
            'WHERE '
                'CASE WHEN "' +
                    Model._table + '".model = %s '
                    'AND "' + Field._table + '".name = %s '
                    + property_clause +
                ' THEN ' +
                    self.get_condition(sql_type, clause) +
                ' ELSE '
                    '%s '
                'END',
            [model.__name__, name] + property_val +
            self.get_condition_args(clause) + [False])

        props = cursor.fetchall()
        default = None
        for prop in props:
            if not prop[0]:
                default = prop[1]
                break

        if not default \
                or ((clause[2] is False or clause[2] is None)
                    and clause[1] in ['=', '!=']) \
                or (clause[1] in ['not like', 'not ilike', 'not in', '!=']):
            operator = 'in'  # default operator
            if (((clause[2] is False or clause[2] is None)
                        and clause[1] == '=')
                    or ((clause[2] is not False and clause[2] is not None)
                        and clause[1] in [
                            'not like', 'not ilike', 'not in', '!='])):
                operator = 'not in'
            return [('id', operator, [x[0] for x in props])]

        #Fetch the res ids that doesn't use the default value
        cursor.execute(
            "SELECT cast(split_part(res,',',2) as integer) "
            'FROM "' + Property._table + '"'
            'WHERE ' + property_query + ' AND res is not null',
            property_val)

        fetchall = cursor.fetchall()
        if not fetchall:
            return [('id', 'in', [x[0] for x in props])]

        else:
            other_ids = [x[0] for x in cursor.fetchall()]

            res_ids = model.search(['OR',
                ('id', 'in', [x[0] for x in props]),
                ('id', 'not in', other_ids)
                ])

            return [('id', 'in', res_ids)]

    @staticmethod
    def get_condition(sql_type, clause):
        operator = '%s'
        if sql_type == 'NUMERIC':
            operator = 'CAST(%s AS NUMERIC)'

        # All negative clauses will be negated later
        if clause[1] in ('in', 'not in'):
            operator = operator % '%%s'
            return ("(CAST(SPLIT_PART(value,',',2) AS %s) IN ("
                + ",".join((operator,) * len(clause[2])) + ")) ") % sql_type
        elif ((clause[2] is False or clause[2] is None)
                and clause[1] in ['=', '!=']):
            return "((cast(split_part(value,',',2) as %s) IS NULL " \
                ") = %%s) " % sql_type
        elif clause[1] in ['not like', 'not ilike']:
            return "(cast(split_part(value,',',2) as %s) %s %s) " % \
                (sql_type, clause[1].split()[1], operator)
        elif clause[1] == '!=':
            return "(cast(split_part(value,',',2) as %s) = %s) " % \
                (sql_type, operator)
        else:
            return "(cast(split_part(value,',',2) as %s) %s %s) " % \
                (sql_type, clause[1], operator)

    @staticmethod
    def get_condition_args(clause):
        res = []
        if clause[1] in ('in', 'not in'):
            res.extend(clause[2])
        elif clause[2] is None:
            res.append(False)
        else:
            res.append(clause[2])
        return res
