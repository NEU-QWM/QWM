import inspect
import functools
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Callable, ClassVar, Optional

from core.device.command import Alert, AlertSeverity, SentinelAlert, SentryAlert
from py_rete import Cond, Filter, Production, V
from py_rete.conditions import AND


@dataclass
class AlertRule:
    """ """

    severity: AlertSeverity
    code: int
    msg: str
    filter: Callable
    variables: tuple[str, ...] = field(init=False)
    applies_in_procedures: list = field(default_factory=list)
    connections_to_check: list[tuple[str, str]] = field(default_factory=list)
    alert_class: ClassVar[type[Alert]]

    def __post_init__(self):
        """
        'Hoist' the variable names from the lambda function: They are bound
        as py_rete variables, and fetched over API for each Sentinel query.

        If current_procedure is not used already in the filter function itself,
        but only in the applies_in_procedures additional condition, add it to
        variables used by this rule.
        """
        self.variables = self.filter.__code__.co_varnames

        if "current_procedure" not in self.variables and self.applies_in_procedures:
            self.variables = (*self.variables, "current_procedure")

        if self.connections_to_check:
            self.variables = (*self.variables, "existing_connections")

    def to_alert(self, msg_args):
        return SentinelAlert(self.severity, self.code, self.msg.format(**msg_args))

    def to_production(self, parameters, automation_parameters):
        filter = self.get_filter(parameters, automation_parameters)

        @_state_production(self.variables, filter, self.applies_in_procedures, self.connections_to_check)
        def _alert(net):
            msg_args = {wme.attribute: wme.value for wme in net.wmes}
            return self.alert_class.from_rule(self, msg_args)

        return _alert

    def get_filter(self, parameters, automation_parameters):
        return self.filter


@dataclass
class ParameterizedRule(AlertRule if TYPE_CHECKING else object):
    """
    Parameterized rules add fields sentinel_parameters (specified in Sentinel
    config) and automation_parameters (from automation.yaml). These need to be
    also included in the filter lambda function as arguments, but they are
    bound before the rule is passed on to py_rete network.
    """

    sentinel_parameters: list[str] = field(default_factory=list)
    automation_parameters: list[str] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        self.variables = tuple(v for v in self.variables if v != "sentinel_parameters" and v != "automation_parameters")

    def get_filter(self, parameters, automation_parameters):
        """
        Function used to bind parameters and return a proper filter function to
        py_rete, that only depends on fridge state variables.
        """
        if (
            "sentinel_parameters" not in inspect.getfullargspec(self.filter).args
            or "automation_parameters" not in inspect.getfullargspec(self.filter).args
        ):
            raise Exception(
                "ParameterizedRule filter function missing sentinel_parameters or automation_parameters arguments"
            )

        try:
            sentinel_parameters = {key: parameters[key] for key in self.sentinel_parameters}
            automation_parameters = {key: automation_parameters[key] for key in self.automation_parameters}
        except KeyError:
            raise Exception(
                f"Not all parameters available for a Sentinel rule, missing Sentinel parameters: {set(self.sentinel_parameters) - set(parameters.keys())} or Automation parameters: {set(self.automation_parameters) - set(automation_parameters.keys())}"
            )
        f = functools.partial(
            self.filter, sentinel_parameters=sentinel_parameters, automation_parameters=automation_parameters
        )
        if set(inspect.getfullargspec(f).kwonlyargs) != {"sentinel_parameters", "automation_parameters"}:
            raise Exception(
                "ParameterizedRule sentinel_parameters and automation_parameters arguments should be given last to the filter function"
            )
        return f


@dataclass
class SentinelRule(AlertRule):
    alert_class = SentinelAlert


@dataclass
class ParameterizedSentinelRule(ParameterizedRule, SentinelRule):
    pass


@dataclass
class SentryRule(AlertRule):
    command: Optional[Callable] = None
    deprecate: Optional[timedelta] = None
    alert_class = SentryAlert

    def action(self, parameters):
        pass

    def execute(self, parameters):
        if self.command:
            args = inspect.getfullargspec(self.command)
            if "parameters" in args.args:
                self.command(parameters)
            else:
                self.command()
        else:
            self.action(parameters)


@dataclass
class ParameterizedSentryRule(ParameterizedRule, SentryRule):
    pass


def _state_production(variables, filter_function, procedures, connections):
    """
    Used as decorator -- see the py_rete documentation for details.

    The end result looks something like this:

    @Production(Fact(color='red'))
    def alert_something_red():
        print("I found something red")

    In our case, the Production first checks for presence of variables used in
    the filter_function in state (as fetched from cryostat), and only if they
    are all present, checks the condition defined by the filter_function.

    Additionally, the rules can have a list applies_in_procedures: That defines
    another filter condition that must be true for the alert to be triggered,
    i.e. current procedure must be one of the procedures listed.
    """
    _production = _state_vars(*variables) & (Filter(filter_function))
    if procedures:
        _production = _production & Filter(lambda current_procedure: current_procedure in procedures)
    if connections:
        _production = _production & Filter(
            lambda existing_connections: any([c in existing_connections for c in connections])
        )

    return Production(_production)


def variable_to_condition(variable) -> Cond:
    """
    Maps a variable name to py_rete condition, that can be evaluated against a
    working memory (WME) entry.

    E.g. Cond("State", "P1_PRESSURE", V("P1_PRESSURE")) evaluates to True
    against a WME("State", "P1_PRESSURE", 10), and binds the value 10 to
    variable P1_PRESSURE, that can be then used in chained Filter expression.
    """
    return Cond("State", variable, V(variable))


def _state_vars(*variables):
    """
    Checks the existence of all variables used in the outer Filter expression
    """
    v = AND(*[variable_to_condition(v) for v in variables])
    return v & Filter(lambda: all([V(variable) is not None for variable in variables]))
