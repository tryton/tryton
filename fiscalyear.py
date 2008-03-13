'Fiscal Year'

from trytond.osv import fields, OSV, ExceptORM
import mx.DateTime
import datetime
STATES = {
    'readonly': "state == 'close'",
}


class FiscalYear(OSV):
    'Fiscal Year'
    _name = 'account.fiscalyear'
    _description = __doc__
    _order = 'start_date'

    name = fields.Char('Name', size=None, required=True)
    code = fields.Char('Code', size=None)
    start_date = fields.Date('Starting Date', required=True, states=STATES)
    end_date = fields.Date('Ending Date', required=True, states=STATES)
    periods = fields.One2Many('account.period', 'fiscalyear', 'Periods',
            states=STATES)
    state = fields.Selection([
        ('open', 'Open'),
        ('close', 'Close'),
        ], 'State', readonly=True)

    def __init__(self):
        super(FiscalYear, self).__init__()
        self._rpc_allowed += [
            'create_period',
            'create_period_3',
        ]

    def default_state(self, cursor, user, context=None):
        return 'open'

    def create_period(self, cursor, user, ids, context=None, interval=1):
        '''
        Create periods for the fiscal years with month interval
        '''
        period_obj = self.pool.get('account.period')
        for fiscalyear in self.browse(cursor, user, ids, context=context):
            end_date = mx.DateTime.strptime(str(fiscalyear.end_date),
                    '%Y-%m-%d')
            period_start_date = mx.DateTime.strptime(str(fiscalyear.start_date),
                    '%Y-%m-%d')
            while period_start_date < end_date:
                period_end_date = period_start_date + \
                        mx.DateTime.RelativeDateTime(months=interval)
                if period_end_date > end_date:
                    period_end_date = end_date
                period_obj.create(cursor, user, {
                    'name': period_start_date.strftime('%Y-%m') + ' - ' + \
                            period_end_date.strftime('%Y-%m'),
                    'start_date': period_start_date.strftime('%Y-%m-%d'),
                    'end_date': period_end_date.strftime('%Y-%m-%d'),
                    'fiscalyear': fiscalyear.id,
                    }, context=context)
                period_start_date = period_start_date + \
                        mx.DateTime.RelativeDateTime(months=interval)
        return True

    def create_period_3(self, cursor, user, ids, context=None):
        '''
        Create periods for the fiscal years with 3 months interval
        '''
        return self.create_period(cursor, user, ids, context=context,
                interval=3)

    def find(self, cursor, user, date=None, exception=True, context=None):
        '''
        Return the fiscal year for the date or the current date.
        If exception is set the function will raise an exception
            if any fiscal year is found.
        '''
        if not date:
            date = datetime.date.today()
        ids = self.search(cursor, user, [
            ('start_date', '<=', date),
            ('end_date', '>=', date),
            ], order='start_date DESC', limit=1, context=context)
        if not ids:
            if exception:
                raise ExceptORM('Error', 'No fiscal year defined for this date!')
            else:
                return False
        return ids[0]

FiscalYear()
