Project Plan Module
###################

The Project Plan module adds planning features on top of the Project
module.


Allocation
**********

An allocation links together an employee, a task and a percentage. It
defines which part of his time the employee should dedicate to this
task.


Work
****

The Work model is extended to support planning features:

- Tasks dependencies: Each work may have predecessor and
  successors. Predecessor and successor must share the same parent
  project.
- tasks leveling, I.E. automatically delay some task to avoid
  overallocation of resources.
- Early Start and Late End computation: If Constraint Start and
  Constraint End are set on a work, on its parent work or on one of
  the predecessors/successors, the Early Start and Late End dates (but
  also Late Start and Early Finish dates) are computed automatically.
- Resource allocation: Each task may allocate one or more resource
  (I.E. a certain amount of time of an employee).


The *Task Leveling* wizard allow to level a group of tasks to avoid
eventual overallocation of resources, It will delay some tasks
depending on task precedencies and task sequences.
