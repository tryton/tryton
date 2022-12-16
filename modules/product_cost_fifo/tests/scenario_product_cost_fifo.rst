=====================
Stock FIFO Cost Price
=====================

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install stock Module::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([('name', '=', 'product_cost_fifo')])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     currency = Currency(name='US Dollar', symbol='$', code='USD',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point='.')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('300')
    >>> template.cost_price = Decimal('80')
    >>> template.cost_price_method = 'fifo'
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Make 4 units of the product available @ 10 ::

    >>> StockMove = Model.get('stock.move')
    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 4
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('10')
    >>> incoming_move.currency = currency
    >>> incoming_move.save()
    >>> StockMove.do([incoming_move.id], config.context)

Check Cost Price is 10::

    >>> product.reload()
    >>> product.template.cost_price == Decimal('10')
    True

Add 2 more units @ 25::

    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 2
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('25')
    >>> incoming_move.currency = currency
    >>> incoming_move.save()
    >>> StockMove.do([incoming_move.id], config.context)

Check Cost Price FIFO is 15::

    >>> product.reload()
    >>> product.template.cost_price == Decimal('15')
    True

Sell 3 units @ 50::

    >>> outgoing_move = StockMove()
    >>> outgoing_move.product = product
    >>> outgoing_move.uom = unit
    >>> outgoing_move.quantity = 3
    >>> outgoing_move.from_location = storage_loc
    >>> outgoing_move.to_location = customer_loc
    >>> outgoing_move.planned_date = today
    >>> outgoing_move.company = company
    >>> outgoing_move.unit_price = Decimal('50')
    >>> outgoing_move.currency = currency
    >>> outgoing_move.save()
    >>> StockMove.do([outgoing_move.id], config.context)

Check Cost Price FIFO is 20::

    >>> product.reload()
    >>> product.template.cost_price == Decimal('20')
    True

Sell 2 more units @ 50::

    >>> outgoing_move = StockMove()
    >>> outgoing_move.product = product
    >>> outgoing_move.uom = unit
    >>> outgoing_move.quantity = 2
    >>> outgoing_move.from_location = storage_loc
    >>> outgoing_move.to_location = customer_loc
    >>> outgoing_move.planned_date = today
    >>> outgoing_move.company = company
    >>> outgoing_move.unit_price = Decimal('50')
    >>> outgoing_move.currency = currency
    >>> outgoing_move.save()
    >>> StockMove.do([outgoing_move.id], config.context)

Check Cost Price FIFO is 25::

    >>> product.reload()
    >>> product.template.cost_price == Decimal('25')
    True
