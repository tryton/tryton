'Move'

from trytond.osv import fields, OSV, ExceptORM
from trytond.wizard import Wizard, WizardOSV
from decimal import Decimal
import datetime

_MOVE_STATES = {
    'readonly': "state == 'posted'",
}
_LINE_STATES = {
    'readonly': "state == 'valid'",
}


class Move(OSV):
    'Account Move'
    _name = 'account.move'
    _description = __doc__

    name = fields.Char('Name', size=None, required=True)
    reference = fields.Char('Reference', size=None, readonly=True)
    period = fields.Many2One('account.period', 'Period', required=True,
            states=_MOVE_STATES)
    journal = fields.Many2One('account.journal', 'Journal', required=True,
            states=_MOVE_STATES)
    date = fields.Date('Effective Date', required=True, states=_MOVE_STATES)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ], 'State', required=True, readonly=True)
    lines = fields.One2Many('account.move.line', 'move', 'Lines',
            states=_MOVE_STATES)

    def __init__(self):
        super(Move, self).__init__()
        self._constraints += [
            ('check_centralisation',
                'Error! You can not create more than one move per period \n' \
                        'in centralized journal', ['journal']),
            ('check_company',
                'Error! You can not create lines on account \n' \
                        'from different company in the same move!', ['lines']),
        ]
        self._rpc_allowed += [
            'button_post',
            'button_draft',
        ]

    def _auto_init(self, cursor, module_name):
        super(Move, self)._auto_init(cursor, module_name)
        cursor.execute('SELECT indexname FROM pg_indexes ' \
                'WHERE indexname = \'account_move_journal_period_index\'')
        if not cursor.rowcount:
            cursor.execute('CREATE INDEX account_move_journal_period_index ' \
                    'ON account_move (period, journal)')

    def default_name(self, cursor, user, context=None):
        sequence_obj = self.pool.get('ir.sequence')
        return sequence_obj.get(cursor, user, 'account.move')

    def default_period(self, cursor, user, context=None):
        period_obj = self.pool.get('account.period')
        return period_obj.find(cursor, user, exception=False, context=context)

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_date(self, cursor, user, context=None):
        return datetime.date.today()

    def check_centralisation(self, cursor, user, ids):
        for move in self.browse(cursor, user, ids):
            if move.journal.centralised:
                move_ids = self.search(cursor, user, [
                    ('period', '=', move.period.id),
                    ('journal', '=', move.journal.id),
                    ], limit=2)
                if len(move_ids) > 1:
                    return False
        return True

    def check_company(self, cursor, user, ids):
        for move in self.browse(cursor, user, ids):
            company_id = -1
            for line in move.lines:
                if company_id < 0:
                    company_id = line.account.company.id
                if line.account.company.id != company_id:
                    return False
        return True

    def write(self, cursor, user, ids, vals, context=None):
        res = super(Move, self).write(cursor, user, ids, vals, context=context)
        self.validate(cursor, user, ids, context=context)
        return res

    def create(self, cursor, user, vals, context=None):
        res = super(Move, self).create(cursor, user, vals, context=context)
        if 'lines' in vals:
            self.validate(cursor, user, [res], context=context)
        return res

    def unlink(self, cursor, user, ids, context=None):
        move_line_obj = self.pool.get('account.move.line')
        for move in self.browse(cursor, user, ids, context=context):
            if move.state == 'posted':
                raise ExceptORM('UserError',
                        'You can not delete posted move!')
            if move.lines:
                move_line_ids = [x.id for x in move.lines]
                move_line_obj.unlink(cursor, user, move_line_ids,
                        context=context)
        return super(Move, self).unlink(cursor, user, ids, context=context)

    def validate(self, cursor, user, ids, context=None):
        '''
        Validate balanced move and centralise it if in centralised journal
        '''
        currency_obj = self.pool.get('account.currency')
        move_line_obj = self.pool.get('account.move.line')
        if isinstance(ids, (int, long)):
            ids = [ids]
        for move in self.browse(cursor, user, ids, context=context):
            if not move.lines:
                continue
            amount = Decimal('0.0')
            company = None
            draft_lines = []
            for line in move.lines:
                amount += line.debit - line.credit
                if not company:
                    company = line.account.company
                if line.state == 'draft':
                    draft_lines.append(line)
            if not currency_obj.is_zero(cursor, user, company.currency, amount):
                if move.journal.centralised:
                    #TODO centralised move
                    raise Exception('Not implemented')
                else:
                    move_line_obj.write(cursor, user,
                            [x.id for x in move.lines if x.state != 'draft'], {
                                'state': 'draft',
                                }, context=context)
                continue
            if not draft_lines:
                continue
            move_line_obj.write(cursor, user,
                    [x.id for x in draft_lines], {
                        'state': 'valid',
                        }, context=context)
            if move.journal.type not in ('expense', 'revenue'):
                continue
            #TODO compute tax
        return

    def post(self, cursor, user, ids, context=None):
        currency_obj = self.pool.get('account.currency')
        sequence_obj = self.pool.get('ir.sequence')
        moves = self.browse(cursor, user, ids, context=context)
        for move in moves:
            amount = Decimal('0.0')
            company = None
            for line in move.lines:
                amount += line.debit - line.credit
                if not company:
                    company = line.account.company
            if not currency_obj.is_zero(cursor, user, company.currency, amount):
                raise ExceptORM('UserError',
                        'You can not post a unbalanced move!')
        for move in moves:
            reference = sequence_obj.get_id(cursor, user, move.journal.sequence.id)
            self.write(cursor, user, move.id, {
                'reference': reference,
                'state': 'posted',
                }, context=context)
        return

    def draft(self, cursor, user, ids, context=None):
        for move in self.browse(cursor, user, ids, context=context):
            if not move.journal.update_posted:
                raise ExceptORM('UserError',
                        'You can not modify a posted move in this journal!')
        return self.write(cursor, user, ids, {
            'state': 'draft',
            }, context=context)

    def button_post(self, cursor, user, ids, context=None):
        return self.post(cursor, user, ids, context=None)

    def button_draft(self, cursor, user, ids, context=None):
        return self.draft(cursor, user, ids, context=context)

