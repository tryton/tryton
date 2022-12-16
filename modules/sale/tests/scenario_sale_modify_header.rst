===========================
Sale Modify Header Scenario
===========================

Imports::

    >>> from proteus import Model, Wizard
    >>> from decimal import Decimal
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, create_tax, get_accounts

Install sale::

    >>> config = activate_modules('sale')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']

Create tax and tax rule::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

    >>> TaxRule = Model.get('account.tax.rule')
    >>> foreign = TaxRule(name='Foreign Customers', company=company)
    >>> no_tax = foreign.lines.new()
    >>> no_tax.origin_tax = tax
    >>> foreign.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_revenue = revenue
    >>> template.customer_taxes.append(tax)
    >>> template.save()
    >>> product, = template.products

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> another = Party(name='Another Customer', customer_tax_rule=foreign)
    >>> another.save()

Create a sale with a line::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 3
    >>> sale.save()
    >>> sale.untaxed_amount, sale.tax_amount, sale.total_amount
    (Decimal('30.00'), Decimal('3.00'), Decimal('33.00'))

Change the party::

    >>> modify_header = Wizard('sale.modify_header', [sale])
    >>> modify_header.form.party = another
    >>> modify_header.execute('modify')

    >>> sale.party.name
    u'Another Customer'
    >>> sale.untaxed_amount, sale.tax_amount, sale.total_amount
    (Decimal('30.00'), Decimal('0'), Decimal('30.00'))
