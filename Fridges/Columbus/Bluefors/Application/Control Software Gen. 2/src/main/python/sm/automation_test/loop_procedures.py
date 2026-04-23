from core.state_machine.procedure import Procedure


class Loop(Procedure):
    name = "Loop"

    def procedure(self, parameters):
        self.wait(1)


class LongLoop1(Procedure):
    name = "Long loop"

    def procedure(self, parameters):
        self.wait(3)


class LongLoop2(Procedure):
    name = "Long loop 2"

    def procedure(self, parameters):
        self.wait(3)
