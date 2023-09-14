==========================
Document Incoming Scenario
==========================

Imports::

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.tools import file_open

Activate modules::

    >>> config = activate_modules('document_incoming')

    >>> Document = Model.get('document.incoming')

Create incoming document::

    >>> document = Document()
    >>> document.name = 'test.pdf'
    >>> document.type = 'document_incoming'
    >>> with file_open(
    ...         'document_incoming/tests/mutipage.pdf',
    ...         mode='rb') as fp:
    ...     document.data = fp.read()
    >>> document.save()

Process document::

    >>> document.click('process')
    >>> document.state
    'done'
    >>> new_document = document.result
    >>> new_document.data == document.data
    True
    >>> new_document.type
