=================================
Quality Control Shipment Scenario
=================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(['quality', 'stock'], create_company)

    >>> Control = Model.get('quality.control')
    >>> Inspection = Model.get('quality.inspection')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> Shipment = Model.get('stock.shipment.in')
    >>> UoM = Model.get('product.uom')

Create party::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()

Create product::

    >>> unit, = UoM.find([('name', '=', "Unit")])
    >>> product_template = ProductTemplate(name="Product")
    >>> product_template.default_uom = unit
    >>> product_template.type = 'goods'
    >>> product_template.save()
    >>> product, = product_template.products

Create control::

    >>> control = Control(name="Check")
    >>> control.operations = ['stock.shipment.in:receive']
    >>> point = control.points.new()
    >>> point.string = "Test"
    >>> point.type_ = 'float'
    >>> point.tolerance_lower = 20
    >>> point.tolerance_upper = 50
    >>> control.save()

Receive product which fails quality inspection::

    >>> shipment = Shipment(supplier=supplier)
    >>> move = shipment.incoming_moves.new()
    >>> move.from_location = shipment.supplier_location
    >>> move.to_location = shipment.warehouse_input
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.unit_price = Decimal('5.0000')
    >>> move.currency = shipment.company.currency
    >>> shipment.save()
    >>> shipment.state
    'draft'

    >>> inspect = shipment.click('receive')
    >>> inspect.form.points = {'test': 60}
    >>> inspect.execute('save')
    >>> inspect.state
    'end'
    >>> shipment.state
    'draft'

    >>> inspection, = Inspection.find([])
    >>> inspection.state
    'failed'

    >>> shipment.click('receive')
    Traceback (most recent call last):
        ...
    InspectionError: ...

Receive a product that passes quantity inspection::

    >>> inspection.click('pass_')
    >>> inspection.state
    'passed'

    >>> shipment.click('receive')
    >>> shipment.state
    'received'
