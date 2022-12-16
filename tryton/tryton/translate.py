# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
"Translate"
import os
import locale
import gettext
import logging
import sys

from gi.repository import Gtk

from tryton.config import CURRENT_DIR

_ = gettext.gettext

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
    'he_IL': 'Hebrew_Israel',
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


def setlang(lang=None, locale_dict=None):
    "Set language"
    locale_dir = os.path.join(CURRENT_DIR, 'data/locale')
    if not os.path.isdir(locale_dir):
        # do not import when frozen
        import pkg_resources
        locale_dir = pkg_resources.resource_filename(
            'tryton', 'data/locale')
    if lang:
        encoding = locale.getdefaultlocale()[1]
        if not encoding:
            encoding = 'UTF-8'
        if encoding.lower() in ('utf', 'utf8'):
            encoding = 'UTF-8'
        if encoding == 'cp1252':
            encoding = '1252'
        try:
            lang2 = locale.normalize(lang).split('.')[0]
            if os.name == 'nt':
                lang2 = _LOCALE2WIN32.get(lang2, lang2)
            elif sys.platform == 'darwin':
                encoding = 'UTF-8'
            # ensure environment variable are str
            lang, lang2, encoding = str(lang), str(lang2), str(encoding)
            os.environ['LANGUAGE'] = lang
            os.environ['LC_ALL'] = lang2 + '.' + encoding
            os.environ['LC_MESSAGES'] = lang2 + '.' + encoding
            os.environ['LANG'] = lang + '.' + encoding
            locale.setlocale(locale.LC_ALL, lang2 + '.' + encoding)
        except locale.Error:
            logging.getLogger(__name__).info(
                    _('Unable to set locale %s') % lang2 + '.' + encoding)

    if os.path.isdir(locale_dir):
        gettext.bindtextdomain('tryton', locale_dir)
    gettext.textdomain('tryton')

    if locale_dict:
        conv = locale.localeconv()
        for field in list(locale_dict.keys()):
            if field == 'date':
                continue
            conv[field] = locale_dict[field]
        locale.localeconv = lambda: conv


def set_language_direction(direction):
    if direction == 'rtl':
        direction = Gtk.TextDirection.RTL
    else:
        direction = Gtk.TextDirection.LTR
    Gtk.Widget.set_default_direction(direction)
