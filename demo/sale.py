# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime as dt
import random

from dateutil.relativedelta import relativedelta

from proteus import Model


def setup(config, modules, company, customers):
    Sale = Model.get('sale.sale')
    Product = Model.get('product.product')

    all_products = Product.find([
            ('salable', '=', True),
            ])
    today = dt.date.today()
    sale_date = today + relativedelta(months=-2)
    while sale_date <= today + relativedelta(days=10):
        for _ in range(random.randint(1, 5)):
            customer = random.choice(customers)
            sale = Sale()
            sale.party = customer
            sale.sale_date = sale_date
            products = random.sample(
                all_products, random.randint(1, len(all_products)))
            for product in products:
                sale_line = sale.lines.new()
                sale_line.product = product
                sale_line.quantity = random.randint(1, 50)
            sale.save()
            if sale_date <= today:
                threshold = 2. / 3.
            else:
                threshold = 1. / 3.
            if random.random() <= threshold:
                sale.click('quote')
                if random.random() <= threshold:
                    sale.click('confirm')
                    if random.random() <= threshold:
                        sale.click('process')
                elif random.random() >= threshold:
                    sale.click('cancel')
            elif random.random() >= threshold:
                sale.click('cancel')
        sale_date += relativedelta(days=random.randint(1, 3))
