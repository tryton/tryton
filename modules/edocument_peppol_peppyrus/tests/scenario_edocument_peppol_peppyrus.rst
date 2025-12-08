==================================
EDocument Peppol Peppyrus Scenario
==================================

Imports::

    >>> import os
    >>> from unittest.mock import patch

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.edocument_peppol.edocument import Peppol
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.tools import file_open

Patch Peppol::

    >>> _validate = patch.object(Peppol, '_validate').start()
    >>> render = patch.object(Peppol, 'render').start()
    >>> participant_scheme, participant_id = (
    ...     os.getenv('PEPPYRUS_PARTICIPANT_ID').split(':', 1))
    >>> participant_vat = os.getenv('PEPPYRUS_PARTICIPANT_VAT')
    >>> with file_open('edocument_peppol_peppyrus/tests/invoice.xml', mode='r') as fp:
    ...     render.return_value = (
    ...         fp.read()
    ...         .replace('PARTICIPANT_SCHEME', participant_scheme)
    ...         .replace('PARTICIPANT_ID', participant_id)
    ...         .replace('PARTICIPANT_VAT', participant_vat.upper())
    ...         .encode())

Activate modules::

    >>> config = activate_modules('edocument_peppol_peppyrus', create_company)

    >>> Cron = Model.get('ir.cron')
    >>> Peppol = Model.get('edocument.peppol')
    >>> PeppolService = Model.get('edocument.peppol.service')

Create a service::

    >>> peppol_service = PeppolService(sequence=1)
    >>> peppol_service.types = ['bis-billing-3']
    >>> peppol_service.service = 'peppyrus'
    >>> peppol_service.peppyrus_server = 'testing'
    >>> peppol_service.peppyrus_api_key = os.getenv('PEPPYRUS_API_KEY')
    >>> peppol_service.save()

Send out a Peppol document::

    >>> peppol = Peppol(direction='out')
    >>> peppol.type = 'bis-billing-3'
    >>> peppol.service = peppol_service
    >>> peppol.click('submit')
    >>> peppol.state
    'processing'
    >>> bool(peppol.transmission_id)
    True

Check Peppol status::

    >>> cron, = Cron.find([
    ...     ('method', '=', 'edocument.peppol|update_status'),
    ...     ], limit=1)
    >>> while peppol.state == 'processing':
    ...     cron.click('run_once')
    ...     peppol.reload()
    >>> peppol.state
    'succeeded'

Fetch messages::

    >>> cron, = Cron.find([
    ...         ('method', '=', 'edocument.peppol.service|peppyrus_fetch'),
    ...         ], limit=1)
    >>> cron.click('run_once')

    >>> bool(Peppol.find([('direction', '=', 'in')]))
    True
