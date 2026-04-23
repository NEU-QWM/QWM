class ProcedureError(Exception):
    title = "Procedure error"
    prefix = "Running of procedure \"{}\" failed: "
    def __init__(self, code=1649, message=""):
        super().__init__(message)
        self.title = "Procedure error"
        self.code = code
        self.message = message


class ValidationError(Exception):
    title = "Procedure validation error"
    prefix = "Validation of procedure \"{}\" failed: "
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class ProcStoppedException(Exception):
    pass


class OperationNotFound(Exception):
    pass


class OperationFailedToStart(Exception):
    def __init__(self):
        super().__init__("Operation failed to start")


class StateMachineNotRunning(Exception):
    def __init__(self):
        super().__init__("Statemachine not running")


class OperationParametersNotFound(Exception):
   pass
