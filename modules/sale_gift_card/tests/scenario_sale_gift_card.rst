=======================
Sale Gift Card Scenario
=======================

Imports::

    >>> from decimal import Decimal
    >>> from unittest.mock import patch

    >>> from proteus import Model, Report
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.sale_gift_card import sale
    >>> from trytond.tests.tools import activate_modules, assertEqual

Patch send_message_transactional::

    >>> smtp_calls = patch.object(
    ...     sale, 'send_message_transactional').start()

Activate modules::

    >>> config = activate_modules('sale_gift_card', create_company, create_chart)

    >>> Account = Model.get('account.account')
    >>> AccountConfig = Model.get('account.configuration')
    >>> GiftCard = Model.get('sale.gift_card')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUoM = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')
    >>> SaleConfig = Model.get('sale.configuration')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceType = Model.get('ir.sequence.type')

Get accounts::

    >>> accounts = get_accounts()

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

Sell 2 gift cards::

    >>> sale = Sale()
    >>> sale.party = customer1
    >>> line = sale.lines.new()
    >>> line.product = gift_card
    >>> line.quantity = 2
    >>> line.gift_card_email = "customer@example.com"
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check gift cards::

    >>> cards = GiftCard.find([])
    >>> len(cards)
    2
    >>> card = cards[-1]
    >>> assertEqual(card.product, gift_card)
    >>> card.value
    Decimal('50.00')
    >>> bool(card.origin)
    True
    >>> bool(card.spent_on)
    False
    >>> smtp_calls.call_count
    2
    >>> msg, = smtp_calls.call_args[0]
    >>> card.number in msg.get_body().get_content()
    True

Print gift cards::

    >>> gift_card_report = Report('sale.gift_card')
    >>> bool(gift_card_report.execute([sale]))
    True

Check invoice::

    >>> invoice, = sale.invoices
    >>> line, = invoice.lines
    >>> assertEqual(line.account, gift_card_revenue)

Redeem a gift card to buy a product::

    >>> sale = Sale()
    >>> sale.party = customer2
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.gift_cards.append(GiftCard(card.id))
    >>> sale.save()
    >>> sale.total_amount
    Decimal('100.00')
    >>> sale.click('quote')
    >>> len(sale.lines)
    2
    >>> sale.total_amount
    Decimal('50.00')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check gift card::

    >>> card.reload()
    >>> assertEqual(card.spent_on, sale)

Check the invoice::

    >>> invoice, = sale.invoices
    >>> len(invoice.lines)
    2
    >>> invoice.total_amount
    Decimal('50.00')
    >>> gift_card_line, = [l for l in invoice.lines if l.product == gift_card]
    >>> gift_card_line.quantity
    -1.0
    >>> assertEqual(gift_card_line.account, gift_card_revenue)
