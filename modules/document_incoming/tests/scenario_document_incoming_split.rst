================================
Document Incoming Split Scenario
================================

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
    >>> with file_open(
    ...         'document_incoming/tests/mutipage.pdf',
    ...         mode='rb') as fp:
    ...     document.data = fp.read()
    >>> document.save()

    >>> document.mime_type
    'application/pdf'

Split in 2::

    >>> split_wizard = document.click('split_wizard')
    >>> split_wizard.form.pages
    '1-3'
    >>> split_wizard.form.pages = '1-2,3'
    >>> split_wizard.execute('split')

    >>> len(document.children)
    2
