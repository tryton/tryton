#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Company Work Time',
    'name_bg_BG': 'Работно време на фирма',
    'name_ca_ES': 'Hores de treball a l''empresa',
    'name_de_DE': 'Unternehmen Arbeitszeit',
    'name_es_AR': 'Tiempo de trabajo en la empresa',
    'name_es_CO': 'Tiempo de Trabajo en la Compañía',
    'name_es_ES': 'Tiempo de trabajo en la empresa',
    'name_fr_FR': 'Temps de travail dans la société',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''
''',
    'description_ca_ES': '''Afegeix les hores de treball al dia, setmana, mes i
any per empresa.
''',
    'description_es_AR': '''Añade horas de trabajo por día, semana, mes y
año por empresa.
''',
    'description_es_ES': '''Añade las horas de trabajo por día, semana, mes y
año por empresa.
''',
    'depends': [
        'ir',
        'company',
    ],
    'xml': [
        'company.xml',
    ],
    'translation': [
        'locale/bg_BG.po',
        'locale/ca_ES.po',
        'locale/cs_CZ.po',
        'locale/de_DE.po',
        'locale/es_AR.po',
        'locale/es_CO.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
