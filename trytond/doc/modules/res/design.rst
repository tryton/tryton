******
Design
******

The *Resource Module* introduces some important concepts.

.. note::

   For historical reasons the module's technical name is ``res``.

.. _model-res.user:

User
====

The *User* concept stores the details of the user accounts for the people who
use Tryton.
Each user is identified by their login name which must be unique.
The login name is used when logging in to Tryton, along with other
authentication data, such as their password.

It also contains a set of other properties that let you store additional
information about the user, such as their name, email address, and language.

Users can belong to `Groups <model-res.group>` which define, amongst other
things, their access rights.
They have a list of `User Applications <model-res.user.application>` that
are linked to the account, and a set of actions that are run when the user
next logs in.

.. note::

   Once a user has been created they cannot be deleted, only deactivated.
   This is to preserve data integrity and ensure history is not lost.

.. seealso::

   A list of users is found by opening the main menu item:

      |Administration --> Users --> Users|__

      .. |Administration --> Users --> Users| replace:: :menuselection:`Administration --> Users --> Users`
      __ https://demo.tryton.org/model/res.user

Reports
-------

.. _report-res.user.email_reset_password:

Email Reset Password
^^^^^^^^^^^^^^^^^^^^

The *Email Reset Password* report provides the contents of the email that is
sent to the `User <model-res.user>` when their password is reset.
It provides information about how they can go about setting a new password.

Wizards
-------

.. _wizard-res.user.config:

User Config
^^^^^^^^^^^

The *User Config* wizard is run from the module configuration wizard after
the *Resource Module* is activated.
It prompts the `User <model-res.user>` into creating one, or more, standard
user accounts.

.. _model-res.group:

Group
=====

The *Groups* concept is used to gather together `Users <model-res.user>` and
make it easy to manage what data they can see, and what actions they can
perform.

Each group is made up of a set of users.
Each of these user's `Access Rights <topics-access_rights>` are affected by the
access permissions defined for the group.

.. seealso::

   A list of users is found by opening the main menu item:

      |Administration --> Users --> Groups|__

      .. |Administration --> Users --> Groups| replace:: :menuselection:`Administration --> Users --> Groups`
      __ https://demo.tryton.org/model/res.group

.. _model-res.user.application:

User Application
================

The *User Application* concept stores a list of the secret keys for any `User
Application <topics-user_application>` that has requested to be connected to a
`User <model-res.user>` account.

Keys that are validated allow the associated user application to use the
endpoints defined for that user application on behalf of the user.

.. _model-res.user.login.attempt:

Login Attempt
=============

The *Login Attempt* concept is used to track and limit login attempts from
IP addresses and networks.

It is configured using settings from the ``[session]`` section of the
`configuration file <topics-configuration>`.

.. _model-res.user.device:

User Device
===========

The concept of a *User Device* allows the server to keep track of devices
from which a user has successfully logged in.
This is done using a device cookie.
It allows the server to distinguish between connection attempts from trusted
and untrusted devices and react accordingly.

.. _model-res.user.warning:

Warning
=======

The user *Warning* concept is used to record whether a user wants to see a
`specific warning <topics-user_errors_warnings>` again.
