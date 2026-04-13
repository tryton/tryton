=======================================================
Purchase Average Lead Time of Product Supplier Scenario
=======================================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('purchase', create_company, create_chart)

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductSupplier = Model.get('purchase.product_supplier')
    >>> ProductTemplate = Model.get('product.template')
    >>> Purchase = Model.get('purchase.purchase')
    >>> UoM = Model.get('product.uom')

Create suppliers::

    >>> supplier1 = Party(name="Supplier 1")
    >>> supplier1.save()
    >>> supplier2 = Party(name="Supplier 2")
    >>> supplier2.save()

Create account category::

    >>> accounts = get_accounts()

    >>> account_category = ProductCategory(name="Account", accounting=True)
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.save()

Create product::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate(name="Product")
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.account_category = account_category
    >>> _ = template.product_suppliers.new(party=supplier1)
    >>> template.save()
    >>> product, = template.products
    >>> _ = product.product_suppliers.new(party=supplier2)
    >>> product.save()

Create purchases::

    >>> purchase = Purchase(party=supplier1)
    >>> purchase.purchase_date = today - dt.timedelta(days=12)
    >>> line = purchase.lines.new(product=product)
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('42.0000')
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

    >>> purchase = Purchase(party=supplier1)
    >>> purchase.purchase_date = today - dt.timedelta(days=6)
    >>> line = purchase.lines.new(product=product)
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('42.0000')
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

    >>> purchase = Purchase(party=supplier2)
    >>> purchase.purchase_date = today - dt.timedelta(days=5)
    >>> line = purchase.lines.new(product=product)
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('42.0000')
    >>> line.product_supplier = None
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

Check average lead time of product suppliers::

    >>> product_supplier1, = ProductSupplier.find([('party', '=', supplier1)])
    >>> product_supplier1.average_lead_time
    datetime.timedelta(days=9)

    >>> product_supplier2, = ProductSupplier.find([('party', '=', supplier2)])
    >>> product_supplier2.average_lead_time
    datetime.timedelta(days=5)
