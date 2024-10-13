# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from decimal import Decimal

from proteus import Model


def setup(config, modules, company=None):
    ProductTemplate = Model.get('product.template')
    Category = Model.get('product.category')
    Uom = Model.get('product.uom')

    if 'account_product' in modules:
        Account = Model.get('account.account')
        expense, = Account.find([
                ('company', '=', company.id),
                ('code', '=', '5.1.1'),
                ])
        revenue, = Account.find([
                ('company', '=', company.id),
                ('code', '=', '4.1.1'),
                ])
        account_category = Category(name="Papers", accounting=True)
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.save()

    papers = Category(name='Papers')
    papers.save()

    sizes = {}
    for format in ['A5', 'A4', 'A3', 'Letter', 'Legal', 'Ledger']:
        size = Category(name=format, parent=papers)
        if 'account_product' in modules:
            size.account_expense = expense
            size.account_revenue = revenue
        size.save()
        sizes[format] = size

    unit, = Uom.find([('name', '=', 'Unit')])

    margin = Decimal('1.01')
    for quantity in [250, 500]:
        for format, category in sizes.items():
            paper_template = ProductTemplate(name='%s Paper %s'
                % (format, quantity))
            paper_template.categories.append(Category(category.id))
            if 'account_product' in modules:
                paper_template.account_category = account_category
            paper_template.default_uom = unit
            paper_template.type = 'goods'
            paper_template.list_price = (Decimal('0.02') * quantity * margin
                ).quantize(Decimal('0.0001'))
            paper, = paper_template.products
            paper.cost_price = Decimal('0.01') * quantity
            if 'sale' in modules:
                paper_template.salable = True
            if 'purchase' in modules:
                paper_template.purchasable = True
            paper_template.save()
        margin *= margin
