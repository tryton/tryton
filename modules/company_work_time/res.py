#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL


class User(ModelSQL, ModelView):
    _name = 'res.user'

    def _get_preferences(self, user, context_only=False):
        res = super(User, self)._get_preferences(user,
            context_only=context_only)
        if user.company:
            res['company_work_time'] = {
                'Y': user.company.hours_per_work_year,
                'M': user.company.hours_per_work_month,
                'w': user.company.hours_per_work_week,
                'd': user.company.hours_per_work_day,
            }
        return res

User()
