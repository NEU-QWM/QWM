from __future__ import annotations
from typing import TYPE_CHECKING
import inspect

from py_rete.beta import ReteNode
from py_rete.common import V

if TYPE_CHECKING:  # pragma: no cover
    from typing import List
    from typing import Callable
    from py_rete.network import ReteNetwork


class FilterNode(ReteNode):
    """
    A beta network node. Takes a function, passes variables in as kwargs, and
    executes it. If the code evaluates to True (boolean), then it activates the
    children with the token/wme.
    """

    def __init__(self, children: List[ReteNode],
                 parent: ReteNode,
                 func: Callable,
                 rete: ReteNetwork):
        super().__init__(children=children, parent=parent)
        self.func = func
        self._rete_net = rete

    def get_function_result(self, token, wme, binding):
        args = inspect.getfullargspec(self.func)[0]
        fnargs = {}
        for arg in args:
            if arg == 'net':
                fnargs[arg] = self._rete_net
            elif arg == 'facts':
                fnargs[arg] = self._rete_net.facts
            elif arg == 'binding':
                fnargs[arg] = binding
            elif binding[V(arg)] in self._rete_net.facts:
                fnargs[arg] = self._rete_net.facts[binding[V(arg)]]
            else:
                fnargs[arg] = binding[V(arg)]

        return self.func(**fnargs)

    def left_activation(self, token, wme, binding):
        """
        :type binding: dict
        :type wme: WME
        :type token: Token
        """
        result = self.get_function_result(token, wme, binding)
        if bool(result):
            for child in self.children:
                child.left_activation(token, wme, binding)
