# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import time
import locale
import os
import pprint

_LOCALE2WIN32 = {
    'af_ZA': 'Afrikaans_South Africa',
    'ar_AE': 'Arabic_UAE',
    'ar_BH': 'Arabic_Bahrain',
    'ar_DZ': 'Arabic_Algeria',
    'ar_EG': 'Arabic_Egypt',
    'ar_IQ': 'Arabic_Iraq',
    'ar_JO': 'Arabic_Jordan',
    'ar_KW': 'Arabic_Kuwait',
    'ar_LB': 'Arabic_Lebanon',
    'ar_LY': 'Arabic_Libya',
    'ar_MA': 'Arabic_Morocco',
    'ar_OM': 'Arabic_Oman',
    'ar_QA': 'Arabic_Qatar',
    'ar_SA': 'Arabic_Saudi_Arabia',
    'ar_SY': 'Arabic_Syria',
    'ar_TN': 'Arabic_Tunisia',
    'ar_YE': 'Arabic_Yemen',
    'az-Cyrl-AZ': 'Azeri_Cyrillic',
    'az-Latn-AZ': 'Azeri_Latin',
    'be_BY': 'Belarusian_Belarus',
    'bg_BG': 'Bulgarian_Bulgaria',
    'bs_BA': 'Serbian (Latin)',
    'ca_ES': 'Catalan_Spain',
    'cs_CZ': 'Czech_Czech Republic',
    'da_DK': 'Danish_Denmark',
    'de_AT': 'German_Austrian',
    'de_CH': 'German_Swiss',
    'de_DE': 'German_Germany',
    'de_LI': 'German_Liechtenstein',
    'de_LU': 'German_Luxembourg',
    'el_GR': 'Greek_Greece',
    'en_AU': 'English_Australian',
    'en_BZ': 'English_Belize',
    'en_CA': 'English_Canadian',
    'en_IE': 'English_Irish',
    'en_JM': 'English_Jamaica',
    'en_TT': 'English_Trinidad',
    'en_US': 'English_USA',
    'en_ZW': 'English_Zimbabwe',
    'es_AR': 'Spanish_Argentina',
    'es_BO': 'Spanish_Bolivia',
    'es_CL': 'Spanish_Chile',
    'es_CO': 'Spanish_Colombia',
    'es_CR': 'Spanish_Costa_Rica',
    'es_DO': 'Spanish_Dominican_Republic',
    'es_EC': 'Spanish_Ecuador',
    'es_ES': 'Spanish_Spain',
    'es_ES_tradnl': 'Spanish_Traditional_Sort',
    'es_GT': 'Spanish_Guatemala',
    'es_HN': 'Spanish_Honduras',
    'es_MX': 'Spanish_Mexican',
    'es_NI': 'Spanish_Nicaragua',
    'es_PA': 'Spanish_Panama',
    'es_PE': 'Spanish_Peru',
    'es_PR': 'Spanish_Puerto_Rico',
    'es_PY': 'Spanish_Paraguay',
    'es_SV': 'Spanish_El_Salvador',
    'es_UY': 'Spanish_Uruguay',
    'es_VE': 'Spanish_Venezuela',
    'et_EE': 'Estonian_Estonia',
    'eu_ES': 'Basque_Spain',
    'fa_IR': 'Farsi_Iran',
    'fi_FI': 'Finnish_Finland',
    'fr_BE': 'French_Belgian',
    'fr_CA': 'French_Canadian',
    'fr_CH': 'French_Swiss',
    'fr_FR': 'French_France',
    'fr_LU': 'French_Luxembourg',
    'fr_MC': 'French_Monaco',
    'ga': 'Scottish Gaelic',
    'gl_ES': 'Galician_Spain',
    'gu': 'Gujarati_India',
    'he_IL': 'Hebrew',
    'he_IL': 'Hebrew_Israel',
    'hi_IN': 'Hindi',
    'hi_IN': 'Hindi',
    'hr_HR': 'Croatian',
    'hu_HU': 'Hungarian',
    'hu': 'Hungarian_Hungary',
    'hy_AM': 'Armenian',
    'id_ID': 'Indonesian_indonesia',
    'is_IS': 'Icelandic_Iceland',
    'it_CH': 'Italian_Swiss',
    'it_IT': 'Italian_Italy',
    'ja_JP': 'Japanese_Japan',
    'ka_GE': 'Georgian_Georgia',
    'kk_KZ': 'Kazakh',
    'km_KH': 'Khmer',
    'kn_IN': 'Kannada',
    'ko_IN': 'Konkani',
    'ko_KR': 'Korean_Korea',
    'lo_LA': 'Lao_Laos',
    'lt_LT': 'Lithuanian_Lithuania',
    'lv_LV': 'Latvian_Latvia',
    'mi_NZ': 'Maori',
    'mi_NZ': 'Maori',
    'mi_NZ': 'Maori',
    'mk_MK': 'Macedonian',
    'ml_IN': 'Malayalam_India',
    'mn': 'Cyrillic_Mongolian',
    'mr_IN': 'Marathi',
    'ms_BN': 'Malay_Brunei_Darussalam',
    'ms_MY': 'Malay_Malaysia',
    'nb_NO': 'Norwegian_Bokmal',
    'nl_BE': 'Dutch_Belgian',
    'nl_NL': 'Dutch_Netherlands',
    'nn_NO': 'Norwegian-Nynorsk_Norway',
    'ph_PH': 'Filipino_Philippines',
    'pl_PL': 'Polish_Poland',
    'pt_BR': 'Portuguese_Brazil',
    'pt_PT': 'Portuguese_Portugal',
    'ro_RO': 'Romanian_Romania',
    'ru_RU': 'Russian_Russia',
    'sa_IN': 'Sanskrit',
    'sk_SK': 'Slovak_Slovakia',
    'sl_SI': 'Slovenian_Slovenia',
    'sq_AL': 'Albanian_Albania',
    'sr_CS': 'Serbian (Cyrillic)_Serbia and Montenegro',
    'sv_FI': 'Swedish_Finland',
    'sv_SE': 'Swedish_Sweden',
    'sw_KE': 'Swahili',
    'ta_IN': 'Tamil',
    'th_TH': 'Thai_Thailand',
    'tr_IN': 'Urdu',
    'tr_TR': 'Turkish_Turkey',
    'tt_RU': 'Tatar',
    'uk_UA': 'Ukrainian_Ukraine',
    'uz-Cyrl_UZ': 'Uzbek_Cyrillic',
    'uz-Latn_UZ': 'Uzbek_Latin',
    'vi_VN': 'Vietnamese_Viet Nam',
    'zh_CN': 'Chinese_PRC',
    'zh_HK': 'Chinese_Hong_Kong',
    'zh_MO': 'Chinese_Macau',
    'zh_SG': 'Chinese_Singapore',
    'zh_TW': 'Chinese_Taiwan',
}


