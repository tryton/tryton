# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta


class User(metaclass=PoolMeta):
    __name__ = 'res.user'

    @classmethod
    def _get_preferences(cls, user, context_only=False):
        res = super(User, cls)._get_preferences(user,
            context_only=context_only)
        if user.company:
            time = {
                'h': 60 * 60,
                'm': 60,
                's': 1,
                }
            for k, v in [
                    ('Y', user.company.hours_per_work_year),
                    ('M', user.company.hours_per_work_month),
                    ('w', user.company.hours_per_work_week),
                    ('d', user.company.hours_per_work_day)]:
                if v:
                    time[k] = v * 60 * 60
            res['company_work_time'] = time
        return res
