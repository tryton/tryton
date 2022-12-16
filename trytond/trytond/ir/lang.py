# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import warnings
from ast import literal_eval

from ..model import ModelView, ModelSQL, fields, Check
from ..cache import Cache
from ..tools import datetime_strftime
from ..transaction import Transaction
from ..pool import Pool
from .time_locale import TIME_LOCALE
from ..backend.database import CursorInterface

warnings.filterwarnings('ignore', "", ImportWarning)
from locale import CHAR_MAX
warnings.resetwarnings()

CursorInterface.cache_keys.add('translate_name')

__all__ = [
    'Lang',
    ]


class Lang(ModelSQL, ModelView):
    "Language"
    __name__ = "ir.lang"
    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True,
        help="RFC 4646 tag: http://tools.ietf.org/html/rfc4646")
    translatable = fields.Boolean('Translatable')
    active = fields.Boolean('Active')
    direction = fields.Selection([
            ('ltr', 'Left-to-right'),
            ('rtl', 'Right-to-left'),
            ], 'Direction', required=True)

    # date
    date = fields.Char('Date', required=True)

    # number
    grouping = fields.Char('Grouping', required=True)
    decimal_point = fields.Char('Decimal Separator', required=True)
    thousands_sep = fields.Char('Thousands Separator')

    _lang_cache = Cache('ir.lang')

    @classmethod
    def __setup__(cls):
        super(Lang, cls).__setup__()

        table = cls.__table__()
        cls._sql_constraints += [
            ('check_decimal_point_thousands_sep',
                Check(table, table.decimal_point != table.thousands_sep),
                'decimal_point and thousands_sep must be different!'),
            ]
        cls._error_messages.update({
                'invalid_grouping': ('Invalid grouping "%(grouping)s" on '
                    '"%(language)s" language.'),
                'invalid_date': ('Invalid date format "%(format)s" on '
                    '"%(language)s" language.'),
                'default_translatable': ('The default language must be '
                    'translatable.'),
                'delete_default': ('Default language can not be deleted.'),
                })

    @classmethod
    def search_rec_name(cls, name, clause):
        langs = cls.search([('code',) + tuple(clause[1:])], order=[])
        if langs:
            langs += cls.search([('name',) + tuple(clause[1:])], order=[])
            return [('id', 'in', [l.id for l in langs])]
        return [('name',) + tuple(clause[1:])]

    @classmethod
    def read(cls, ids, fields_names=None):
        pool = Pool()
        Translation = pool.get('ir.translation')
        Config = pool.get('ir.configuration')
        res = super(Lang, cls).read(ids, fields_names=fields_names)
        if (Transaction().context.get('translate_name')
                and (not fields_names or 'name' in fields_names)):
            with Transaction().set_context(
                    language=Config.get_language(),
                    translate_name=False):
                res2 = cls.read(ids, fields_names=['id', 'code', 'name'])
            for record2 in res2:
                for record in res:
                    if record['id'] == record2['id']:
                        break
                res_trans = Translation.get_ids(cls.__name__ + ',name',
                        'model', record2['code'], [record2['id']])
                record['name'] = (res_trans.get(record2['id'], False)
                    or record2['name'])
        return res

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_translatable():
        return False

    @staticmethod
    def default_direction():
        return 'ltr'

    @staticmethod
    def default_date():
        return '%m/%d/%Y'

    @staticmethod
    def default_grouping():
        return '[]'

    @staticmethod
    def default_decimal_point():
        return '.'

    @staticmethod
    def default_thousands_sep():
        return ','

    @classmethod
    def validate(cls, languages):
        super(Lang, cls).validate(languages)
        cls.check_grouping(languages)
        cls.check_date(languages)
        cls.check_translatable(languages)

    @classmethod
    def check_grouping(cls, langs):
        '''
        Check if grouping is list of numbers
        '''
        for lang in langs:
            try:
                grouping = literal_eval(lang.grouping)
                for i in grouping:
                    if not isinstance(i, int):
                        raise
            except Exception:
                cls.raise_user_error('invalid_grouping', {
                        'grouping': lang.grouping,
                        'language': lang.rec_name,
                        })

    @classmethod
    def check_date(cls, langs):
        '''
        Check the date format
        '''
        for lang in langs:
            try:
                datetime_strftime(datetime.datetime.now(),
                        lang.date.encode('utf-8'))
            except Exception:
                cls.raise_user_error('invalid_date', {
                        'format': lang.date,
                        'language': lang.rec_name,
                        })
            if (('%Y' not in lang.date)
                    or ('%b' not in lang.date
                        and '%B' not in lang.date
                        and '%m' not in lang.date
                        and '%-m' not in lang.date)
                    or ('%d' not in lang.date
                        and '%-d' not in lang.date
                        and '%j' not in lang.date
                        and '%-j' not in lang.date)
                    or ('%x' in lang.date
                        or '%X' in lang.date
                        or '%c' in lang.date
                        or '%Z' in lang.date)):
                cls.raise_user_error('invalid_date', {
                        'format': lang.date,
                        'language': lang.rec_name,
                        })

    @classmethod
    def check_translatable(cls, langs):
        pool = Pool()
        Config = pool.get('ir.configuration')
        # Skip check for root because when languages are created from XML file,
        # translatable is not yet set.
        if Transaction().user == 0:
            return True
        for lang in langs:
            if (lang.code == Config.get_language()
                    and not lang.translatable):
                cls.raise_user_error('default_translatable')

    @staticmethod
    def check_xml_record(langs, values):
        return True

    @classmethod
    def get_translatable_languages(cls):
        res = cls._lang_cache.get('translatable_languages')
        if res is None:
            langs = cls.search([
                    ('translatable', '=', True),
                    ])
            res = [x.code for x in langs]
            cls._lang_cache.set('translatable_languages', res)
        return res

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Translation = pool.get('ir.translation')
        # Clear cache
        cls._lang_cache.clear()
        languages = super(Lang, cls).create(vlist)
        Translation._get_language_cache.clear()
        return languages

    @classmethod
    def write(cls, langs, values, *args):
        pool = Pool()
        Translation = pool.get('ir.translation')
        # Clear cache
        cls._lang_cache.clear()
        super(Lang, cls).write(langs, values, *args)
        Translation._get_language_cache.clear()

    @classmethod
    def delete(cls, langs):
        pool = Pool()
        Config = pool.get('ir.configuration')
        Translation = pool.get('ir.translation')
        for lang in langs:
            if lang.code == Config.get_language():
                cls.raise_user_error('delete_default')
        # Clear cache
        cls._lang_cache.clear()
        super(Lang, cls).delete(langs)
        Translation._get_language_cache.clear()

    @staticmethod
    def _group(lang, s, monetary=None):
        # Code from _group in locale.py

        # Iterate over grouping intervals
        def _grouping_intervals(grouping):
            last_interval = 0
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
            thousands_sep = monetary.mon_thousands_sep
            grouping = literal_eval(monetary.mon_grouping)
        else:
            thousands_sep = lang.thousands_sep
            grouping = literal_eval(lang.grouping)
        if not grouping:
            return (s, 0)
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

    @classmethod
    def format(cls, lang, percent, value, grouping=False, monetary=None,
            *additional):
        '''
        Returns the lang-aware substitution of a %? specifier (percent).
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
            return s[lpos:rpos + 1]

        if not lang:
            lang = cls(
                decimal_point=cls.default_decimal_point(),
                thousands_sep=cls.default_thousands_sep(),
                grouping=cls.default_grouping(),
                )

        # this is only for one-percent-specifier strings
        # and this should be checked
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
                parts[0], seps = cls._group(lang, parts[0], monetary=monetary)
            if monetary:
                decimal_point = monetary.mon_decimal_point
            else:
                decimal_point = lang.decimal_point
            formatted = decimal_point.join(parts)
            if seps:
                formatted = _strip_padding(formatted, seps)
        elif percent[-1] in 'diu':
            if grouping:
                formatted, seps = cls._group(lang, formatted,
                    monetary=monetary)
            if seps:
                formatted = _strip_padding(formatted, seps)
        return formatted

    @classmethod
    def currency(cls, lang, val, currency, symbol=True, grouping=False):
        """
        Formats val according to the currency settings in lang.
        """
        # Code from currency in locale.py
        if not lang:
            lang = cls(
                decimal_point=cls.default_decimal_point(),
                thousands_sep=cls.default_thousands_sep(),
                grouping=cls.default_grouping(),
                )

        # check for illegal values
        digits = currency.digits
        if digits == 127:
            raise ValueError("Currency formatting is not possible using "
                             "the 'C' locale.")

        s = cls.format(lang, '%%.%if' % digits, abs(val), grouping,
                monetary=currency)
        # '<' and '>' are markers if the sign must be inserted
        # between symbol and value
        s = '<' + s + '>'

        if symbol:
            smb = currency.symbol
            precedes = (val < 0 and currency.n_cs_precedes
                or currency.p_cs_precedes)
            separated = (val < 0 and currency.n_sep_by_space
                or currency.p_sep_by_space)

            if precedes:
                s = smb + (separated and ' ' or '') + s
            else:
                s = s + (separated and ' ' or '') + smb

        sign_pos = val < 0 and currency.n_sign_posn or currency.p_sign_posn
        sign = val < 0 and currency.negative_sign or currency.positive_sign

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

    @staticmethod
    def strftime(datetime, code, format):
        '''
        Convert datetime to a string as specified by the format argument.
        '''
        if code in TIME_LOCALE:
            for f, i in (('%a', 6), ('%A', 6), ('%b', 1), ('%B', 1)):
                format = format.replace(f,
                        TIME_LOCALE[code][f][datetime.timetuple()[i]])
            format = format.replace('%p',
                TIME_LOCALE[code]['%p'][datetime.timetuple()[3] < 12 and 0
                    or 1]).encode('utf-8')
        else:
            format = format.encode('utf-8')
        return datetime_strftime(datetime, format).decode('utf-8')
