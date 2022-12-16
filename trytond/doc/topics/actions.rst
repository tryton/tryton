.. _topics-actions:

=======
Actions
=======

Actions are used to describe specific behaviors in the client.

There are four types of actions:

    * Report

    * Window

    * Wizard

    * URL


Keyword
-------

Keywords define where to display the action in the client.

There are five places:

    * Open tree (``tree_open``)

    * Print form (``form_print``)

    * Action form (``form_action``)

    * Form relate (``form_relate``)

    * Open Graph (``graph_open``)

Report
======

.. TODO

Window
======

The window action describe how to create a new tab in the client.

View
----

.. TODO

Domain
------

The window action could have a list of domains which could be activated on the
view. The boolean field count indicates if the client must display the number
of records for this domain.

.. warning::
    The counting option must be activated only on domains which have not too
    much records otherwise it may overload the database.

Wizard
======

.. TODO

URL
===

.. TODO
