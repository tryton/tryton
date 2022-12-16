=============================
Sale Gift Card Goods Scenario
=============================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)

Activate modules::

    >>> config = activate_modules('sale_gift_card')

    >>> Account = Model.get('account.account')
    >>> AccountConfig = Model.get('account.configuration')
    >>> GiftCard = Model.get('sale.gift_card')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUoM = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

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

Create gift card product::

    >>> unit, = ProductUoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = "Gift Card"
    >>> template.type = 'goods'
    >>> template.default_uom = unit
    >>> template.salable = True
    >>> template.gift_card = True
    >>> template.list_price = Decimal('20')
    >>> template.save()
    >>> gift_card, = template.products

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create a product::

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.salable = True
    >>> template.list_price = Decimal('100')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create parties::

    >>> customer1 = Party(name='Customer 1')
    >>> customer1.save()
    >>> customer2 = Party(name='Customer 2')
    >>> customer2.save()

Sell 1 gift cards::

    >>> sale = Sale()
    >>> sale.party = customer1
    >>> line = sale.lines.new()
    >>> line.product = gift_card
    >>> line.quantity = 1
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check gift cards::

    >>> cards = GiftCard.find([])
    >>> len(cards)
    0

Check invoice::

    >>> invoice, = sale.invoices
    >>> line, = invoice.lines
    >>> line.account == gift_card_revenue
    True

Ship the gift card::

    >>> shipment, = sale.shipments
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    MoveGiftCardValidationError: ...
    >>> move, = shipment.outgoing_moves
    >>> gift_card = move.gift_cards.new(product=gift_card)
    >>> gift_card.number = "1234"
    >>> gift_card.value
    Decimal('20.00')
    >>> move.save()
    >>> shipment.click('done')
