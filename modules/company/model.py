# This file is part of Tryton.  The COPYRIGHT file at the toplevel of this
# repository contains the full copyright notices and license terms.
from trytond.model import MultiValueMixin, ValueMixin, fields
from trytond.transaction import Transaction

__all__ = ['CompanyMultiValueMixin', 'CompanyValueMixin']


class CompanyMultiValueMixin(MultiValueMixin):

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

    def set_multivalue(self, name, value, **pattern):
        Value = self.multivalue_model(name)
        if issubclass(Value, CompanyValueMixin):
            pattern.setdefault('company', Transaction().context.get('company'))
        return super(CompanyMultiValueMixin, self).set_multivalue(
            name, value, **pattern)


class CompanyValueMixin(ValueMixin):
    company = fields.Many2One(
        'company.company', "Company", select=True, ondelete='CASCADE')
