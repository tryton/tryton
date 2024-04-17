# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta


class Rule(metaclass=PoolMeta):
    __name__ = 'ir.rule'

    @classmethod
    def _get_context(cls, model_name):
        pool = Pool()
        User = pool.get('res.user')
        context = super()._get_context(model_name)
        if model_name == 'purchase.requisition':
            context['employees'] = User.get_employees()
        return context

    @classmethod
    def _get_cache_key(cls, model_names):
        pool = Pool()
        User = pool.get('res.user')
        key = super()._get_cache_key(model_names)
        if 'purchase.requisition' in model_names:
            key = (*key, User.get_employees())
        return key
