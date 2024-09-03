==============================
Stock Product Replace Scenario
==============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import (
    ...     activate_modules, assertEqual, assertFalse, assertTrue)

Activate modules::

    >>> config = activate_modules('stock')

    >>> Cron = Model.get('ir.cron')
    >>> Location = Model.get('stock.location')
    >>> Move = Model.get('stock.move')
    >>> ProductTemplate = Model.get('product.template')
    >>> UoM = Model.get('product.uom')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Get stock locations::

    >>> supplier_loc, = Location.find([('code', '=', "SUP")])
    >>> storage_loc, = Location.find([('code', '=', "STO")])
    >>> customer_loc, = Location.find([('code', '=', "CUS")])

Create a product::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.type = 'goods'
    >>> template.default_uom = unit
    >>> template.save()
    >>> product1, = template.products

Create a second product::

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.type = 'goods'
    >>> template.default_uom = unit
    >>> template.save()
    >>> product2, = template.products

Fill storage location::

    >>> move = Move(product=product1)
    >>> move.quantity = 1
    >>> move.from_location = supplier_loc
    >>> move.to_location = storage_loc
    >>> move.unit_price = Decimal('10.0000')
    >>> move.currency = company.currency
    >>> move.click('do')
    >>> move.state
    'done'

Replace the product::

    >>> replace = Wizard('product.product.replace', models=[product1])
    >>> replace.form.destination = product2
    >>> replace.execute('replace')
    >>> assertEqual(product1.replaced_by, product2)
    >>> assertTrue(product1.active)

Create a draft move::

    >>> move = Move(product=product1)
    >>> move.quantity = 1
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('20.0000')
    >>> move.currency = company.currency
    >>> move.save()
    >>> move.state
    'draft'

Empty storage location::

    >>> move = Move(product=product1)
    >>> move.quantity = 1
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('20.0000')
    >>> move.currency = company.currency
    >>> move.click('do')
    >>> move.state
    'done'

Check replaced product is deactivated and draft move is deleted::

    >>> product1.reload()
    >>> assertFalse(product1.active)
    >>> Move.find([('state', '=', 'draft')])
    []

Create a move for replaced product change the product::

    >>> move = Move(product=product1)
    >>> move.quantity = 1
    >>> move.from_location = storage_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('20.0000')
    >>> move.currency = company.currency
    >>> move.save()
    >>> assertEqual(move.product, product2)
