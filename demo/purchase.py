# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
import random

from dateutil.relativedelta import relativedelta

from proteus import Model


def setup(config, modules, company, suppliers):
    Purchase = Model.get('purchase.purchase')
    Product = Model.get('product.product')

    all_products = Product.find([
            ('purchasable', '=', True),
            ])
    today = dt.date.today()
    purchase_date = today - relativedelta(days=60)
    while purchase_date <= today + relativedelta(days=20):
        supplier = random.choice(suppliers)
        purchase = Purchase()
        purchase.party = supplier
        purchase.purchase_date = purchase_date
        products = random.sample(
            all_products, random.randint(1, len(all_products)))
        for product in products:
            purchase_line = purchase.lines.new()
            purchase_line.product = product
            purchase_line.quantity = random.randint(20, 100)
            purchase_line.unit_price = product.cost_price
        purchase.save()
        threshold = 2. / 3.
        if random.random() <= threshold:
            purchase.click('quote')
            if random.random() <= threshold:
                purchase.click('confirm')
                purchase.click('process')
        elif random.choice([True, False]):
            purchase.click('cancel')
        purchase_date += relativedelta(days=random.randint(5, 10))
