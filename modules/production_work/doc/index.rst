Production Work Module
######################

The production work module allows to manage work order for each production.
It also adds in the production cost for the work cost.

Work Center
***********

Work center are places in the warehouse where production operations are
performed. They can be organized in a tree structure and each center can be
linked to a category. A cost can be defined on the work center with two
methods: `Per Cycle` or `Per Hour`.

Work
****

Works define for a production which operation to do at which work center.
They also contains the number of cycles consumed to perform the operation.

The work can be in one of these states:

* Request

  The linked production is still waiting.

* Draft

  The production has started but no cycle was already consumed.

* Waiting

  There are some draft cycles planned.

* Running

  There is at least one running cycle.

* Finished

  All the cycles are done (or cancelled).

* Done

  The production is done.

The works are created on the waiting production using the linked routing. For
each step of the routing, a work is created with the operation. The work center
is set if the operation has a work center category, by choosing a children work
center of this category. Or if the operation has no category, it is the
production work center that is used.

Cycle
*****

Cycles are used to count the consumption and the duration of the work. It also
records the effective cost from the work center.

The cycle can be in one of this states:

* Draft
* Running
* Done
* Cancelled
