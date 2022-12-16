==============================
Sale Promotion Coupon Scenario
==============================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_chart, \
    ...     get_accounts

Activate modules::

    >>> config = activate_modules('sale_promotion_coupon')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product,  = template.products

Create Promotion with coupon::

    >>> Promotion = Model.get('sale.promotion')
    >>> promotion = Promotion(name="10%")
    >>> promotion.formula = '0.9 * unit_price'
    >>> coupon = promotion.coupons.new(name="Promo")
    >>> coupon.number_of_use = 0
    >>> number = coupon.numbers.new(number="CODE10")
    >>> promotion.save()

Sale without promotion coupon::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 5
    >>> sale.save()
    >>> sale.untaxed_amount
    Decimal('100.00')
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('100.00')

Add promotion coupon to the sale::

    >>> sale.click('draft')
    >>> sale.coupons.extend(sale.coupons.find([('rec_name', '=', 'CODE10')]))
    >>> len(sale.coupons)
    1
    >>> sale.save()
    >>> sale.untaxed_amount
    Decimal('100.00')
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('90.00')

Check coupon inactive after usage::

    >>> Number = Model.get('sale.promotion.coupon.number')
    >>> coupon, = promotion.coupons

    >>> number, = Number.find([('rec_name', '=', 'CODE10')])
    >>> bool(number.active)
    True

    >>> with config.set_context(party=customer.id):
    ...     number_party, = Number.find([('rec_name', '=', 'CODE10')])
    >>> bool(number_party.active)
    True

    >>> coupon.number_of_use = 1
    >>> coupon.save()
    >>> number.reload()
    >>> bool(number.active)
    False
    >>> Number.find([('rec_name', '=', 'CODE10')])
    []
    >>> number_party.reload()
    >>> bool(number_party.active)
    False
    >>> with config.set_context(party=customer.id):
    ...     Number.find([('rec_name', '=', 'CODE10')])
    []

Cancel sale remove the coupons::

    >>> sale.click('cancel')
    >>> len(sale.coupons)
    0
