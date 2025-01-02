=============================================
Sale Complaint with Promotion Coupon Scenario
=============================================

Imports::

    >>> import datetime as dt
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
    ...     ['sale_complaint', 'sale_promotion_coupon'],
    ...     create_company, create_chart)

    >>> Complaint = Model.get('sale.complaint')
    >>> IrModel = Model.get('ir.model')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Promotion = Model.get('sale.promotion')
    >>> Sale = Model.get('sale.sale')
    >>> Type = Model.get('sale.complaint.type')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Create parties::

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create complaint type::

    >>> sale_type = Type(name='Sale')
    >>> sale_type.origin, = IrModel.find([('name', '=', 'sale.sale')])
    >>> sale_type.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create Promotion with coupon::

    >>> promotion = Promotion(name="50%")
    >>> promotion.formula = '0.5 * unit_price'
    >>> coupon = promotion.coupons.new()
    >>> coupon.number_of_use = 1
    >>> coupon.per_party = False
    >>> promotion.save()
    >>> coupon, = promotion.coupons

Sale 1 product::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 1
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Fill a complaint for the sale::

    >>> complaint = Complaint()
    >>> complaint.customer = customer
    >>> complaint.type = sale_type
    >>> complaint.origin = sale
    >>> complaint.save()

Resolve complaint with a coupon::

    >>> action = complaint.actions.new(action='promotion_coupon')
    >>> action.promotion_coupon = coupon
    >>> action.promotion_coupon_number = "DISC50"
    >>> action.promotion_coupon_duration = dt.timedelta(days=30)
    >>> complaint.click('wait')
    >>> complaint.click('approve')
    >>> complaint.state
    'done'

    >>> action, = complaint.actions
    >>> coupon_number = action.result
    >>> coupon_number.number
    'DISC50'
    >>> assertEqual(coupon_number.coupon, coupon)
    >>> assertEqual(
    ...     coupon_number.end_date - coupon_number.start_date, dt.timedelta(days=30))
