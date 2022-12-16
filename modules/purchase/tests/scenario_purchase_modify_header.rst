===============================
Purchase Modify Header Scenario
===============================

Imports::

    >>> from proteus import Model, Wizard
    >>> from decimal import Decimal
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, create_tax, get_accounts

Install sale::

    >>> config = activate_modules('purchase')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> expense = accounts['expense']

Create tax and tax rule::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

    >>> TaxRule = Model.get('account.tax.rule')
    >>> foreign = TaxRule(name='Foreign Suppliers', company=company)
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
    >>> template.purchasable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_expense = expense
    >>> template.supplier_taxes.append(tax)
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('5')
    >>> product.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> another = Party(name='Another Supplier', supplier_tax_rule=foreign)
    >>> another.save()

Create a sale with a line::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 3
    >>> purchase.save()
    >>> purchase.untaxed_amount, purchase.tax_amount, purchase.total_amount
    (Decimal('15.00'), Decimal('1.50'), Decimal('16.50'))

Change the party::

    >>> modify_header = Wizard('purchase.modify_header', [purchase])
    >>> modify_header.form.party = another
    >>> modify_header.execute('modify')

    >>> purchase.party.name
    u'Another Supplier'
    >>> purchase.untaxed_amount, purchase.tax_amount, purchase.total_amount
    (Decimal('15.00'), Decimal('0'), Decimal('15.00'))
