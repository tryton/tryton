=============================
Sale Point Gift Card Scenario
=============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)

Activate modules::

    >>> config = activate_modules(['sale_gift_card', 'sale_point'])

    >>> Account = Model.get('account.account')
    >>> AccountConfig = Model.get('account.configuration')
    >>> GiftCard = Model.get('sale.gift_card')
    >>> Journal = Model.get('account.journal')
    >>> Location = Model.get('stock.location')
    >>> POS = Model.get('sale.point')
    >>> PaymentMethod = Model.get('sale.point.payment.method')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUoM = Model.get('product.uom')
    >>> Sale = Model.get('sale.point.sale')
    >>> SaleConfig = Model.get('sale.configuration')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> SequenceType = Model.get('ir.sequence.type')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Setup gift card accounting::

    >>> gift_card_type, = accounts['payable'].type.duplicate(
    ...     {'gift_card': True})
    >>> gift_card_revenue = Account(name="Gift Card")
    >>> gift_card_revenue.type = gift_card_type
    >>> gift_card_revenue.deferral = True
    >>> gift_card_revenue.save()
    >>> account_config = AccountConfig(1)
    >>> account_config.gift_card_account_revenue = gift_card_revenue
    >>> account_config.save()

Set gift card sequence::

    >>> sale_config = SaleConfig(1)
    >>> gift_card_sequence = Sequence(name="Gift Card")
    >>> gift_card_sequence.sequence_type, = SequenceType.find([
    ...         ('name', '=', "Gift Card"),
    ...         ])
    >>> gift_card_sequence.type = 'hexadecimal timestamp'
    >>> gift_card_sequence.save()
    >>> sale_config.gift_card_sequence = gift_card_sequence
    >>> sale_config.save()

Create gift card product::

    >>> unit, = ProductUoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = "Gift Card"
    >>> template.type = 'service'
    >>> template.default_uom = unit
    >>> template.salable = True
    >>> template.gift_card = True
    >>> template.list_price = Decimal('50')
    >>> template.save()
    >>> gift_card_product, = template.products

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUoM.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.account_category = account_category
    >>> template.gross_price = Decimal('50.0000')
    >>> template.save()
    >>> product, = template.products

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

Create a payment method::

    >>> payment_method = PaymentMethod(name="Cash")
    >>> payment_method.account = accounts['cash']
    >>> payment_method.save()

Make a sale::

    >>> sale = Sale(point=pos)
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 10
    >>> sale.save()
    >>> sale.total
    Decimal('500.00')

Overpay::

    >>> payment = Wizard('sale.point.sale.pay', [sale])
    >>> payment.form.method = payment_method
    >>> payment.form.amount = Decimal('600.00')
    >>> payment.execute('pay')

    >>> payment.form.amount
    Decimal('-100.00')

Return change with a gift card::

    >>> payment.execute('gift_card')
    >>> payment.form.product = gift_card_product
    >>> payment.form.amount
    Decimal('100.00')
    >>> payment.execute('add_gift_card')

    >>> sale.state
    'done'

Check gift card::

    >>> gift_card, = GiftCard.find([])
    >>> gift_card.value
    Decimal('100.00')
    >>> gift_card.currency == sale.currency
    True

Print gift card::

    >>> gift_card_report = Report('sale.gift_card')
    >>> bool(gift_card_report.execute([sale]))
    True

Post sale::

    >>> sale.click('post')
    >>> sale.state
    'posted'

Make a second sale and pay with gift card::

    >>> sale = Sale(point=pos)
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> sale.gift_cards.append(GiftCard(gift_card.id))
    >>> sale.save()
    >>> sale.total
    Decimal('150.00')

Pay::

    >>> payment = Wizard('sale.point.sale.pay', [sale])
    >>> payment.form.method = payment_method
    >>> payment.execute('pay')

    >>> sale.state
    'done'
    >>> sale.total
    Decimal('150.00')

Check gift card::

    >>> gift_card.reload()
    >>> gift_card.spent_on == sale
    True

Post sale::

    >>> sale.click('post')
    >>> sale.state
    'posted'
