#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Company"
from trytond.model import ModelView, ModelSQL, fields


class Company(ModelSQL, ModelView):
    _name = 'company.company'

    hours_per_work_day = fields.Float("Hours per Work Day", required=True)
    hours_per_work_week = fields.Float("Hours per Work Week", required=True)
    hours_per_work_month = fields.Float("Hours per Work Month", required=True)
    hours_per_work_year = fields.Float("Hours per Work Year", required=True)

    def default_hours_per_work_day(self, cursor, user, context=None):
        return 8

    def default_hours_per_work_week(self, cursor, user, context=None):
        return 40

    def default_hours_per_work_month(self, cursor, user, context=None):
        return 160

    def default_hours_per_work_year(self, cursor, user, context=None):
        return 1920

Company()
