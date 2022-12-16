#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import time
import datetime
import warnings

from trytond.model import ModelView, ModelSQL, fields
from trytond.model.cacheable import Cacheable
from trytond.tools import safe_eval, datetime_strftime
from trytond.transaction import Transaction
from trytond.pool import Pool
from time_locale import TIME_LOCALE

warnings.filterwarnings('ignore', "", ImportWarning)
from locale import CHAR_MAX
warnings.resetwarnings()


class Lang(ModelSQL, ModelView, Cacheable):
    "Language"
    _name = "ir.lang"
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True,
            help="RFC 4646 tag: http://tools.ietf.org/html/rfc4646")
    translatable = fields.Boolean('Translatable')
    active = fields.Boolean('Active')
    direction = fields.Selection([
       ('ltr', 'Left-to-right'),
       ('rtl', 'Right-to-left'),
       ], 'Direction',required=True)

    #date
    date = fields.Char('Date', required=True)

    #number
    grouping = fields.Char('Grouping', required=True)
    decimal_point = fields.Char('Decimal Separator', required=True)
    thousands_sep = fields.Char('Thousands Separator')

    def __init__(self):
        super(Lang, self).__init__()
        self._constraints += [
            ('check_grouping', 'invalid_grouping'),
            ('check_date', 'invalid_date'),
        ]
        self._sql_constraints += [
            ('check_decimal_point_thousands_sep',
                'CHECK(decimal_point != thousands_sep)',
                'decimal_point and thousands_sep must be different!'),
        ]
        self._error_messages.update({
            'invalid_grouping': 'Invalid Grouping!',
            'invalid_date': 'The date format is not valid!',
        })

    def search_rec_name(self, name, clause):
        ids = self.search([('code',) + tuple(clause[1:])], order=[])
        if ids:
            ids += self.search([('name',) + tuple(clause[1:])], order=[])
            return [('id', 'in', ids)]
        return [('name',) + tuple(clause[1:])]

    def read(self, ids, fields_names=None):
        pool = Pool()
        translation_obj = pool.get('ir.translation')
        res = super(Lang, self).read(ids, fields_names=fields_names)
        if (Transaction().context.get('translate_name')
                and (not fields_names or 'name' in fields_names)):
            with Transaction().set_context(
                    language=self.default_code(),
                    translate_name=False):
                res2 = self.read(ids, fields_names=['id', 'code', 'name'])
            for record2 in res2:
                for record in res:
                    if record['id'] == record2['id']:
                        break
                res_trans = translation_obj._get_ids(self._name + ',name',
                        'model', record2['code'], [record2['id']])
                record['name'] = res_trans.get(record2['id'], False) \
                        or record2['name']
        return res

    def default_code(self):
        return 'en_US'

    def default_active(self):
        return True

    def default_translatable(self):
        return False

    def default_direction(self):
        return 'ltr'

    def default_date(self):
        return '%m/%d/%Y'

    def default_grouping(self):
        return '[]'

    def default_decimal_point(self):
        return '.'

    def default_thousands_sep(self):
        return ','

    def check_grouping(self, ids):
        '''
        Check if grouping is list of numbers
        '''
        for lang in self.browse(ids):
            try:
                grouping = safe_eval(lang.grouping)
                for i in grouping:
                    if not isinstance(i, int):
                        return False
            except Exception:
                return False
        return True

    def check_date(self, ids):
        '''
        Check the date format
        '''
        for lang in self.browse(ids):
            try:
                datetime_strftime(datetime.datetime.now(),
                        lang.date.encode('utf-8'))
            except Exception:
                return False
            if '%Y' not in lang.date:
                return False
            if '%b' not in lang.date \
                    and '%B' not in lang.date \
                    and '%m' not in lang.date \
                    and '%-m' not in lang.date:
                return False
            if '%d' not in lang.date \
                    and '%-d' not in lang.date \
                    and '%j' not in lang.date \
                    and '%-j' not in lang.date:
                return False
            if '%x' in lang.date \
                    or '%X' in lang.date \
                    or '%c' in lang.date \
                    or '%Z' in lang.date:
                return False
        return True

    def check_xml_record(self, ids, values):
        return True

    def get_translatable_languages(self):
        res = self.get('translatable_languages')
        if res is None:
            lang_ids = self.search([
                    ('translatable', '=', True),
                    ])
            res = [x.code for x in self.browse(lang_ids)]
            self.add('translatable_languages', res)
        return res

    def create(self, vals):
        # Clear cache
        if self.get('translatable_languages'):
            self.invalidate('translatable_languages')
        return super(Lang, self).create(vals)

    def write(self, ids, vals):
        # Clear cache
        if self.get('translatable_languages'):
            self.invalidate('translatable_languages')
        return super(Lang, self).write(ids, vals)

    def delete(self, ids):
        # Clear cache
        if self.get('translatable_languages'):
            self.invalidate('translatable_languages')
        return super(Lang, self).delete(ids)

    def _group(self, lang, s, monetary=False):
        # Code from _group in locale.py

        # Iterate over grouping intervals
        def _grouping_intervals(grouping):
            for interval in grouping:
                # if grouping is -1, we are done
                if interval == CHAR_MAX:
                    return
                # 0: re-use last group ad infinitum
                if interval == 0:
                    while True:
                        yield last_interval
                yield interval
                last_interval = interval

        if monetary:
            thousands_sep = monetary['mon_thousands_sep']
            grouping = safe_eval(monetary['mon_grouping'])
        else:
            thousands_sep = lang['thousands_sep']
            grouping = safe_eval(lang['grouping'])
        if not grouping:
            return (s, 0)
        result = ""
        seps = 0
        spaces = ""
        if s[-1] == ' ':
            stripped = s.rstrip()
            right_spaces = s[len(stripped):]
            s = stripped
        else:
            right_spaces = ''
        left_spaces = ''
        groups = []
        for interval in _grouping_intervals(grouping):
            if not s or s[-1] not in "0123456789":
                # only non-digit characters remain (sign, spaces)
                left_spaces = s
                s = ''
                break
            groups.append(s[-interval:])
            s = s[:-interval]
        if s:
            groups.append(s)
        groups.reverse()
        return (
            left_spaces + thousands_sep.join(groups) + right_spaces,
            len(thousands_sep) * (len(groups) - 1)
        )

    def format(self, lang, percent, value, grouping=False, monetary=None, *additional):
        '''
        Returns the lang-aware substitution of a %? specifier (percent).

        :param lang: the BrowseRecord of the language
        :param percent: the string with %? specifier
        :param value: the value
        :param grouping: a boolean to take grouping into account
        :param monetary: a BrowseRecord of the currency or None
        :param additional: for format strings which contain one or more modifiers

        :return: the formatted string
        '''
        # Code from format in locale.py

        # Strip a given amount of excess padding from the given string
        def _strip_padding(s, amount):
            lpos = 0
            while amount and s[lpos] == ' ':
                lpos += 1
                amount -= 1
            rpos = len(s) - 1
            while amount and s[rpos] == ' ':
                rpos -= 1
                amount -= 1
            return s[lpos:rpos+1]

        if not lang:
            lang = {
                'decimal_point': self.default_decimal_point(),
                'thousands_sep': self.default_thousands_sep(),
                'grouping': self.default_grouping(),
            }

        # this is only for one-percent-specifier strings and this should be checked
        if percent[0] != '%':
            raise ValueError("format() must be given exactly one %char "
                             "format specifier")
        if additional:
            formatted = percent % ((value,) + additional)
        else:
            formatted = percent % value
        # floats and decimal ints need special action!
        if percent[-1] in 'eEfFgG':
            seps = 0
            parts = formatted.split('.')
            if grouping:
                parts[0], seps = self._group(lang, parts[0], monetary=monetary)
            if monetary:
                decimal_point = monetary['mon_decimal_point']
            else:
                decimal_point = lang['decimal_point']
            formatted = decimal_point.join(parts)
            if seps:
                formatted = _strip_padding(formatted, seps)
        elif percent[-1] in 'diu':
            if grouping:
                formatted, seps = self._group(lang, formatted, monetary=monetary)
            if seps:
                formatted = _strip_padding(formatted, seps)
        return formatted


    def currency(self, lang, val, currency, symbol=True, grouping=False):
        """
        Formats val according to the currency settings in lang.

        :param lang: the BrowseRecord of the language
        :param val: the value to format
        :param currency: the BrowseRecord of the currency
        :param symbol: a boolean to include currency symbol
        :param grouping: a boolean to take grouping into account

        :return: the formatted string
        """
        # Code from currency in locale.py
        if not lang:
            lang = {
                'decimal_point': self.default_decimal_point(),
                'thousands_sep': self.default_thousands_sep(),
                'grouping': self.default_grouping(),
            }

        # check for illegal values
        digits = currency.digits
        if digits == 127:
            raise ValueError("Currency formatting is not possible using "
                             "the 'C' locale.")

        s = self.format(lang, '%%.%if' % digits, abs(val), grouping,
                monetary=currency)
        # '<' and '>' are markers if the sign must be inserted between symbol and value
        s = '<' + s + '>'

        if symbol:
            smb = currency.symbol
            precedes = val<0 and currency.n_cs_precedes or currency.p_cs_precedes
            separated = val<0 and currency.n_sep_by_space or currency.p_sep_by_space

            if precedes:
                s = smb + (separated and ' ' or '') + s
            else:
                s = s + (separated and ' ' or '') + smb

        sign_pos = val<0 and currency.n_sign_posn or currency.p_sign_posn
        sign = val<0 and currency.negative_sign or currency.positive_sign

        if sign_pos == 0:
            s = '(' + s + ')'
        elif sign_pos == 1:
            s = sign + s
        elif sign_pos == 2:
            s = s + sign
        elif sign_pos == 3:
            s = s.replace('<', sign)
        elif sign_pos == 4:
            s = s.replace('>', sign)
        else:
            # the default if nothing specified;
            # this should be the most fitting sign position
            s = sign + s

        return s.replace('<', '').replace('>', '')

    def strftime(self, datetime, code, format):
        '''
        Convert datetime to a string as specified by the format argument.

        :param datetime: a datetime
        :param code: locale code
        :param format: a string
        :return: a unicode string
        '''
        if code in TIME_LOCALE:
            for f, i in (('%a', 6), ('%A', 6), ('%b', 1), ('%B', 1)):
                format = format.replace(f,
                        TIME_LOCALE[code][f][datetime.timetuple()[i]])
            format = format.replace('%p', TIME_LOCALE[code]['%p']\
                    [datetime.timetuple()[3] < 12 and 0 or 1]).encode('utf-8')
        else:
            format = format.encode('utf-8')
        return datetime_strftime(datetime, format).decode('utf-8')

Lang()
