======================
Stock Lot POS Scenario
======================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     ['stock_lot', 'sale_point'], create_company, create_chart)

    >>> Journal = Model.get('account.journal')
    >>> Location = Model.get('stock.location')
    >>> Lot = Model.get('stock.lot')
    >>> POS = Model.get('sale.point')
    >>> PaymentMethod = Model.get('sale.point.payment.method')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.point.sale')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> StockMove = Model.get('stock.move')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Create account categories::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.account_category = account_category
    >>> template.gross_price = Decimal('10.0000')
    >>> template.lot_required = ['storage', 'customer']
    >>> template.save()
    >>> goods, = template.products

    >>> lot = Lot(number='0001', product=goods)
    >>> lot.save()

    >>> template = ProductTemplate()
    >>> template.name = 'service'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.salable = True
    >>> template.account_category = account_category
    >>> template.gross_price = Decimal('10.0000')
    >>> template.save()
    >>> service, = template.products

Get journal::

    >>> journal_revenue, = Journal.find([('type', '=', 'revenue')], limit=1)

Get stock locations::

    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Create POS::

    >>> pos = POS(name="POS")
    >>> pos.journal = journal_revenue
    >>> pos.sequence = SequenceStrict(name="POS", company=pos.company)
    >>> pos.sequence.sequence_type, = SequenceType.find(
    ...     [('name', '=', "POS")], limit=1)
    >>> pos.sequence.save()
    >>> pos.storage_location = storage_loc
    >>> pos.customer_location = customer_loc
    >>> pos.save()

Setup a payment method::

    >>> cash_method = PaymentMethod(name="Cash")
    >>> cash_method.account = accounts['cash']
    >>> cash_method.cash = True
    >>> cash_method.save()

Make a sale with lot::

    >>> sale = Sale(point=pos)
    >>> line = sale.lines.new()
    >>> line.product = goods
    >>> line.lot = lot
    >>> line.quantity = 1
    >>> line = sale.lines.new()
    >>> line.product = service
    >>> line.quantity = 1
    >>> sale.save()
    >>> sale.state
    'open'

Pay the sale::

    >>> payment = sale.click('pay')
    >>> payment.form.method = cash_method
    >>> payment.execute('pay')
    >>> sale.state
    'done'

Post the sale::

    >>> sale.click('post')
    >>> sale.state
    'posted'

Check stock move::

    >>> move, = StockMove.find([
    ...     ('origin.sale', '=', sale.id, 'sale.point.sale.line')
    ...     ])
    >>> assertEqual(move.product, goods)
    >>> assertEqual(move.lot, lot)
