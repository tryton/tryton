========================
Product Replace Scenario
========================

Imports::

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules, assertEqual, assertFalse

Activate modules::

    >>> config = activate_modules('product')

    >>> Cron = Model.get('ir.cron')
    >>> ProductTemplate = Model.get('product.template')
    >>> UoM = Model.get('product.uom')

Get units::

    >>> unit, = UoM.find([('name', '=', "Unit")])
    >>> kg, = UoM.find([('name', '=', "Kilogram")])

Create a product::

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.type = 'goods'
    >>> template.default_uom = kg
    >>> template.save()
    >>> product1, = template.products

Create a second product::

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.type = 'service'
    >>> template.default_uom = unit
    >>> template.save()
    >>> product2, = template.products

Try to replace goods with service::

    >>> replace = Wizard('product.product.replace', models=[product1])
    >>> assertEqual(replace.form.source, product1)
    >>> replace.form.destination = product2
    >>> replace.execute('replace')
    Traceback (most recent call last):
        ...
    DomainValidationError: ...

Try to replace with different categories of unit of measure::

    >>> product2.template.type = 'goods'
    >>> product2.template.save()

    >>> replace = Wizard('product.product.replace', models=[product1])
    >>> replace.form.destination = product2
    >>> replace.execute('replace')
    Traceback (most recent call last):
        ...
    DomainValidationError: ...

Replace product::

    >>> product2.template.default_uom = kg
    >>> product2.template.save()

    >>> replace = Wizard('product.product.replace', models=[product1])
    >>> replace.form.destination = product2
    >>> replace.execute('replace')
    >>> assertEqual(product1.replaced_by, product2)
    >>> assertFalse(product1.active)

Cron task deactivate replaced product::

    >>> product1.active = True
    >>> product1.save()

    >>> deactivate_replaced, = Cron.find([
    ...     ('method', '=', 'product.product|deactivate_replaced'),
    ...     ])
    >>> deactivate_replaced.click('run_once')

    >>> product1.reload()
    >>> assertFalse(product1.active)
