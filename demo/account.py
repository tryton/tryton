# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt

from dateutil.relativedelta import relativedelta

from proteus import Model, Wizard


def setup(config, modules, company):
    AccountTemplate = Model.get('account.account.template')
    Account = Model.get('account.account')
    FiscalYear = Model.get('account.fiscalyear')
    SequenceStrict = Model.get('ir.sequence.strict')
    SequenceType = Model.get('ir.sequence.type')
    Party = Model.get('party.party')
    WriteOff = Model.get('account.move.reconcile.write_off')
    Journal = Model.get('account.journal')

    root_template, = AccountTemplate.find([
        ('parent', '=', None),
        ('name', '=', 'Universal Chart of Accounts'),
        ])
    create_chart_account = Wizard('account.create_chart')
    create_chart_account.execute('account')
    create_chart_account.form.account_template = root_template
    create_chart_account.form.company = company
    create_chart_account.execute('create_account')

    receivable, = Account.find([
            ('company', '=', company.id),
            ('code', '=', '1.2.1'),
            ])
    payable, = Account.find([
            ('company', '=', company.id),
            ('code', '=', '2.1.1'),
            ])

    create_chart_account.form.account_receivable = receivable
    create_chart_account.form.account_payable = payable
    create_chart_account.execute('create_properties')

    # Set account for parties created without company
    parties = Party.find([])
    for party in parties:
        party.account_receivable = receivable
        party.account_payable = payable
    Party.save(parties)

    move_sequence_type, = SequenceType.find(
        [('name', '=', "Account Move")], limit=1)
    invoice_sequence_type, = SequenceType.find([
            ('name', '=', "Invoice"),
            ], limit=1)
    today = dt.date.today()
    for start_date in (
            today + relativedelta(month=1, day=1, years=-1),
            today + relativedelta(month=1, day=1),
            today + relativedelta(month=1, day=1, years=1)):
        fiscalyear = FiscalYear(name='%s' % start_date.year)
        fiscalyear.start_date = start_date
        fiscalyear.end_date = start_date + relativedelta(month=12, day=31)
        fiscalyear.company = company
        move_sequence = SequenceStrict(
            name='%s' % start_date.year,
            sequence_type=move_sequence_type,
            company=company)
        move_sequence.save()
        fiscalyear.move_sequence = move_sequence
        invoice_sequence, = fiscalyear.invoice_sequences
        if 'account_invoice' in modules:
            for attr, name in (('out_invoice_sequence', 'Invoice'),
                    ('in_invoice_sequence', 'Supplier Invoice'),
                    ('out_credit_note_sequence', 'Credit Note'),
                    ('in_credit_note_sequence', 'Supplier Credit Note')):
                sequence = SequenceStrict(
                    name='%s %s' % (name, start_date.year),
                    sequence_type=invoice_sequence_type,
                    company=company)
                sequence.save()
                setattr(invoice_sequence, attr, sequence)
        fiscalyear.save()
        fiscalyear.click('create_period')

    expense, = Account.find([
            ('company', '=', company.id),
            ('code', '=', '6.2.1'),
            ], limit=1)
    write_off = WriteOff()
    write_off.name = "Currency Exchange"
    write_off.journal, = Journal.find(
        [('code', '=', 'EXC'), ('type', '=', 'write-off')], limit=1)
    write_off.credit_account = expense
    write_off.debit_account = expense
    write_off.save()
