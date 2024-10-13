# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
import random
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from proteus import Model


def setup(config, activated, company):
    BOM = Model.get('production.bom')
    Production = Model.get('production')
    ProductTemplate = Model.get('product.template')
    Category = Model.get('product.category')
    Uom = Model.get('product.uom')

    unit, = Uom.find([('name', '=', 'Unit')])

    if 'account_product' in activated:
        Account = Model.get('account.account')
        expense, = Account.find([
                ('company', '=', company.id),
                ('code', '=', '5.1.1'),
                ])
        revenue, = Account.find([
                ('company', '=', company.id),
                ('code', '=', '4.1.1'),
                ])
        account_category = Category(name="Computers", accounting=True)
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.save()

    def create_product(name, list_price, cost_price):
        template = ProductTemplate(name=name)
        template.default_uom = unit
        template.type = 'goods'
        template.list_price = list_price
        template.cost_price = cost_price
        if 'account_product' in activated:
            template.account_category = account_category
        template.save()
        return template.products[0]

    bom = BOM(name='Computer rev1')

    input_ = bom.inputs.new()
    tower = create_product('Tower', Decimal(400), Decimal(250))
    input_.product = tower
    input_.quantity = 1

    input_ = bom.inputs.new()
    input_.product = create_product('Keyboard', Decimal(30), Decimal(10))
    input_.quantity = 1

    input_ = bom.inputs.new()
    input_.product = create_product('Mouse', Decimal(10), Decimal(5))
    input_.quantity = 1

    input_ = bom.inputs.new()
    input_.product = create_product('Screen', Decimal(300), Decimal(200))
    input_.quantity = 1

    output = bom.outputs.new()
    computer = create_product('Computer', Decimal(750), Decimal(465))
    computer.template.producible = True
    computer.template.save()
    output.product = computer
    output.quantity = 1

    bom.save()
    computer.boms.new(bom=bom)
    computer.save()

    if 'production_routing' in activated:
        setup_routing(config, activated, company)

    if 'production_work' in activated:
        WorkCenter = Model.get('production.work.center')
        WorkCycle = Model.get('production.work.cycle')
        setup_production_work(config, activated, company)
        work_centers = WorkCenter.find([('parent', '=', None)])

    today = dt.date.today()
    production_date = today + relativedelta(months=-1)
    while production_date <= today + relativedelta(days=20):
        for _ in range(random.randint(0, 3)):
            production = Production()
            production.effective_date = production_date
            production.product = computer
            production.quantity = random.randint(1, 40)
            production.bom = computer.boms[0].bom

            if 'production_routing' in activated:
                production.routing = computer.boms[0].routing

            if 'production_work' in activated:
                production.work_center = random.choice(work_centers)

            production.save()

            if (production_date < today) or (random.random() <= 1. / 3.):
                production.click('wait')
                if production_date < today:
                    production.click('assign_force')
                    production.click('run')
                    if random.random() <= 2. / 3.:
                        if 'production_work' in activated:
                            for work in production.works:
                                for _ in range(0, random.randint(1, 2)):
                                    cycle = WorkCycle(
                                        work=work,
                                        duration=dt.timedelta(
                                            seconds=random.randint(60, 3600)),
                                        )
                                    cycle.save()
                                    cycle.click('run')
                                    cycle.click('do')
                        output, = production.outputs
                        output.unit_price = (production.cost
                            / Decimal(production.quantity)
                            ).quantize(Decimal('0.0001'))
                        production.click('do')
            production_date += relativedelta(days=random.randint(1, 3))


def setup_routing(config, activated, company):
    Routing = Model.get('production.routing')
    Operation = Model.get('production.routing.operation')
    Product = Model.get('product.product')

    routing = Routing(name='Computer routing rev1')

    operation1 = Operation(name='Assemble pieces')
    operation1.save()
    step1 = routing.steps.new()
    step1.operation = operation1

    operation2 = Operation(name='Install software')
    operation2.save()
    step2 = routing.steps.new()
    step2.operation = operation2

    operation3 = Operation(name='Test')
    operation3.save()
    step3 = routing.steps.new()
    step3.operation = operation3

    operation4 = Operation(name='Package')
    operation4.save()
    step4 = routing.steps.new()
    step4.operation = operation4

    routing.boms.extend(routing.boms.find([('name', '=', 'Computer rev1')]))

    routing.save()

    computer, = Product.find([('name', '=', 'Computer')])
    bom, = computer.boms
    bom.routing = routing
    bom.save()


def setup_production_work(config, activated, company):
    WorkCenterCategory = Model.get('production.work.center.category')
    WorkCenter = Model.get('production.work.center')
    Operation = Model.get('production.routing.operation')

    assembly = WorkCenterCategory(name='Assembly')
    assembly.save()
    operation, = Operation.find([('name', '=', 'Assemble pieces')])
    operation.work_center_category = assembly
    operation.save()

    installation = WorkCenterCategory(name='Installation')
    installation.save()
    operations = Operation.find([
            ('name', 'in', ['Install software', 'Test']),
            ])
    for operation in operations:
        operation.work_center_category = installation
    Operation.save(operations)

    packaging = WorkCenterCategory(name='Packaging')
    packaging.save()
    operation, = Operation.find([('name', '=', 'Package')])
    operation.work_center_category = packaging
    operation.save()

    lines = []
    for i in range(1, 4):
        line = WorkCenter(name='Line %i' % i)

        assembly_line = line.children.new()
        assembly_line.name = 'Assembly Line %i' % i
        assembly_line.category = assembly
        assembly_line.cost_method = 'cycle'
        assembly_line.cost_price = Decimal(20)

        installation_line = line.children.new()
        installation_line.name = 'Installation Line %i' % i
        installation_line.category = installation
        installation_line.cost_method = 'hour'
        installation_line.cost_price = Decimal(15)

        packaging_line = line.children.new()
        packaging_line.name = 'Packaging Line %i' % i
        packaging_line.category = packaging
        packaging_line.cost_method = 'hour'
        packaging_line.cost_price = Decimal(10)

        lines.append(line)
    WorkCenter.save(lines)
