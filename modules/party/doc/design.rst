******
Design
******

The *Party Module* introduces the following concepts:

.. _model-party.party:

Party
=====

*Parties* are the primary concept provided by the *Party Module*.
Each party represents a person, business, organisation, association or other
group that can be treated as a single entity.

There are often a lot of properties associated with a party, including things
like `Addresses <model-party.address>`,
`Contact Mechanisms <model-party.contact_mechanism>`, and sometimes one or more
`Identifiers <model-party.identifier>` and `Categories <model-party.category>`.

.. seealso::

   Parties can be found by opening the main menu item:

      |Parties --> Parties|__

      .. |Parties --> Parties| replace:: :menuselection:`Parties --> Parties`
      __ https://demo.tryton.org/model/party.party

Reports
-------

.. _report-party.label:

Labels
^^^^^^

The *Labels* report creates a document containing the names and postal
addresses of the selected parties.
It is preformatted so it is ready to be printed onto labels which can then be
stuck onto envelopes.

Wizards
-------

.. _wizard-party.check_vies:

Check VIES
^^^^^^^^^^

The *Check* :abbr:`VIES (VAT Information Exchange System)` wizard uses the
European Commission's `VIES web service`_ to verify that a party's
VAT-identification number is valid.

.. _VIES web service: https://ec.europa.eu/taxation_customs/vies/

.. _wizard-party.replace:

Replace
^^^^^^^

This wizard is used to replace selected duplicate parties with the party that
should be used instead.
It updates all the documents that the duplicate party appears on so they point
to the party that is replacing it.
The duplicate party is then deactivated and linked to the party that replaces
it.

.. _wizard-party.erase:

Erase
^^^^^

This wizard clears out all of a party's personal data from the system
including any historized data and any resources such as attachments or notes.

.. note::

   If the party `Replaced <wizard-party.replace>` some other parties, then the
   personal data for those other parties is also erased.

.. _model-party.identifier:

Identifier
==========

A party identifier is a code that is used to identify a
`Party <model-party.party>`.
They include things like company, personal identification, social security,
tax and vat registration numbers.
Most types of identifiers are checked by Tryton before they get saved to
ensure that they are valid.

.. _model-party.address:

Address
=======

Tryton provides the party *Address* concept which is used to store a
`Party's <model-party.party>` postal addresses.
It has fields available for each different component of an address.
Each party can have more than one address, and the preferred order of the
addresses can also be defined.

.. seealso::

   Party addresses can be found by opening the main menu item:

      |Parties --> Addresses|__

      .. |Parties --> Addresses| replace:: :menuselection:`Parties --> Addresses`
      __ https://demo.tryton.org/model/party.address

.. _model-party.address.format:

Address Format
==============

The *Address Formats* allow different address formats to be specified based on
`Country <country:model-country.country>` and language.
These formats are then used when postal addresses need generating.

.. seealso::

   You can find address formats by opening the main menu item:

      |Parties --> Configuration --> Address Formats|__

      .. |Parties --> Configuration --> Address Formats| replace:: :menuselection:`Parties --> Configuration --> Address Formats`
      __ https://demo.tryton.org/model/party.address.format

.. _model-party.address.subdivision_type:

Address Subdivision Type
========================

*Address Subdivision Types* allow you to define, for each
`Country <country:model-country.country>`, which types of
`Subdivision <country:model-country.subdivision>` are used in their postal
addresses.

.. seealso::

   The address subdivision types can be accessed from the main menu item:

      |Parties --> Configuration --> Address Subdivision Types|__

      .. |Parties --> Configuration --> Address Subdivision Types| replace:: :menuselection:`Parties --> Configuration --> Address Subdivision Types`
      __ https://demo.tryton.org/model/party.address.subdivision_type

.. _model-party.contact_mechanism:

Contact Mechanism
=================

Each of the *Contact Mechanisms* represent a way in which a
`Party <model-party.party>` can be contacted.
These are things such as email addresses, phone numbers, websites, and so on.
In Tryton there is no limit to the number and type of contact mechanisms that
can be associated with a party.

.. note::

   If the Python phonenumbers_ library is installed, then any phone and
   fax numbers that get entered are validated and formatted before they are
   saved.

   .. _phonenumbers: https://pypi.org/project/phonenumbers/

.. seealso::

   A list of contact mechanisms can be found by opening the main menu item:

      |Parties --> Contact Mechanisms|__

      .. |Parties --> Contact Mechanisms| replace:: :menuselection:`Parties --> Contact Mechanisms`
      __ https://demo.tryton.org/model/party.contact_mechanism

.. _model-party.category:

Category
========

Party *Categories* are a flexible way of grouping `Parties <model-party.party>`
together.
The categories can be structured by giving them a parent category and some
sub-categories.

.. seealso::

   The party categories can be found by opening the main menu item:

      |Parties --> Categories|__

      .. |Parties --> Categories| replace:: :menuselection:`Parties --> Categories`
      __ https://demo.tryton.org/model/party.category

.. _model-party.configuration:

Configuration
=============

The party *Configuration* contains the settings which are used to configure the
behaviour and default values for things to do with parties.

The default configuration will automatically generate a code for a new
`Party <model-party.party>`.
This setting can be changed if you are `Manually assigning party codes`.

.. seealso::

   Configuration settings are found by opening the main menu item:

      |Parties --> Configuration --> Configuration|__

      .. |Parties --> Configuration --> Configuration| replace:: :menuselection:`Parties --> Configuration --> Configuration`
      __ https://demo.tryton.org/model/party.configuration/1
