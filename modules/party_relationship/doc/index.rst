Party Relationship Module
#########################

The party relationship module allows to define different types of relations
between parties.

Each relation is defined by a relation type. A reverse relation type can be
defined, so  when creating a relation of a type, the reverse relation will be
automatically created.

It is possible to order parties by how closely related they are to a defined
party. The distance is calculated based on the number of steps it takes to get
from the defined party to another. By default all the different types of
relationship are considered, but this can be limited by adding
``relation_usages`` to the context.

Configuration
*************

The party_relationship module use the section `party_relationship` to retrieve
some parameters:

- `depth`: The maximum number of steps to consider when calculating the
  distance between parties.
  The default value is `7`.
