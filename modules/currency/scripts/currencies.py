#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import sys
import pycountry

symbols = {
    'AFN': u'؋',
    'ARS': u'$',
    'AWG': u'ƒ',
    'AZN': u'ман',
    'BSD': u'$',
    'THB': u'฿',
    'PAB': u'B/.',
    'BBD': u'$',
    'BYR': u'p.',
    'BZD': u'BZ$',
    'BMD': u'$',
    'VEF': u'Bs',
    'BOB': u'$b',
    'BRL': u'R$',
    'BGN': u'лв',
    'CAD': u'$',
    'KYD': u'$',
    'CLP': u'$',
    'COP': u'$',
    'BAM': u'KM',
    'NIO': u'C$',
    'CRC': u'₡',
    'HRK': u'kn',
    'CUP': u'₱',
    'CZK': u'Kč',
    'DKK': u'kr',
    'MKD': u'ден',
    'DOP': u'RD$',
    'VND': u'₫',
    'XCD': u'$',
    'EGP': u'£',
    'EUR': u'€',
    'FJD': u'$',
    'HUF': u'Ft',
    'GBP': u'£',
    'GIP': u'£',
    'PYG': u'Gs',
    'GYD': u'$',
    'HKD': u'HK$',
    'UAH': u'₴',
    'ISK': u'kr',
    'INR': u'₨',
    'IRR': u'﷼',
    'JMD': u'J$',
    'LAK': u'₭',
    'EEK': u'kr',
    'LBP': u'£',
    'ALL': u'Lek',
    'HNL': u'L',
    'LRD': u'$',
    'LTL': u'Lt',
    'MYR': u'RM',
    'MUR': u'₨',
    'MZN': u'MT',
    'NGN': u'₦',
    'NAD': u'$',
    'NPR': u'₨',
    'ANG': u'ƒ',
    'ILS': u'₪',
    'RON': u'lei',
    'TWD': u'NT$',
    'TRY': u'YTL',
    'NZD': u'$',
    'KPW': u'₩',
    'NOK': u'kr',
    'PEN': u'S/.',
    'PKR': u'₨',
    'UYU': u'$U',
    'PHP': u'Php',
    'BWP': u'P',
    'QAR': u'﷼',
    'GTQ': u'Q',
    'ZAR': u'R',
    'OMR': u'﷼',
    'KHR': u'៛',
    'IDR': u'Rp',
    'RUB': u'руб',
    'SHP': u'£',
    'SAR': u'﷼',
    'RSD': u'Дин.',
    'SCR': u'₨',
    'SGD': u'$',
    'SBD': u'$',
    'KGS': u'лв',
    'SOS': u'S',
    'LKR': u'₨',
    'SRD': u'$',
    'SEK': u'kr',
    'CHF': u'CHF',
    'KZT': u'лв',
    'TTD': u'TT$',
    'MNT': u'₮',
    'USD': u'$',
    'UZS': u'лв',
    'YER': u'﷼',
    'JPY': u'¥',
    'CNY': u'元',
    'ZWD': u'Z$',
    'PLN': u'zł',
}

currencies = {
    'EUR': {
        'rounding': "Decimal('0.01')",
        'digits': '2',
        },
    'GBP': {
        'rounding': "Decimal('0.01')",
        'digits': '2',
        },
    'CHF': {
        'rounding': "Decimal('0.01')",
        'digits': '2',
        },
    'USD': {
        'rounding': "Decimal('0.01')",
        'digits': '2',
        },
    'ARS': {
        'rounding': "Decimal('0.01')",
        'digits': '2',
        },
}

sys.stdout.write(u'<?xml version="1.0"?>\n')
sys.stdout.write(u'<tryton>\n')
sys.stdout.write(u'    <data skiptest="1" grouped="1">\n')

for currency in pycountry.currencies:
    extend = ''
    if currency.alpha_3 in currencies:
        extend = u'''
            <field name="rounding" eval="%(rounding)s"/>
            <field name="digits" eval="%(digits)s"/>''' % (
                currencies[currency.alpha_3])
    record = u'''
        <record model="currency.currency" id="%s">
            <field name="name">%s</field>
            <field name="code">%s</field>
            <field name="numeric_code">%s</field>
            <field name="symbol">%s</field>%s
        </record>\n''' % (currency.alpha_3.lower(), currency.name,
                currency.alpha_3, currency.numeric,
                symbols.get(currency.alpha_3, currency.alpha_3), extend)
    sys.stdout.write(record.encode('utf-8'))

sys.stdout.write(u'    </data>\n')
sys.stdout.write(u'</tryton>\n')
