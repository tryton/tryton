=====================================================
Sale Product Recommendation Association Rule Scenario
=====================================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(
    ...     'sale_product_recommendation_association_rule',
    ...     create_company)

    >>> Cron = Model.get('ir.cron')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductAssociationRule = Model.get('sale.product.association.rule')
    >>> Sale = Model.get('sale.sale')
    >>> SaleConfiguration = Model.get('sale.configuration')
    >>> Uom = Model.get('product.uom')

Configuration association rule::

    >>> sale_config = SaleConfiguration(1)
    >>> sale_config.product_association_rule_transactions_up_to = (
    ...     dt.timedelta(days=30))
    >>> sale_config.product_recommendation_method = 'association_rule'
    >>> sale_config.save()

Create customer::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create products::

    >>> unit, = Uom.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = "Egg"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.recommendable = True
    >>> template.list_price = Decimal('1')
    >>> template.save()
    >>> egg, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Bacon"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.recommendable = True
    >>> template.list_price = Decimal('5')
    >>> template.save()
    >>> bacon, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Soup"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.recommendable = True
    >>> template.list_price = Decimal('8')
    >>> template.save()
    >>> soup, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Apple"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.recommendable = True
    >>> template.list_price = Decimal('3')
    >>> template.save()
    >>> apple, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Banana"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.recommendable = True
    >>> template.list_price = Decimal('4')
    >>> template.save()
    >>> banana, = template.products

Create some sales::

    >>> sale = Sale(party=customer)
    >>> line = sale.lines.new(product=egg)
    >>> line.quantity = 12
    >>> line = sale.lines.new(product=bacon)
    >>> line.quantity = 2
    >>> line = sale.lines.new(product=soup)
    >>> line.quantity = 1
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'confirmed'

    >>> sale = Sale(party=customer)
    >>> line = sale.lines.new(product=egg)
    >>> line.quantity = 6
    >>> line = sale.lines.new(product=bacon)
    >>> line.quantity = 4
    >>> line = sale.lines.new(product=apple)
    >>> line.quantity = 5
    >>> sale.click('quote')
    >>> sale.click('confirm')

    >>> sale = Sale(party=customer)
    >>> line = sale.lines.new(product=soup)
    >>> line.quantity = 3
    >>> line = sale.lines.new(product=bacon)
    >>> line.quantity = 2
    >>> line = sale.lines.new(product=banana)
    >>> line.quantity = 5
    >>> sale.click('quote')
    >>> sale.click('confirm')

    >>> sale = Sale(party=customer)
    >>> line = sale.lines.new(product=apple)
    >>> line.quantity = 2
    >>> line = sale.lines.new(product=banana)
    >>> line.quantity = 2
    >>> sale.click('quote')
    >>> sale.click('confirm')

Compute association rules::

    >>> cron_compute_association_rule, = Cron.find([
    ...     ('method', '=', 'sale.product.association.rule|compute'),
    ...     ])
    >>> cron_compute_association_rule.click('run_once')

    >>> bool(ProductAssociationRule.find([]))
    True

Test recommended products::

    >>> sale = Sale(party=customer)
    >>> [p.name for p in sale.recommended_products]
    []
    >>> line = sale.lines.new(product=apple)
    >>> [p.name for p in sale.recommended_products]
    []
    >>> line = sale.lines.new(product=egg)
    >>> [p.name for p in sale.recommended_products]
    ['Bacon']
