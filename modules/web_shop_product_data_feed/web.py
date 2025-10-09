# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import csv
import fnmatch
import os
import shutil
import tempfile
import time
from functools import wraps
from string import Template

import trytond.config as config
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

_SUBSTITUTION_HELP = (
    "The following placeholders can be used:\n"
    "- ${id}\n"
    "- ${code}\n"
    "- ${name}\n"
    "- ${language}\n"
    )


def product_substitutions(func):
    @wraps(func)
    def wrapper(self, product, **substitutions):
        substitutions.setdefault('id', product.id)
        substitutions.setdefault('code', product.code or product.id)
        substitutions.setdefault('name', product.name)
        substitutions.setdefault('language', Transaction().language)
        return func(self, product, **substitutions)
    return wrapper


def _get_directory():
    database = Transaction().database.name
    directory = os.path.join(
        tempfile.gettempdir(), f'trytond/{database}/web_shop')
    os.makedirs(directory, mode=0o700, exist_ok=True)
    return directory


_duration = config.getint(
    'web_shop', 'product_data_feed_cache', default=60 * 60 * 24)


class Shop(metaclass=PoolMeta):
    __name__ = 'web.shop'

    product_url_template = fields.Char(
        "Product URL",
        help="The fallback template to generate the product URL.\n"
        + _SUBSTITUTION_HELP)
    product_image_url_template = fields.Char(
        "Product Image URL",
        help="The fallback template to generate the product image URL.\n"
        + _SUBSTITUTION_HELP
        + "- ${index}\n")

    @product_substitutions
    def product_url(self, product, **substitutions):
        for record in product.web_shop_urls:
            if record.shop == self and record.url:
                url = record.url
                break
        else:
            url = Template(self.product_url_template or '').substitute(
                **substitutions)
        return url

    @product_substitutions
    def product_image_url(self, product, index=0, **substitutions):
        images = [i for i in getattr(product, 'images_used', []) if i.web_shop]
        try:
            image = images[index]
        except IndexError:
            url = Template(self.product_image_url_template or '').substitute(
                index=index, **substitutions)
        else:
            url = image.get_image_url(_external=True, id=image.id)
        return url

    def get_context(self):
        context = super().get_context()
        if language := Transaction().context.get('_product_data_language'):
            context['language'] = language
        return context

    @classmethod
    def update_product_data_feed_csv(cls, shops=None):
        if shops is None:
            shops = cls.search([])

        directory = _get_directory()
        duration = config.getint(
            'web_shop', 'product_data_feed_cache', default=60 * 60 * 24)
        for shop in shops:
            for name in fnmatch.filter(
                    os.listdir(directory),
                    f'{shop.name}-{shop.id}-*.csv'):
                name = name[len(f'{shop.name}-{shop.id}-'):-len('.csv')]
                if '-' in name:
                    format, language = name.rsplit('-', 1)
                else:
                    format, language = name, None
                shop.product_data_feed_csv(
                    format, language=language, duration=duration / 2)

    def product_data_feed_csv(self, format, language=None, duration=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        transaction = Transaction()
        directory = _get_directory()
        if duration is None:
            duration = config.getint(
                'web_shop', 'product_data_feed_cache', default=60 * 60 * 24)
        if language:
            filename = f'{self.name}-{self.id}-{format}-{language}.csv'
        else:
            filename = f'{self.name}-{self.id}-{format}.csv'
        filename = os.path.join(directory, filename)

        # Fallback to the default language if it does not exist
        try:
            Lang.get(language)
        except ValueError:
            language = None

        try:
            if (time.time() - os.path.getmtime(filename)) < duration:
                return filename
        except OSError:
            # Create the file so cron will update it
            # even if this generation fails
            open(filename, 'a').close()

        with transaction.set_context(_product_data_language=language):
            products, prices, taxes = self.get_products()
            sale_prices, sale_taxes = prices, taxes

            context = self.get_context()
            with Transaction().set_context(_non_sale_price=True):
                sale_context = self.get_context()
                if context != sale_context:
                    _, prices, taxes = self.get_products()

        with tempfile.NamedTemporaryFile('w', delete=False) as fp, \
                transaction.set_context(context):
            writer = csv.DictWriter(
                fp, extrasaction='ignore',
                **self._product_data_feed_writer(format))
            writer.writeheader()
            sizes = self._product_data_feed_field_sizes(format)
            for product in products:
                if prices[product.id] is None:
                    continue
                price = prices[product.id] + (taxes.get(product.id) or 0)
                if sale_prices[product.id] is not None:
                    sale_price = (
                        sale_prices[product.id]
                        + (sale_taxes.get(product.id) or 0))
                else:
                    sale_price = price
                if not sale_price:
                    continue
                row = self._product_data_feed_row(product, price, sale_price)
                for field, size in sizes.items():
                    if field in row:
                        row[field] = (row[field] or '')[:size]
                writer.writerow(row)
            fp.flush()
            shutil.move(fp.name, filename)
        return filename

    def _product_data_feed_writer(self, format):
        fieldnames = [
            'id',
            'title',
            'description',
            'link',
            'image_link',
            'availability',
            'price',
            'sale_price',
            'google_product_category',
            'brand',
            'condition',
            'item_group_id',
            ]
        dialect = csv.excel
        if format == 'google':
            dialect = csv.excel_tab
            fieldnames.extend([
                    'unit_pricing_measure',
                    'unit_pricing_base_measure',
                    'product_type',
                    'gtin',
                    'mpn',
                    ])
        elif format == 'facebook':
            fieldnames.extend([
                    'fb_product_category',
                    ])
        return {
            'fieldnames': fieldnames,
            'dialect': dialect,
            }

    def _product_data_feed_row(self, product, price, sale_price):
        price = self.currency.round(price)
        sale_price = self.currency.round(sale_price)
        if ean := product.identifier_get('ean'):
            ean = ean.code
        if brand := product.identifier_get('brand'):
            brand = brand.code
        else:
            brand = self.company.party.name
        row = {
            'id': ean or product.code or str(product.id),
            'title': product.name.title(),
            'description': product.description,
            'link': self.product_url(product),
            'image_link': self.product_image_url(product),
            'availability': 'in stock',  # XXX
            'price': (
                f'{price} {self.currency.code}'
                if price > sale_price else
                f'{sale_price} {self.currency.code}'),
            'sale_price': (
                f'{sale_price} {self.currency.code}'
                if sale_price < price else ''),
            'google_product_category': (
                product.google_category.code if product.google_category
                else ''),
            'fb_product_category': (
                product.facebook_category.code if product.facebook_category
                else ''),
            # TODO: product_type
            'brand': brand,
            'gtin': ean,
            'condition': 'new',
            'item_group_id': (
                product.template.code if len(product.template.products) > 1
                else ''),
            }
        symbol = product.sale_uom.product_data_feed_symbol
        if symbol:
            row['unit_pricing_measure'] = f'1{symbol}'
            rounding = product.sale_uom.rounding
            if rounding != 1:
                row['unit_pricing_base_measure'] = f'{rounding}{symbol}'
        if mpn := product.identifier_get('mpn'):
            row['mpn'] = mpn.code
        return row

    def _product_data_feed_field_sizes(self, format):
        sizes = {
            'custom_label_0': 100,
            'custom_label_1': 100,
            'custom_label_2': 100,
            'custom_label_3': 100,
            'custom_label_4': 100,
            }
        if format == 'google':
            sizes.update({
                    'id': 50,
                    'title': 150,
                    'description': 5000,
                    'product_type': 750,
                    'brand': 70,
                    'gtin': 50,
                    'mpn': 70,
                    'ads_redirect': 2000,
                    })
        elif format == 'facebook':
            sizes.update({
                    'id': 100,
                    'title': 200,
                    'description': 9999,
                    'brand': 100,
                    })
        return sizes


class Shop_Kit(metaclass=PoolMeta):
    __name__ = 'web.shop'

    def _product_data_feed_writer(self, format):
        writer = super()._product_data_feed_writer(format)
        if format == 'google':
            writer['fieldnames'].append('is_bundle')
        return writer

    def _product_data_feed_row(self, product, price, sale_price):
        row = super()._product_data_feed_row(product, price, sale_price)
        row['is_bundle'] = product.type == 'kit'
        return row


class Shop_Measurement(metaclass=PoolMeta):
    __name__ = 'web.shop'

    def _product_data_feed_writer(self, format):
        writer = super()._product_data_feed_writer(format)
        if format == 'google':
            writer['fieldnames'].extend([
                    'product_length',
                    'product_width',
                    'product_height',
                    'product_weight',
                    ])
        return writer

    def _product_data_feed_carrier_cost(
            self, product, country, carrier, price):
        pool = Pool()
        UoM = pool.get('product.uom')
        context = {}
        if (carrier.carrier_cost_method == 'weight'
                and self.product.weight):
            context['weights'] = [
                UoM.compute_qty(
                    product.weight_uom, product.weight, carrier.weight_uom,
                    round=False),
                ]
        with Transaction().set_context(context=context):
            return super()._product_data_feed_carrier_cost(
                product, country, carrier, price)

    def _product_data_feed_row(self, product, price, sale_price):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        UoM = pool.get('product.uom')

        cm = UoM(ModelData.get_id('product', 'uom_centimeter'))
        kg = UoM(ModelData.get_id('product', 'uom_kilogram'))
        gr = UoM(ModelData.get_id('product', 'uom_gram'))

        row = super()._product_data_feed_row(product, price, sale_price)

        if product.length:
            length = UoM.compute_qty(
                product.length_uom, product.length, cm)
            if 1 <= length <= 3000:
                row['product_length'] = f'{length} {cm.symbol}'
        if product.width:
            width = UoM.compute_qty(
                product.width_uom, product.width, cm)
            if 1 <= width <= 3000:
                row['product_width'] = f'{width} {cm.symbol}'
        if product.height:
            height = UoM.compute_qty(
                product.height_uom, product.height, cm)
            if 1 <= height <= 3000:
                row['product_height'] = f'{height} {cm.symbol}'
        if product.weight:
            for unit in {kg, gr}:
                weight = UoM.compute_qty(
                    product.weight_uom, product.weight, unit)
                if 1 <= weight <= 2000:
                    row['product_weight'] = f'{weight} {unit.symbol}'
                    break
        return row


class Shop_ShipmentCost(metaclass=PoolMeta):
    __name__ = 'web.shop'

    def _product_data_feed_writer(self, format):
        writer = super()._product_data_feed_writer(format)
        writer['fieldnames'].extend([
                'shipping',
                ])
        return writer

    def _product_data_feed_carrier_selection(
            self, product, country, **pattern):
        pool = Pool()
        CarrierSelection = pool.get('carrier.selection')
        if (self.warehouse
                and self.warehouse.address
                and self.warehouse.address.country):
            pattern.setdefault(
                'from_country', self.warehouse.address.country.id)
        else:
            pattern.setdefault('from_country')
        pattern.setdefault('to_country', country.id)
        return CarrierSelection.get_carriers(pattern)

    def _product_data_feed_carrier_cost(
            self, product, country, carrier, price, pattern=None):
        pool = Pool()
        Currency = pool.get('currency.currency')
        Date = pool.get('ir.date')
        Tax = pool.get('account.tax')
        if pattern is None:
            pattern = {}

        today = Date.today()
        context = {}
        if carrier.carrier_cost_method == 'percentage':
            context['amount'] = price
            context['currency'] = self.currency.id
        with Transaction().set_context(context=context):
            cost, currency_id = carrier.get_sale_price()
        if cost is None:
            return
        customer_tax_rule = self._customer_taxe_rule()
        taxes = set()
        for tax in carrier.carrier_product.customer_taxes_used:
            if customer_tax_rule:
                tax_ids = customer_tax_rule.apply(tax, pattern)
                if tax_ids:
                    taxes.update(tax_ids)
                continue
            taxes.add(tax.id)
        if customer_tax_rule:
            tax_ids = customer_tax_rule.apply(None, pattern)
            if tax_ids:
                taxes.update(tax_ids)
        taxes = Tax.browse(taxes)
        l_taxes = Tax.compute(taxes, cost, 1, today)
        for l_tax in l_taxes:
            cost += l_tax['amount']
        return Currency.compute(
            Currency(currency_id), cost, self.currency)

    def _product_data_feed_row(self, product, price, sale_price):
        row = super()._product_data_feed_row(product, price, sale_price)

        shipping = []
        for country in self.countries:
            for carrier in self._product_data_feed_carrier_selection(
                    product, country):
                cost = self._product_data_feed_carrier_cost(
                    product, country, carrier, price)
                if cost is not None:
                    shipping.append(
                        f'{country.code}::{carrier.carrier_product.name}:'
                        f'{cost} {self.currency.code}')
        row['shipping'] = ','.join(shipping)
        return row


class Shop_TaxRuleCountry(metaclass=PoolMeta):
    __name__ = 'web.shop'

    def _product_data_feed_carrier_cost(
            self, product, country, carrier, price, pattern=None):
        pattern = pattern.copy() if pattern is not None else {}
        if (self.warehouse
                and self.warehouse.address
                and self.warehouse.address.country):
            pattern.setdefault(
                'from_country', self.warehouse.address.country.id)
        else:
            pattern.setdefault('from_country')
        pattern.setdefault('to_country', country.id)
        return super()._product_data_feed_carrier_cost(
            product, country, carrier, price, pattern=pattern)
