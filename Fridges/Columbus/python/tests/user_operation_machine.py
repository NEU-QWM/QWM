import logging
from datetime import timedelta

from core.state_machine.procedure import Procedure, OperationProcedure, Initial, Manual
from core.state_machine.config import StateMachineConfig
from core.state_machine.exceptions import ValidationError

# from core.state_machine import StateMachineBase, GlobalParameters, Parameter, Procedure, \
#    OperationProcedure, ProcReturnDone, ProcReturnError, ProcReturnTimeout

import core.api


logger = logging.getLogger(__name__)


class Constants:
    NEXT_STEP_DELTA = 0.1
    OTHER_STEP_DELTA = 0.2
    PREV_STEP_THRESHOLD = 10
    TARGET_TEMPERATURE = 4
    # START_DT = 2


parameters = {
    "TARGET_TEMPERATURE": "TARGET_TEMPERATURE",
    "PREV_STEP_THRESHOLD": "PREV_STEP_THRESHOLD",
    "NEXT_STEP_DELTA": "NEXT_STEP_DELTA",
    "OTHER_STEP_DELTA": "OTHER_STEP_DELTA",
    "failValidation": "failValidation",
}


class First(Procedure):
    name = "First"
    image_url = "/images/start.png"
    penalty = timedelta(seconds=4 * 60 * 60)

    def validate(self, parameters, state):
        if core.api.state["fail_recovery"]:
            yield ValidationError(-1, "Failed recovery")

    def procedure(self, parameters):
        logger.debug("START")


class Another(Procedure):
    name = "Another"
    image_url = "/images/50k.png"
    penalty = timedelta(seconds=6 * 60 * 60)

    def validate(self, parameters, state):
        if core.api.state["fail_recovery"]:
            yield ValidationError(-1, "Failed recovery")

    def procedure(self, parameters):
        logger.debug("ANOTHER: %d", Constants.PREV_STEP_THRESHOLD)


class Next(OperationProcedure):
    name = "Next"
    operation_name = "NextOperation"
    image_url = "/images/ppc.png"
    penalty = timedelta(seconds=4 * 60 * 60 + 1)

    def validate(self, parameters, state):
        if core.api.state["fail_recovery"]:
            yield ValidationError(-1, "Failed recovery")

    def procedure(self, parameters):
        logger.debug("NEXT WAIT")
        # Machine.test_value = 0.6


class Other(Procedure):
    name = "Other"
    image_url = "/images/4K.png"

    def procedure(self, parameters):
        pass


class Continue(OperationProcedure):
    name = "Continue"
    operation_name = "Continue"
    penalty = timedelta(seconds=1)
    required_parameters = ["failValidation"]

    def validate(self, parameters, state):
        if parameters["failValidation"]:
            yield ValidationError(-1, "Validation failed due to parameter value")

    def procedure(self, parameters):
        pass

    def idle(self, parameters):
        pass


class Final(OperationProcedure):
    name = "Final"
    operation_name = "Final"
    image_url = "/images/final.png"

    def validate(self, parameters, state):
        if not core.api.state["test_value"] > 0.5:
            yield ValidationError(-1, "Validation of Continue failed")

    def validate_operation(self, from_procedure, operation, parameters, state):
        if operation.procedures[0] == Continue and from_procedure != Continue:
            yield ValidationError(code=-1, message=f"Cannot start operation {self.name} from {from_procedure}")

    def procedure(self, parameters):
        pass


class Loop(Procedure):
    name = "Loop"


class LongLoop1(Procedure):
    name = "LongLoop1"
    duration = timedelta(hours=1)


class LongLoop2(Procedure):
    name = "LongLoop2"


class StartRecoveryProcedure(Procedure):
    name = "Start Recovery Procedure"


class StartRecoveryProcedure2(Procedure):
    name = "Start Recovery Procedure2"


sm_config = StateMachineConfig(
    name="test",
    transitions=(
        (Initial, First),
        (Initial, Continue),
        (Continue, Final),
        (First, Another),
        (Another, Next),
        (Another, Other),
        (Next, Next),
        (Next, Final),
        (Other, Final),
    ),
    loop_procedures={Next: [(Loop,), (LongLoop1, LongLoop2)]},
    parameter_mapping=parameters,
    # StartRecoveryProcedure -> Next -> Final
    recovery_paths=[(StartRecoveryProcedure, Next, Final), (StartRecoveryProcedure2, Another, Final)],
)
