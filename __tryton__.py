#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'Stock Forecast',
    'name_bg_BG': 'Прогнозиране на наличност',
    'name_ca_ES': 'Previsió d''estocs',
    'name_de_DE': 'Lagerverwaltung Bedarfsermittlung',
    'name_es_AR': 'Previsión de existencias',
    'name_es_CO': 'Previsión de existencias',
    'name_es_ES': 'Previsión de stock',
    'name_fr_FR': 'Prévision de stock',
    'version': '2.4.0',
    'author': 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': '''Provide the "Forecast" model in Inventory Management.
The Forecast form allow to define the expected stock movement towards
customers in any period of time in the future. A wizard allow to
compute the expected quantities with respect to a period in the
past. Once the form confirmed, the corresponding moves are created and
spread homogeneously across the period. Those moves will allow other
process to take forecasts into account.
''',
    'description_bg_BG': '''Предоставя модел за "прогнозиране" при управление на инвентазирация
    - Формата за "Прогноза" позволява да се зададат очакваните движения на наличност
      към клиенти в бъдещ период. Помощник позволява да се изчислят очакваните
      количества отчитайки периоди в миналто. След потвърждаване на формата, съответните
      движения биват създадени и разпределени равномерно за периода. Тези движения
      позволяват на други процеси да вземат предвид тези прогнози.
''',
    'description_ca_ES': '''Proporciona el model de «Previsió» en la gestió d'inventaris.
El formulari de previsió permet definir els moviments d'estoc previstos
cap a clients en el futur. Un assistent permet calcular les quantitats previstes
respecte a un període en el passat. Una vegada el formulari es confirma, els
moviments corresponents es creen i es distribueixen homogèniament al llarg del
període. Aquests moviments permetran a altres processos tenir en compte les
previsions.
''',
    'description_de_DE': '''Bedarfsermittlung für die Lagerverwaltung
    - Fügt das Modell "Vorhersage" zur Lagerverwaltung hinzu.
    - Das Formular "Bedarfsermittlung" ermöglicht die Erstellung von zu
      erwartenden Lagerbewegungen zu Kunden in einem beliebigen Zeitraum in der
      Zukunft. Ein Wizard ermöglicht die Berechnung der zu erwartenden
      Bewegungen auf der Grundlage eines Zeitraumes in der Vergangenheit. Bei
      Bestätigung des Formulars werden die entsprechenden Lagerbewegungen
      erzeugt und über den entsprechenden Zeitraum gleichmässig verteilt. Diese
      Lagerbewegungen ermöglichen die Berücksichtigung von Vorhersagen in
      den anderen Prozessen der Lagerverwaltung.
''',
    'description_es_AR': '''Provee el modelo de «Previsión» en la gestión de
inventarios.
El formulario de previsión permite definir los movimientos de existencias
planificados hacia los clientes en cualquier período de tiempo en el futuro.
Un asistente permite calcular las cantidades esperadas respecto a un período
en el pasado. Una vez el formulario se confirma, los movimientos
correspondientes se crean y se distribuyen homogéneamente a lo largo del
período. Dichos movimientos permitirá a otros procesos tener en cuenta las
previsiones.
''',
    'description_es_CO': '''Provee el modelo de «Previsión» en la gestión de
inventarios.
El formulario de previsión permite definir los movimientos de existencias
planificados hacia los clientes en cualquier período de tiempo en el futuro.
Un asistente permite calcular las cantidades esperadas respecto a un período
anterior.  Cuando se confirma, los movimientos correspondientes se crean
y se distribuyen homogeneamente en el período. Tales movimientos permitirá
a otros procesos hacer previsiones.
''',
    'description_es_ES': '''Proporciona el modelo de «Previsión» en la gestión de inventarios.
El formulario de previsión permite definir los movimientos de stock
previstos hacia los clientes en cualquier período de tiempo en el futuro.
Un asistente permite calcular las cantidades previstas respecto a un período
en el pasado. Una vez el formulario se confirma, los movimientos
correspondientes se crean y se distribuyen homogeneamente a lo largo del
período. Dichos movimientos permitirá a otros procesos tener en cuenta las previsiones.
''',
    'description_fr_FR': '''Fournit le modèle "Prévision" dans la gestion des stocks.
Le formulaire de prévision permet de définir les mouvements attendus
vers les clients pour n'importe quelle période dans le futur. Un
wizard permet de calculer les quantités attendues en fonction d'une
période dans le passé. A la validation du formulaire, les mouvements
correspondants sont créés et répartis sur la période donnée. Ces
mouvement permettent aux autres processus de prendre en compte les
prévisions.
''',
    'depends': [
        'ir',
        'res',
        'stock',
        'product',
        'company',
    ],
    'xml': [
        'forecast.xml',
    ],
    'translation': [
        'locale/cs_CZ.po',
        'locale/bg_BG.po',
        'locale/ca_ES.po',
        'locale/de_DE.po',
        'locale/es_AR.po',
        'locale/es_CO.po',
        'locale/es_ES.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