Move()


class Line(OSV):
    'Account Move Line'
    _name = 'account.move.line'
    _description = __doc__
    _order = 'id DESC'

    name = fields.Char('Name', size=None, required=True)
    debit = fields.Numeric('Debit', digits=(16, 2))
    credit = fields.Numeric('Credit', digits=(16, 2))
    account = fields.Many2One('account.account', 'Account', required=True,
            domain=[('type', '!=', 'view'), ('type', '!=', 'closed')],
            select=1)
    move = fields.Many2One('account.move', 'Move', states=_LINE_STATES,
            select=1, required=True)
    journal = fields.Function('get_move_field', fnct_inv='set_move_field',
            type='many2one', relation='account.journal', string='Journal',
            fnct_search='search_move_field')
    period = fields.Function('get_move_field', fnct_inv='set_move_field',
            type='many2one', relation='account.period', string='Period',
            fnct_search='search_move_field')
    date = fields.Function('get_move_field', fnct_inv='set_move_field',
            type='date', string='Effective Date', required=True,
            fnct_search='search_move_field')
    reference = fields.char('Reference', size=None)
    amount_second_currency = fields.Numeric('Amount Second Currency',
            digits=(16, 2), help='The amount expressed in a second currency')
    second_currency = fields.Many2One('account.currency', 'Second Currency',
            help='The second currency')
    partner = fields.Many2One('partner.partner', 'Partner',
            on_change=['move', 'partner', 'account', 'debit', 'credit',
                'journal'])
    blocked = fields.Boolean('Litigation',
            help='Mark the line as litigation with the partner.')
    maturity_date = fields.Date('Muturity Date',
            help='This field is used for payable and receivable linees. \n' \
                    'You can put the limit date for the payment.')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('valid', 'Valid'),
        ], 'State', readonly=True, required=True)
    active = fields.Boolean('Active', select=2)
    #TODO add reconcile

    def __init__(self):
        super(Line, self).__init__()
        self._sql_constraints += [
            ('credit_debit',
                'CHECK((credit * debit = 0) AND (credit + debit >= 0))',
                'Wrong credit/debit values!'),
        ]
        self._constraints += [
            ('check_account', 'You can not create move line \n' \
                    'on view/closed/inactive account!', ['account']),
        ]
        self._rpc_allowed += [
            'on_write',
        ]

    def default_date(self, cursor, user, context=None):
        '''
        Return the date of the last line for journal, period
        or the starting date of the period
        or today
        '''
        if context is None:
            context = {}
        period_obj = self.pool.get('account.period')
        res = datetime.date.today()
        if context.get('journal') and context.get('period'):
            line_ids = self.search(cursor, user, [
                ('journal', '=', context['journal']),
                ('period', '=', context['period']),
                ], order='id DESC', limit=1, context=context)
            if line_ids:
                line = self.browse(cursor, user, line_ids[0], context=context)
                res = line.date
            else:
                period = period_obj.browse(cursor, user, context['period'],
                        context=context)
                res = period.start_date
        return res

    def default_state(self, cursor, user, context=None):
        return 'draft'

    def default_blocked(self, cursor, user, context=None):
        return False

    def default_active(self, cursor, user, context=None):
        return True

    def default_get(self, cursor, user, fields, context=None):
        if context is None:
            context = {}
        move_obj = self.pool.get('account.move')
        values = super(Line, self).default_get(cursor, user, fields,
                context=context)

        if 'move' not in fields:
            #Not manual entry
            return values

        if context.get('journal') and context.get('period'):
            line_ids = self.search(cursor, user, [
                ('move.journal', '=', context['journal']),
                ('move.period', '=', context['period']),
                ('create_uid', '=', user),
                ('state', '=', 'draft'),
                ], order='id DESC', limit=1, context=context)
            if not line_ids:
                return values
            line = self.browse(cursor, user, line_ids[0], context=context)
            values['move'] = line.move.id

        if 'move' not in values:
            return values

        move = move_obj.browse(cursor, user, values['move'], context=context)
        total = Decimal('0.0')
        for line in move.lines:
            total += line.debit - line.credit
            if line.partner and 'partner' in fields:
                values.setdefault('partner', line.partner.id)
            if 'reference' in fields:
                values.setdefault('reference', line.reference)
            if 'name' in fields:
                values.setdefault('name', line.name)
            #TODO taxes

        if 'account' in fields:
            if total >= 0.0:
                values.setdefault('account', move.journal.credit_account \
                        and move.journal.credit_account.id or False)
            else:
                values.setdefault('account', move.journal.debit_account \
                        and move.journal.debit_account.id or False)
            if values['account']:
                #TODO add taxes code
                pass

        if move.journal.type in ('expense', 'revenue'):
            #TODO taxes
            pass

        #Compute last line
        if ('debit' in fields) or ('credit' in fields):
            values.setdefault('debit',  total < 0 and - total or False)
            values.setdefault('credit', total > 0 and total or False)
        return values

    def on_change_partner(self, cursor, user, ids, vals, context=None):
        partner_obj = self.pool.get('partner.partner')
        if (not vals.get('partner')) or vals.get('account'):
            return {}
        partner = partner_obj.browse(cursor, user, vals.get('partner'),
                context=context)
        #TODO add property on partner
        return {}

    def get_move_field(self, cursor, user, ids, name, arg, context=None):
        if name not in ('period', 'journal', 'date'):
            raise Exception('Invalid name')
        obj = self.pool.get('account.' + name)
        res = {}
        for line in self.browse(cursor, user, ids, context=context):
            if name in ('date',):
                res[line.id] = line.move[name]
            else:
                res[line.id] = line.move[name].id
        if name in ('date',):
            return res
        obj_names = {}
        for obj_id, obj_name in obj.name_get(cursor, user,
                [x for x in res.values() if x], context=context):
            obj_names[obj_id] = obj_name

        for i in res.keys():
            if res[i] and res[i] in obj_names:
                res[i] = (res[i], obj_names[res[i]])
            else:
                res[i] = False
        return res

    def set_move_field(self, cursor, user, id, name, value, arg, context=None):
        if name not in ('period', 'journal', 'date'):
            raise Exception('Invalid name')
        move_obj = self.pool.get('account.move')
        line = self.browse(cursor, user, id, context=context)
        move_obj.write(cursor, user, line.move.id, {
            name: value,
            }, context=context)

    def search_move_field(cursor, user, obj, name, args, context=None):
        args2 = []
        i = 0
        while i < len(args):
            args2.append(('move.' + args[i][0], args[i][1], args[i][2]))
            i += 1
        return args2

    def query_get(self, cursor, user, obj='l', context=None):
        '''
        Return SQL clause for account move line.
        obj is the SQL alias of the account_move_line in the query.
        '''
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        if context is None:
            context = {}
        if not context.get('fiscalyear', False):
            fiscalyear_ids = fiscalyear_obj.search(cursor, user, [
                ('state', '=', 'open'),
                ], context=context)
            fiscalyear_clause = (','.join([str(x) for x in fiscalyear_ids])) or 'False'
        else:
            fiscalyear_clause = '%s' % int(context.get('fiscalyear'))
        if context.get('periods', False):
            ids = ','.join([str(int(x)) for x in context['periods']])
            return obj + '.active ' \
                    'AND ' + obj + '.state != \'draft\' ' \
                    'AND ' + obj + '.move IN (' \
                        'SELECT id FROM account_move ' \
                            'WHERE period IN (' \
                                'SELECT id FROM account_period ' \
                                'WHERE fiscalyear IN (' + fiscalyear_clause + ') ' \
                                    'AND id IN (' + ids + ')' \
                            ')' \
                        ')'
        else:
            return obj + '.active ' \
                    'AND ' + obj + '.state != \'draft\' ' \
                    'AND ' + obj + '.move IN (' \
                        'SELECT id FROM account_move ' \
                            'WHERE period IN (' \
                                'SELECT id FROM account_period ' \
                                'WHERE fiscalyear IN (' + fiscalyear_clause + ')' \
                            ')' \
                        ')'

    def on_write(self, cursor, user, ids, context=None):
        lines = self.browse(cursor, user, ids, context)
        res = []
        for line in lines:
            res.extend([x.id for x in line.move.lines])
        return list({}.fromkeys(res))

    def check_account(self, cursor, user, ids):
        for line in self.browse(cursor, user, ids):
            if line.account.type in ('view', 'closed'):
                return False
            if not line.account.active:
                return False
        return True

    def check_journal_period_modify(self, cursor, user, period_id,
            journal_id, context=None):
        '''
        Check if the lines can be modified or created for the journal - period
        and if there is no journal - period, create it
        '''
        journal_period_obj = self.pool.get('account.journal.period')
        journal_obj = self.pool.get('account.journal')
        period_obj = self.pool.get('account.period')
        journal_period_ids = journal_period_obj.search(cursor, user, [
            ('journal', '=', journal_id),
            ('period', '=', period_id),
            ], limit=1, context=context)
        if journal_period_ids:
            journal_period = journal_period_obj.browse(cursor, user,
                    journal_period_ids[0], context=context)
            if journal_period.state == 'close':
                raise ExceptORM('UserError',
                        'You can not add/modify lines \n' \
                                'in a closed journal period!')
        else:
            journal = journal_obj.browse(cursor, user, journal_id,
                    context=context)
            period = period_obj.browse(cursor, user, period_id,
                    context=context)
            journal_period_obj.create(cursor, user, {
                'name': journal.name + ' - ' + period.name,
                'journal': journal.id,
                'period': period.id,
                }, context=context)
        return

    def check_modify(self, cursor, user, ids, context=None):
        '''
        Check if the lines can be modified
        '''
        journal_period_done = []
        for line in self.browse(cursor, user, ids, context=context):
            if line.move.state == 'posted':
                raise ExceptORM('UserError',
                        'You can not modify line from a posted move!')
            #TODO add reconcile
            journal_period = (line.journal.id, line.period.id)
            if journal_period not in journal_period_done:
                self.check_journal_period_modify(cursor, user, line.period.id,
                        line.journal.id, context=context)
                journal_period_done.append(journal_period)
        return

    def unlink(self, cursor, user, ids, context=None):
        move_obj = self.pool.get('account.move')
        self.check_modify(cursor, user, ids, context=context)
        lines = self.browse(cursor, user, ids, context=context)
        move_ids = [x.move.id for x in lines]
        res = super(Line, self).unlink(cursor, user, ids, context=context)
        move_obj.validate(cursor, user, move_ids, context=context)
        return res

    def write(self, cursor, user, ids, vals, context=None):
        move_obj = self.pool.get('account.move')
        self.check_modify(cursor, user, ids, context=context)
        lines = self.browse(cursor, user, ids, context=context)
        move_ids = [x.move.id for x in lines]
        res = super(Line, self).write(cursor, user, ids, vals, context=context)
        lines = self.browse(cursor, user, ids, context=context)
        for line in lines:
            if line.move.id not in move_ids:
                move_ids.append(line.move.id)
        move_obj.validate(cursor, user, move_ids, context=context)
        return res

    def create(self, cursor, user, vals, context=None):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        move_obj = self.pool.get('account.move')
        vals = vals.copy()
        if not vals.get('move'):
            journal_id = vals.get('journal', context.get('journal'))
            if not journal_id:
                raise ExceptORM('Error', 'No journal defined!')
            journal = journal_obj.browse(cursor, user, journal_id,
                    context=context)
            if journal.centralised:
                #TODO journalised
                raise Exception('Not implemented')
            else:
                vals['move'] = move_obj.create(cursor, user, {
                    'period': vals.get('period', context.get('period')),
                    'journal': vals.get('journal', context.get('journal')),
                    }, context=context)
        res = super(Line, self).create(cursor, user, vals, context=context)
        line = self.browse(cursor, user, res, context=context)
        self.check_journal_period_modify(cursor, user, line.period.id,
                line.journal.id, context=context)
        move_obj.validate(cursor, user, [vals['move']], context=context)
        return res

    def view_header_get(self, cursor, user, view_id=None, view_type='form',
            context=None):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        period_obj = self.pool.get('account.period')
        if not context.get('journal') or not context.get('period'):
            return False
        journal = journal_obj.browse(cursor, user, context['journal'],
                context=context)
        period = period_obj.browse(cursor, user, context['period'],
                context=context)
        if journal and period:
            return journal.name + ': ' + period.name
        return False

    def fields_view_get(self, cursor, user, view_id=None, view_type='form',
            context=None, toolbar=False, hexmd5=None):
        if context is None:
            context = {}
        journal_obj = self.pool.get('account.journal')
        result = super(Line, self).fields_view_get(cursor, user,
                view_id=view_id, view_type=view_type, context=context,
                toolbar=toolbar, hexmd5=hexmd5)
        if view_type == 'tree' and 'journal' in context:
            title = self.view_header_get(cursor, user, view_id=view_id,
                    view_type=view_type, context=context)
            journal = journal_obj.browse(cursor, user, context['journal'],
                    context=context)

            if not journal.view:
                return result

            xml = '<?xml version="1.0"?>\n' \
                    '<tree string="%s" editable="top" on_write="on_write" ' \
                    'colors="red:state==\'draft\'">\n'
            fields = []
            for column in journal.view.columns:
                fields.append(column.field.name)
                attrs = []
                if column.field.name == 'debit':
                    attrs.append('sum="Total debit"')
                elif column.field.name == 'credit':
                    attrs.append('sum="Total credit"')
                if column.readonly:
                    attrs.append('readonly="1"')
                if column.required:
                    attrs.append('required="1"')
                else:
                    attrs.append('required="0"')
                xml += '<field name="%s" %s/>\n' % (column.field.name, ' '.join(attrs))
            xml += '</tree>'
            result['arch'] = xml
            result['fields'] = self.fields_get(cursor, user, fields_names=fields,
                    context=context)
            #TODO add hexmd5
        return result

