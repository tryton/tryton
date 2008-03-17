'Period'

from trytond.osv import fields, OSV, ExceptORM
import datetime
_STATES = {
    'readonly': "state == 'close'",
}


class Period(OSV):
    'Period'
    _name = 'account.period'
    _description = __doc__
    _order = 'start_date'

    name = fields.Char('Name', size=None, required=True)
    code = fields.Char('Code', size=None)
    start_date = fields.Date('Starting Date', required=True, states=_STATES)
    end_date = fields.Date('Ending Date', required=True, states=_STATES)
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True, states=_STATES)
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close'),
        ], 'State', readonly=True, required=True)

    def default_state(self, cursor, user, context=None):
        return 'open'

    def find(self, cursor, user, date=None, exception=True, context=None):
        '''
        Return the period for the date or the current date.
        If exception is set the function will raise an exception
            if any period is found.
        '''
        if not date:
            date = datetime.date.today()
        ids = self.search(cursor, user, [
            ('start_date', '<=', date),
            ('end_date', '>=', date),
            ], order='start_date DESC', limit=1, context=context)
        if not ids:
            if exception:
                raise ExceptORM('Error', 'No period defined for this date!')
            else:
                return False
        return ids[0]

Period()
