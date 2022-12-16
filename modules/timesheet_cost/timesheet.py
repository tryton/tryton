#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['TimesheetLine']
__metaclass__ = PoolMeta


class TimesheetLine:
    __name__ = 'timesheet.line'

    def compute_cost(self):
        Currency = Pool().get('currency.currency')

        cost_price = self.employee.compute_cost_price(date=self.date)

        line_company = self.employee.company
        work_company = self.work.company
        if (line_company != work_company and
                line_company.currency != work_company.currency):
            with Transaction().set_context(date=self.date):
                cost_price = Currency.compute(line_company.currency,
                    cost_price, work_company.currency)

        return Decimal(str(self.hours)) * cost_price
