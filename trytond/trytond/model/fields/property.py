#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import copy
from sql import Cast, Literal
from sql.functions import Substring, Position
from sql.conditionals import Case

from .function import Function
from .field import Field, SQL_OPERATORS
from .numeric import Numeric
from ...transaction import Transaction
from ...pool import Pool


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
        with Transaction().set_context(_check_access=False):
            pool = Pool()
            Property = pool.get('ir.property')
            return Property.get(name, model.__name__, ids)

    def set(self, Model, name, ids, value, *args):
        '''
        Set the property.
        '''
        with Transaction().set_context(_check_access=False):
            pool = Pool()
            Property = pool.get('ir.property')
            args = iter((ids, value) + args)
            for ids, value in zip(args, args):
                if value is not None:
                    prop_value = '%s,%s' % (getattr(self, 'model_name', ''),
                        str(value))
                else:
                    prop_value = None
                # TODO change set API to use sequence of records, value
                Property.set(name, Model.__name__, ids, prop_value)

    def convert_domain(self, domain, tables, Model):
        pool = Pool()
        Rule = pool.get('ir.rule')
        Property = pool.get('ir.property')
        IrModel = pool.get('ir.model')
        Field = pool.get('ir.model.field')
        cursor = Transaction().cursor

        name, operator, value = domain

        sql_type = self._field.sql_type().base

        property_cond = Rule.domain_get('ir.property')

        property_ = Property.__table__()
        model_field = Field.__table__()
        model = IrModel.__table__()

        #Fetch res ids that comply with the domain
        join = property_.join(model_field,
            condition=model_field.id == property_.field)
        join = join.join(model,
            condition=model.id == model_field.model)
        cond = ((model.model == Model.__name__)
            & (model_field.name == name))
        if property_cond:
            cond &= property_.id.in_(property_cond)
        cursor.execute(*join.select(
                Cast(Substring(property_.res,
                        Position(',', property_.res) + Literal(1)),
                    Model.id.sql_type().base),
                property_.id,
                where=Case((cond, self.get_condition(sql_type, domain,
                            property_)),
                    else_=False)))

        props = cursor.fetchall()
        default = None
        for prop in props:
            if not prop[0]:
                default = prop[1]
                break

        if (not default
                or ((value is False or value is None)
                    and operator in ['=', '!='])
                or (operator in ['not like', 'not ilike', 'not in', '!='])):
            dom_operator = 'in'  # default operator
            if (((value is False or value is None) and operator == '=')
                    or ((value is not False and value is not None)
                        and operator in [
                            'not like', 'not ilike', 'not in', '!='])):
                dom_operator = 'not in'
            return [('id', dom_operator, [x[0] for x in props])]

        #Fetch the res ids that doesn't use the default value
        cursor.execute(*property_.select(
                Cast(Substring(property_.res,
                        Position(',', property_.res) + Literal(1)),
                    Model.id.sql_type().base),
                where=property_cond & (property_.res != None)))

        fetchall = cursor.fetchall()
        if not fetchall:
            return [('id', 'in', [x[0] for x in props])]

        else:
            other_ids = [x[0] for x in cursor.fetchall()]

            res_ids = Model.search(['OR',
                ('id', 'in', [x[0] for x in props]),
                ('id', 'not in', other_ids)
                ])

            return [('id', 'in', res_ids)]

    @staticmethod
    def get_condition(sql_type, clause, table):
        operator = clause[1]
        value = clause[2]

        numeric = Numeric('numeric')
        if sql_type == numeric.sql_type().base and value:
            if isinstance(value, (list, tuple)):
                value = [Cast(v, sql_type) for v in value]
            else:
                value = Cast(value, sql_type)

        if value is None:
            value = False

        column = Cast(Substring(table.value,
                Position(',', table.value) + Literal(1)),
            sql_type)
        Operator = SQL_OPERATORS[operator]

        # All negative clauses will be negated later
        if operator in ('in', 'not in'):
            return column.in_(value)
        elif ((value is False or value is None)
                and operator in ('=', '!=')):
            return (column == None) == value
        elif operator == 'not like':
            return column.like(value)
        elif operator == 'not ilike':
            return column.ilike(value)
        elif operator == '!=':
            return column == value
        return Operator(column, value)
