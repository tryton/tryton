# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta

_EMPLOYEES_RULE_MODELS = {
    'timesheet.line',
    'timesheet.hours_employee',
    'timesheet.hours_employee_weekly',
    'timesheet.hours_employee_monthly',
    }


class Rule(metaclass=PoolMeta):
    __name__ = 'ir.rule'

    @classmethod
    def _get_context(cls, model_name):
        pool = Pool()
        User = pool.get('res.user')
        context = super()._get_context(model_name)
        if model_name in _EMPLOYEES_RULE_MODELS:
            context['employees'] = User.get_employees()
        return context

    @classmethod
    def _get_cache_key(cls, model_name):
        pool = Pool()
        User = pool.get('res.user')
        key = super()._get_cache_key(model_name)
        if model_name in _EMPLOYEES_RULE_MODELS:
            key = (*key, User.get_employees())
        return key
