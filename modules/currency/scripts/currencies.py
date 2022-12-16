#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import sys
import pycountry

symbols = {
    'AFN': '؋',
    'ARS': '$',
    'AWG': 'ƒ',
    'AZN': 'ман',
    'BSD': '$',
    'THB': '฿',
    'PAB': 'B/.',
    'BBD': '$',
    'BYR': 'p.',
    'BZD': 'BZ$',
    'BMD': '$',
    'VEF': 'Bs',
    'BOB': '$b',
    'BRL': 'R$',
    'BGN': 'лв',
    'CAD': '$',
    'KYD': '$',
    'CLP': '$',
    'COP': '$',
    'BAM': 'KM',
    'NIO': 'C$',
    'CRC': '₡',
    'HRK': 'kn',
    'CUP': '₱',
    'CZK': 'Kč',
    'DKK': 'kr',
    'MKD': 'ден',
    'DOP': 'RD$',
    'VND': '₫',
    'XCD': '$',
    'EGP': '£',
    'EUR': '€',
    'FJD': '$',
    'HUF': 'Ft',
    'GBP': '£',
    'GIP': '£',
    'PYG': 'Gs',
    'GYD': '$',
    'HKD': 'HK$',
    'UAH': '₴',
    'ISK': 'kr',
    'INR': '₨',
    'IRR': '﷼',
    'JMD': 'J$',
    'LAK': '₭',
    'EEK': 'kr',
    'LBP': '£',
    'ALL': 'Lek',
    'HNL': 'L',
    'LRD': '$',
    'LTL': 'Lt',
    'MYR': 'RM',
    'MUR': '₨',
    'MZN': 'MT',
    'NGN': '₦',
    'NAD': '$',
    'NPR': '₨',
    'ANG': 'ƒ',
    'ILS': '₪',
    'RON': 'lei',
    'TWD': 'NT$',
    'TRY': 'YTL',
    'NZD': '$',
    'KPW': '₩',
    'NOK': 'kr',
    'PEN': 'S/.',
    'PKR': '₨',
    'UYU': '$U',
    'PHP': 'Php',
    'BWP': 'P',
    'QAR': '﷼',
    'GTQ': 'Q',
    'ZAR': 'R',
    'OMR': '﷼',
    'KHR': '៛',
    'IDR': 'Rp',
    'RUB': 'руб',
    'SHP': '£',
    'SAR': '﷼',
    'RSD': 'Дин.',
    'SCR': '₨',
    'SGD': '$',
    'SBD': '$',
    'KGS': 'лв',
    'SOS': 'S',
    'LKR': '₨',
    'SRD': '$',
    'SEK': 'kr',
    'CHF': 'CHF',
    'KZT': 'лв',
    'TTD': 'TT$',
    'MNT': '₮',
    'USD': '$',
    'UZS': 'лв',
    'YER': '﷼',
    'JPY': '¥',
    'CNY': '元',
    'ZWD': 'Z$',
    'PLN': 'zł',
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

sys.stdout.write('<?xml version="1.0"?>\n')
sys.stdout.write('<tryton>\n')
sys.stdout.write('    <data skiptest="1" grouped="1">\n')

for currency in pycountry.currencies:
    extend = ''
    if currency.alpha_3 in currencies:
        extend = '''
            <field name="rounding" eval="%(rounding)s"/>
            <field name="digits" eval="%(digits)s"/>''' % (
                currencies[currency.alpha_3])
    record = '''
        <record model="currency.currency" id="%s">
            <field name="name">%s</field>
            <field name="code">%s</field>
            <field name="numeric_code">%s</field>
            <field name="symbol">%s</field>%s
        </record>\n''' % (currency.alpha_3.lower(), currency.name,
                currency.alpha_3, currency.numeric,
                symbols.get(currency.alpha_3, currency.alpha_3), extend)
    sys.stdout.write(record.encode('utf-8'))

sys.stdout.write('    </data>\n')
sys.stdout.write('</tryton>\n')
