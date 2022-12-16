#This file is part of Tryton.  The COPYRIGHT file at the top level
#of this repository contains the full copyright notices and license terms.

from trytond.osv import OSV, fields
import datetime


class Date(OSV):
    'Date'
    _name = 'ir.date'
    _description = __doc__

    def today(self, cursor, user, context=None):
        '''
        Current date

        :param cursor: the database cursor
        :param user: the user id
        :param context: the context
        :return: a current datetime.date
        '''
        return datetime.date.today()

Date()
