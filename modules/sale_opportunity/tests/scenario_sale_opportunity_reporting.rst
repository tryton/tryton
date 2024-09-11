===================================
Sale Opportunity Reporting Scenario
===================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('sale_opportunity', create_company)

    >>> Employee = Model.get('company.employee')
    >>> Opportunity = Model.get('sale.opportunity')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')

Create employees::

    >>> employee1_party = Party(name="Employee 1")
    >>> employee1_party.save()
    >>> employee1 = Employee(party=employee1_party)
    >>> employee1.save()

    >>> employee2_party = Party(name="Employee 2")
    >>> employee2_party.save()
    >>> employee2 = Employee(party=employee2_party)
    >>> employee2.save()

Create parties::

    >>> customer1 = Party(name="Customer 1")
    >>> customer1.save()
    >>> customer2 = Party(name="Customer 2")
    >>> customer2.save()

Create leads and opportunities::

    >>> lead = Opportunity(party=customer1)
    >>> lead.amount = Decimal('1000.00')
    >>> lead.save()

    >>> opportunity = Opportunity(party=customer1)
    >>> opportunity.amount = Decimal('2000.00')
    >>> opportunity.employee = employee1
    >>> opportunity.click('opportunity')

    >>> opportunity = Opportunity(party=customer2)
    >>> opportunity.amount = Decimal('500.00')
    >>> opportunity.employee = employee2
    >>> opportunity.end_date = today
    >>> opportunity.click('opportunity')
    >>> sale, = opportunity.click('convert')

    >>> opportunity = Opportunity(party=customer1)
    >>> opportunity.amount = Decimal('700.00')
    >>> opportunity.employee = employee1
    >>> opportunity.click('opportunity')
    >>> sale, = opportunity.click('convert')
    >>> line = sale.lines.new()
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('800.00')
    >>> sale.invoice_address, = sale.party.addresses
    >>> sale.click('quote')
    >>> sale.click('confirm')

    >>> opportunity = Opportunity(party=customer2)
    >>> opportunity.amount = Decimal('200.00')
    >>> opportunity.employee = employee2
    >>> opportunity.click('opportunity')
    >>> opportunity.click('lost')

Check opportunity reporting::

    >>> Main = Model.get('sale.opportunity.reporting.main')
    >>> context = dict(
    ...     from_date=today,
    ...     to_date=today,
    ...     period='month')
    >>> with config.set_context(context=context):
    ...     reports = Main.find([])
    >>> report, = reports
    >>> report.number
    5
    >>> report.amount
    Decimal('4500.00')
    >>> report.converted
    2
    >>> report.conversion_rate
    0.4
    >>> report.converted_amount
    Decimal('1300.00')

    >>> report, = report.time_series
    >>> report.number
    5
    >>> report.amount
    Decimal('4500.00')
    >>> report.converted
    2
    >>> report.conversion_rate
    0.4
    >>> report.converted_amount
    Decimal('1300.00')

Check conversion reporting::

    >>> Conversion = Model.get('sale.opportunity.reporting.conversion')
    >>> with config.set_context(context=context):
    ...     reports = Conversion.find([])
    >>> report, = reports
    >>> report.number
    3
    >>> report.converted
    2
    >>> report.won
    1
    >>> report.winning_rate
    0.3333
    >>> report.won_amount
    Decimal('800.00')
    >>> report.lost
    1
    >>> len(report.time_series)
    1

    >>> ConversionEmployee = Model.get(
    ...     'sale.opportunity.reporting.conversion.employee')
    >>> with config.set_context(context=context):
    ...     reports = ConversionEmployee.find([])
    >>> len(reports)
    2
