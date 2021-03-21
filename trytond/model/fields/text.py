# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Query, Expression, Null, Literal
from sql.operators import ILike, Not, In, NotIn

from trytond.transaction import Transaction

from .field import Field, SQL_OPERATORS
from .char import Char


class Text(Char):
    '''
    Define a text field (``unicode``).
    '''
    _type = 'text'
    _sql_type = 'TEXT'
    forbidden_chars = ''
    search_full_text = True


class FullText(Field):
    '''
    Define a full text field.
    '''
    _type = 'full_text'
    _sql_type = 'FULLTEXT'
    _py_type = str

    def sql_format(self, value):
        if isinstance(value, (Query, Expression)):
            return value
        if not value:
            return Null
        if isinstance(value, (int, float)):
            return value
        transaction = Transaction()
        database = transaction.database
        if isinstance(value, str):
            value = [value]
        return database.format_full_text(*value, language=transaction.language)

    def _rank_column(self, column, name, Model):
        transaction = Transaction()
        context = transaction.context
        database = transaction.database
        key = '%s.%s.order' % (Model.__name__, name)
        value = context.get(key)
        if value and database.has_search_full_text():
            value = database.format_full_text_query(
                value, language=transaction.language)
            column = database.rank_full_text(column, value, normalize=['rank'])
        else:
            column = Null
        return column

    def convert_domain(self, domain, tables, Model):
        transaction = Transaction()
        database = transaction.database
        table, _ = tables[None]
        name, operator, value = domain
        assert name == self.name
        column = self.sql_column(table)
        column = self._domain_column(operator, column)
        if operator.endswith('like'):
            if database.has_search_full_text():
                value = database.format_full_text_query(
                    value, language=transaction.language)
                expression = database.search_full_text(column, value)
            else:
                expression = Literal(True)
                for v in value.split():
                    expression &= ILike(column, '%' + v + '%')
            if operator.startswith('not'):
                expression = Not(expression)
        else:
            Operator = SQL_OPERATORS[operator]
            column = self._rank_column(column, name, Model)
            expression = Operator(column, self._domain_value(operator, value))
            if isinstance(expression, In) and not expression.right:
                expression = Literal(False)
            elif isinstance(expression, NotIn) and not expression.right:
                expression = Literal(True)
            expression = self._domain_add_null(
                column, operator, value, expression)
        return expression

    def convert_order(self, name, tables, Model):
        method = getattr(Model, 'order_%s' % name, None)
        if method:
            return method(tables)
        table, _ = tables[None]
        column = self.sql_column(table)
        column = self._domain_column('ilike', column)
        return [self._rank_column(column, name, Model)]
