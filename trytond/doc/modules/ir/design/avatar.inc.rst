.. _model-ir.avatar:

Avatar
======

*Avatar* is a :class:`~trytond.ir.resource.ResourceMixin` that stores a single
`avatar <https://en.wikipedia.org/wiki/Avatar_(computing)>`_ for any
:meth:`~trytond.model.avatar_mixin` record.
Each *Avatar* record has a :abbr:`UUID (Universally Unique Identifier)` which
is used to construct a URL that returns the picture.
A version of the picture is stored in a cache for each size requested.
