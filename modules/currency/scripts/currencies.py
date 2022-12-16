#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

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
        'p_cs_precedes': 'False',
        'n_cs_precedes': 'False',
        'p_sep_by_space': 'True',
        'n_sep_by_space': 'True',
        'mon_grouping': '[3, 3, 0]',
        'mon_decimal_point': ',',
        'mon_thousands_sep': ' ',
        'p_sign_posn': '1',
        'n_sign_posn': '1',
        'negative_sign': '-',
        'positive_sign': '',
        },
    'GBP': {
        'rounding': "Decimal('0.01')",
        'digits': '2',
        'p_cs_precedes': 'True',
        'n_cs_precedes': 'True',
        'p_sep_by_space': 'False',
        'n_sep_by_space': 'False',
        'mon_grouping': '[]',
        'mon_decimal_point': '.',
        'mon_thousands_sep': ',',
        'p_sign_posn': '1',
        'n_sign_posn': '1',
        'negative_sign': '-',
        'positive_sign': '',
        },
    'CHF': {
        'rounding': "Decimal('0.01')",
        'digits': '2',
        'p_cs_precedes': 'False',
        'n_cs_precedes': 'False',
        'p_sep_by_space': 'True',
        'n_sep_by_space': 'True',
        'mon_grouping': '[3, 3, 0]',
        'mon_decimal_point': ',',
        'mon_thousands_sep': ' ',
        'p_sign_posn': '1',
        'n_sign_posn': '1',
        'negative_sign': '-',
        'positive_sign': '',
        },
    'USD': {
        'rounding': "Decimal('0.01')",
        'digits': '2',
        'p_cs_precedes': 'True',
        'n_cs_precedes': 'True',
        'p_sep_by_space': 'False',
        'n_sep_by_space': 'False',
        'mon_grouping': '[]',
        'mon_decimal_point': '.',
        'mon_thousands_sep': ',',
        'p_sign_posn': '1',
        'n_sign_posn': '1',
        'negative_sign': '-',
        'positive_sign': '',
        },
}

for currency in pycountry.currencies:
    extend = ''
    if currency.letter in currencies:
        extend = '''
            <field name="rounding" eval="%(rounding)s"/>
            <field name="digits" eval="%(digits)s"/>
            <field name="p_cs_precedes" eval="%(p_cs_precedes)s"/>
            <field name="n_cs_precedes" eval="%(n_cs_precedes)s"/>
            <field name="p_sep_by_space" eval="%(p_sep_by_space)s"/>
            <field name="n_sep_by_space" eval="%(n_sep_by_space)s"/>
            <field name="mon_grouping">%(mon_grouping)s</field>
            <field name="mon_decimal_point">%(mon_decimal_point)s</field>
            <field name="mon_thousands_sep">%(mon_thousands_sep)s</field>
            <field name="p_sign_posn" eval="%(p_sign_posn)s"/>
            <field name="n_sign_posn" eval="%(n_sign_posn)s"/>
            <field name="negative_sign">%(negative_sign)s</field>
            <field name="positive_sign">%(positive_sign)s</field>''' % \
                    currencies[currency.letter]
    print '''
        <record model="currency.currency" id="%s">
            <field name="name">%s</field>
            <field name="code">%s</field>
            <field name="numeric_code">%s</field>
            <field name="symbol">%s</field>%s
        </record>''' % (currency.letter.lower(), currency.name.encode('utf-8'),
                currency.letter, getattr(currency, 'numeric', ''),
                symbols.get(currency.letter, currency.letter), extend)
