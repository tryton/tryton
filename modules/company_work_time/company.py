# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    hours_per_work_day = fields.Float("Hours per Work Day", required=True)
    hours_per_work_week = fields.Float("Hours per Work Week", required=True)
    hours_per_work_month = fields.Float("Hours per Work Month", required=True)
    hours_per_work_year = fields.Float("Hours per Work Year", required=True)

    @staticmethod
    def default_hours_per_work_day():
        return 8

    @staticmethod
    def default_hours_per_work_week():
        return 40

    @staticmethod
    def default_hours_per_work_month():
        return 160

    @staticmethod
    def default_hours_per_work_year():
        return 1920

    @classmethod
    def write(cls, *args):
        pool = Pool()
        User = pool.get('res.user')
        super(Company, cls).write(*args)
        User._get_preferences_cache.clear()
