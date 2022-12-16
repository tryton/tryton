#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL


class User(ModelSQL, ModelView):
    _name = 'res.user'

    def _get_preferences(self, cursor, user_id, user, context_only=False,
            context=None):
        res = super(User, self)._get_preferences(cursor, user_id, user,
                context_only=context_only, context=context)
        if user.company:
            res['company_work_time'] = {
                'Y': user.company.hours_per_work_year,
                'M': user.company.hours_per_work_month,
                'w': user.company.hours_per_work_week,
                'd': user.company.hours_per_work_day,
            }
        return res

User()