def locale_strftime(lang):
    time_locale = {
        '%a': [],
        '%A': [],
        '%b': [None],
        '%B': [None],
        '%p': [],
    }
    encoding = locale.getdefaultlocale()[1]
    if not encoding:
        encoding = 'UTF-8'
    if encoding.lower() in ('utf', 'utf8'):
        encoding = 'UTF-8'
    if encoding == 'cp1252':
        encoding = '1252'
    if os.name == 'nt':
        lang = _LOCALE2WIN32.get(lang, lang)
    locale.setlocale(locale.LC_ALL, lang + '.' + encoding)
    t = list(time.gmtime())
    for i in range(12):
        t[1] = i + 1
        for format in ('%b', '%B'):
            time_locale[format].append(time.strftime(format,
                t).decode(encoding))
    for i in range(7):
        t[6] = i
        for format in ('%a', '%A'):
            time_locale[format].append(time.strftime(format,
                t).decode(encoding))
    t[3] = 0
    time_locale['%p'].append(time.strftime('%p', t).decode(encoding))
    t[3] = 23
    time_locale['%p'].append(time.strftime('%p', t).decode(encoding))
    return time_locale

if __name__ == '__main__':
    with open(os.path.join(os.path.dirname(__file__), 'time_locale.py'),
            'w') as fp:
        fp.write('''# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of')
# this repository contains the full copyright notices and license terms.')
''')
        time_locale = {}
        fp.write('TIME_LOCALE = \\\n')
        for lang in [
                'bg_BG',
                'ca_ES',
                'cs_CZ',
                'de_DE',
                'en_US',
                'es_AR',
                'es_EC',
                'es_ES',
                'es_CO',
                'fr_FR',
                'nl_NL',
                'ru_RU',
                'sl_SI',
                ]:
            time_locale[lang] = locale_strftime(lang)
        pp = pprint.PrettyPrinter(stream=fp)
        pp.pprint(time_locale)
