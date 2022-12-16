*************
Configuration
*************

The *Product Image Module* uses some settings from the ``[product]`` section of
the :doc:`configuration file <trytond:topics/configuration>`.

.. _config-product-image_filestore:

``image_filestore``
===================

This configuration value indicates whether the image should be stored in the
:py:mod:`trytond:trytond.filestore` (``True``) or the database (``False``).

The default value is: ``False``

``ìmage_prefix``
================

This is the prefix to use with the :py:mod:`trytond:trytond.filestore`.
This value is only used when the `image_filestore
<config-product-image_filestore>` setting is in use.

The default value is: ``None``

``image_base``
==============

The base URL for the images, without the path.

The default value is generated from the `hostname
<trytond:topics-configuration>` configuration setting.

``image_timeout``
=================

The maximum time in seconds that the image can be stored in cache.

The default value is: ``365 * 24 * 60 * 60`` (1 year)
