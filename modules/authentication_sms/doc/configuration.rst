*************
Configuration
*************

The *Authentication SMS Module* introduces a new `authentication service
<trytond:config-session.authentications>` ``sms`` and uses settings from the
``[authentication_sms]`` section of the :ref:`trytond:topics-configuration`.

.. _config-authentication_sms.function:

``function``
============

The fully qualified name of the Python method used to send :abbr:`SMS (Short
Message Service)` with the signature: ``(text, to, from)``.

.. important::
   The method is required to use this authentication method.

.. _config-authentication_sms.from:

``from``
========

The phone number from which the SMS are sent.

.. _config.authentication_sms.length:

``length``
==========

The number of figures for the generated authentication code sent by SMS.

The default value is: ``6``

.. _config.authentication_sms.ttl:

``ttl``
=======

The duration in seconds for which the generated codes is still valid.

The default value is: ``5 * 60``

``name``
========

The name of the application used in the text of the SMS.

The default value is: ``Tryton``