Line()


class OpenJournalInit(WizardOSV):
    _name = 'account.move.open_journal.init'
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    period = fields.Many2One('account.period', 'Period', required=True)

    def default_period(self, cursor, user, context=None):
        period_obj = self.pool.get('account.period')
        return period_obj.find(cursor, user, exception=False, context=context)

OpenJournalInit()


class OpenJournal(Wizard):
    'Open Journal'
    _name = 'account.move.open_journal'
    states = {
        'init': {
            'result': {
                'type': 'choice',
                'next_state': '_next',
            },
        },
        'ask': {
            'result': {
                'type': 'form',
                'object': 'account.move.open_journal.init',
                'state': [
                    ('end', 'Cancel', 'gtk-cancel'),
                    ('open', 'Open', 'gtk-ok', True),
                ],
            },
        },
        'open': {
            'result': {
                'type': 'action',
                'action': '_action_open_journal',
                'state': 'end',
            },
        },
    }

    def _next(self, cursor, user, data, context=None):
        if data.get('model', '') == 'account.journal.period' \
                and data.get('id'):
            return 'open'
        return 'ask'

    def _get_journal_period(self, cursor, user, data, context=None):
        journal_period_obj = self.pool.get('account.journal.period')
        if data.get('model', '') == 'account.journal.period' \
                and data.get('id'):
            journal_period = journal_period_obj.browse(cursor, user,
                    data['id'], context=context)
            return {
                'journal': journal_period.journal.id,
                'period': journal_period.period.id,
            }
        return {}

    def _action_open_journal(self, cursor, user, data, context=None):
        journal_period_obj = self.pool.get('account.journal.period')
        journal_obj = self.pool.get('account.journal')
        period_obj = self.pool.get('account.period')
        if data.get('model', '') == 'account.journal.period' \
                and data.get('id'):
            journal_period = journal_period_obj.browse(cursor, user,
                    data['id'], context=context)
            journal_id = journal_period.journal.id
            period_id = journal_period.period.id
        else:
            journal_id = data['form']['journal']
            period_id = data['form']['period']
        if not journal_period_obj.search(cursor, user, [
            ('journal', '=', journal_id),
            ('period', '=', period_id),
            ], context=context):
            journal = journal_obj.browse(cursor, user, journal_id,
                    context=context)
            period = period_obj.browse(cursor, user, period_id,
                    context=context)
            journal_period_obj.create(cursor, user, {
                'name': journal.name + ' - ' + period.name,
                'journal': journal.id,
                'period': period.id,
                }, context=context)
        return {
            'domain': str([
                ('journal', '=', journal_id),
                ('period', '=', period_id),
                ]),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move.line',
            'type': 'ir.action.act_window',
            'context': str({
                'journal': journal_id,
                'period': period_id,
            }),
        }

OpenJournal()
