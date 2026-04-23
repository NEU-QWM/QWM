# StateMachine

This is a [StateMachine](https://en.wikipedia.org/wiki/Finite-state_machine)
implementation written in Python for controlling a Cryostat's cooldown and
warmup sequences.

## Requirements

- [Python](https://www.python.org/) `3.10+`
- [pip](https://pypi.org/project/pip/)

---

Below are the core components of the StateMachine. For a full list of entities
and outside world communications, see [the
wiki](https://bluefors.atlassian.net/wiki/spaces/CS2/pages/3097067526/StateMachine+redesign).

## StateMachine and StateMachineConfig

**StateMachine** contains the logic for finding and running sets of operations
for controlling the cryostat. Additionally, it contains functions that expose
the StateMachine's inner state and available actions outside, which are
ultimately shown in the CS2 applications's user interface, mostly through the
Operations card.

**StateMachineConfig** contains the following components:
- name (for clarity, no functional meaning)
- transitions
- parameter_mapping
- loop_procedures
- recovery_paths

Transitions is a directed graph that contains a list of two-tuples of
**Procedures**, each pair defining a possible transition between system states.
Parameter mapping contains the mappings for parameters as defined in
`automation.yaml`, which are made available in the `parameters` dictionary for
procedures.

Optional parameters for loop procedures and recovery path may contain
additional procedures (as a form of single list or two-tuples of transitions,
respectively), that define further functionality.

The transitions as defined by two-tuples of Procedures form a set of possible
paths that the system can execute. When shown to the user or when selected for
execution, this sequence of Procedures form an **Operation** that the
StateMachine can then run.

A default StateMachine implementation contains the `Initial` and `Manual`
Procedures. The StateMachine starts in the `Manual` Procedure, unless some
other Operation was successfully recovered after a non-clean shutdown.

A StateMachine is paired with a Sentinel, containing a set of rules that are
continuously checked during the runtime of the StateMachine.

The available StateMachines can be found in `sm/<sm_name>/statemachine_new.py`.

## Procedure

An executable entity within the StateMachine.

When defining a Procedure, the subclass of Procedure may override the methods:
- `validate`: to if we are in a valid state to start the procedure
- `enter`: executed as a first step (preparations)
- `procedure`: main logic that is run in the phase
- `exit`: executed when exit (cleanup)

The `validate` method yields `ValidationError`s that contain information on why
a specific validation rule did not pass. The `enter`, `procedure` and `exit`
methods can raise a `ProcedureError`, in case the running of the Procedure is
terminated from inside due to some foreseen circumstances.

Procedure's `run` method is used to call these methods in order, and to handle
and pass on the errors that may rise during the validation and running of the
Procedure.

Procedures contain the parameters:
- `name`: Name of the Procedure
- `penalty`: Expected duration in seconds. This can be used to find the
shortest routes in time.
- `required_parameters`: A list of parameters that are needed for the procedure.
- `direction`: Specifies if the procedure is a part of a cooling sequence, a
warming sequence or neither. Used to narrow down the set of sensible operations
the user can take.
- `image_url`: Image for the Procedure.

## OperationProcedure

**OperationProcedures** Procedures, that determine the end points for
operations that are available to the user. The sequence that forms an Operation
may contain both Procedures and OperationsProcedures, but it must end in an
OperationProcedure.

Subclasses of OperationProcedure may override the methods:
- `validate_operation`, check if Operation leading to this Procedure is OK to
start

OperationProcedures must have additional parameters:
- `operation_name`: name of the Operation, may differ from the procedure name
- `priority`: priority of the Operation, to order the list of Operations shown
to the user. Defaults to zero.

## Operation, RunningOperation

Initialized with a sequence of Procedures that end in an OperationProcedure. 

May contain parameters, that need to be set before an Operation can be
validated or serialized.[^1]

[^1]: Possible TODO: separate an Operation containing the parameters and
    validation status to its own class.

An Operation contains the methods:
- validate: used to check if the operation is valid to enter. Checks the first Procedure's `validate` and the goal OperationProcedure's `validate_operation` methods' results.
- serialize: used to show the operations for the use in the CS2 user interface

**RunningOperation** is composed from an Operation and a set of parameters
related to the running an operation:
- operation
- parameters: concrete parameter values used for running the operation's
procedures
- current_procedure: the procedure currently under execution
- start_time: time the Operation was first started
- running: boolean field indicating whether the end of the goal
OperationProcedure has been reached
- uuid: an identifier generated for each Operation started for logging purposes
- last_start_time: used to calculate elapsed time spent in the procedure from
the start of the Operation or after recovering
- _elapsed_time_in_seconds: in case of an error interrupting the running of an
Operation, used after recovery to add to the runtime calculated from
last_start_time for the run after recovery

RunningOperation contains the methods:
- serialize: For showing the currently running operation and progress in the
CS2 user interface, and for logging the progress in database
- deserialize: Used in recovery, to rebuild the RunningOperation and continue
its execution

---

## Communication with Backend

### Java -> Python calls
Java API to python provided by `libpython-clj` is used to call the StateMachine
from Java. The methods may return values or raise pre-determined errors, that
are handled on the Java side.

The interface provided for the Java side is exposed in the `automation.py` file
at the root of the module.

### System state, device commands
For everything else, the communication happens over HTTP API:
- Fetching the system state
- Sending device commands
- Alerting the Backend of errors encountered while running an Operation
- Persisting the currently running operation in the database, for recovery and logging.

## Sentinel

The `sentinel` module contains a slightly modified Py-Rete implementation
([original](https://github.com/cmaclell/py_rete)) to create a set of production
rules applied to the `State` object. The rules are expected to return side
effects in form of a dictionary object that is sent to the CS2 using the
`notify` message. These side effects include for instance logging alerts when
certain threshold levels are exceeded.

## Tests

There are tests located in the `tests/` directory. They can be also used as an
example of how to implement a StateMachine and how to use the features
provided  not yet used in production configurations.

