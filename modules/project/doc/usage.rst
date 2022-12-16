*****
Usage
*****

You can find things related to projects under the [:menuselection:`Projects`]
main menu item.

.. _Setting up projects and tasks:

Setting up projects and tasks
=============================

In Tryton both `Projects <concept-project.work.project>` and
`Tasks <concept-project.work.task>` are just types of
`Work Efforts <model-project.work>`.

In many cases projects and tasks can be used interchangeably.
However, it is often best practice to use projects for larger more complex
jobs and then break these down into sub tasks for the smaller individual
parts of each project.
To allow you to do this you can give each project or task a parent, and
any number of children.

.. tip::

   With your projects structured like this any time and effort expended on a
   project or task will then also be included as part of its parent's total
   effort.
