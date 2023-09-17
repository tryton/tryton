# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
import functools

from trytond.model import MultiValueMixin, ValueMixin, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

__all__ = ['CompanyMultiValueMixin', 'CompanyValueMixin',
    'set_employee', 'reset_employee', 'employee_field']


class CompanyMultiValueMixin(MultiValueMixin):
    __slots__ = ()

    def multivalue_records(self, field):
        Value = self.multivalue_model(field)
        records = super(CompanyMultiValueMixin, self).multivalue_records(field)
        if issubclass(Value, CompanyValueMixin):
            # Sort to get record with empty company at the end
            # and so give priority to record with company filled.
            records = sorted(records, key=lambda r: r.company is None)
        return records

    def get_multivalue(self, name, **pattern):
        Value = self.multivalue_model(name)
        if issubclass(Value, CompanyValueMixin):
            pattern.setdefault('company', Transaction().context.get('company'))
        return super(CompanyMultiValueMixin, self).get_multivalue(
            name, **pattern)

    def set_multivalue(self, name, value, save=True, **pattern):
        Value = self.multivalue_model(name)
        if issubclass(Value, CompanyValueMixin):
            pattern.setdefault('company', Transaction().context.get('company'))
        return super(CompanyMultiValueMixin, self).set_multivalue(
            name, value, save=save, **pattern)


class CompanyValueMixin(ValueMixin):
    __slots__ = ()
    company = fields.Many2One('company.company', "Company", ondelete='CASCADE')


def employee_field(string, states=None, company='company'):
    if states is None:
        states = ['done', 'cancel', 'cancelled']
    return fields.Many2One(
        'company.employee', string,
        domain=[('company', '=', Eval(company, -1))],
        states={
            'readonly': Eval('state').in_(states),
            })


def set_employee(field, company='company', when='after'):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(cls, records, *args, **kwargs):
            pool = Pool()
            User = pool.get('res.user')
            user = User(Transaction().user)

            if when == 'after':
                result = func(cls, records, *args, **kwargs)
            employee = user.employee
            if employee:
                emp_company = employee.company
                cls.write(
                    [r for r in records
                        if not getattr(r, field)
                        and getattr(r, company) == emp_company], {
                        field: employee.id,
                        })
            if when == 'before':
                result = func(cls, records, *args, **kwargs)
            return result
        return wrapper
    assert when in {'before', 'after'}
    return decorator


def reset_employee(*fields, when='after'):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(cls, records, *args, **kwargs):
            if when == 'after':
                result = func(cls, records, *args, **kwargs)
            cls.write(records, {f: None for f in fields})
            if when == 'before':
                result = func(cls, records, *args, **kwargs)
            return result
        return wrapper
    assert when in {'before', 'after'}
    return decorator
