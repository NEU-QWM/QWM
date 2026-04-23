from datetime import timedelta

from core.state_machine.operation import Operation
from core.state_machine.procedure import (
    Direction,
    OperationProcedure,
    Procedure,
)


class MockProcedure(Procedure):
    required_parameters = ["persistenceMaxTimeout"]

    def procedure(self, parameters):
        self.wait(3)


class MockOperationProcedure(OperationProcedure):
    operation_name = "placeholder"
    required_parameters = ["persistenceMaxTimeout"]

    def procedure(self, parameters):
        self.wait(3)


class MockCollectMixture(MockProcedure):
    name = "Collect mixture"
    image_url = "images/Collect_mixture.mp4"
    penalty = timedelta(hours=4)
    direction = Direction.WARMING


class MockCollectMixtureInitial(MockProcedure):
    name = "Stop circulation and recover most of the mixture"
    image_url = "images/Collect_mixture.mp4"
    penalty = timedelta(hours=1)
    direction = Direction.WARMING


class MockCondensingFinalization(MockProcedure):
    name = "Condensing finalization"
    image_url = "images/Condensing.mp4"
    penalty = timedelta(minutes=30)
    direction = Direction.COOLING


class MockCondensingHighPressure(MockProcedure):
    name = "Condensing through needle valve"
    image_url = "images/Condensing.mp4"
    penalty = timedelta(hours=1)
    direction = Direction.COOLING


class MockCondensingLowPressure(MockProcedure):
    name = "Condensing directly from tank"
    image_url = "images/Condensing.mp4"
    penalty = timedelta(minutes=30)
    direction = Direction.COOLING


class MockEvacuateGHS(MockProcedure):
    name = "Evacuate Gas Handling System service side"
    image_url = "images/Vacuum_Pump.mp4"
    penalty = timedelta(minutes=10)


class MockIdleCirculating(MockOperationProcedure):
    name = "System in circulation mode"
    image_url = "images/Circulation.mp4"
    operation_name = "Cool down"


class MockIdleFourKelvin(MockOperationProcedure):
    name = "4K state"
    image_url = "images/4K.mp4"
    operation_name = "Go to 4K state"

    @classmethod
    def display_name(cls, operation: Operation, parameters, state):
        if operation.start.name == "Manual":
            return "Return to 4K state"
        if operation.direction == Direction.COOLING:
            return "Cool down to 4K"
        elif operation.direction == Direction.WARMING:
            return "Warm up to 4K"
        else:
            return "Return to 4K state"


class MockIdleVacuum(MockOperationProcedure):
    name = "Vacuum can evacuated"
    image_url = "images/Vacuum_Pump.mp4"
    operation_name = "Evacuate vacuum can"
    direction = Direction.COOLING


class MockIdleWarm(MockOperationProcedure):
    name = "System at room temperature"
    operation_name = "Warm-up system"
    image_url = "images/System_Warm.mp4"


class MockPulsePreCooling(MockProcedure):
    name = "Pulse pre-cooling"
    image_url = "images/PPC.mp4"
    penalty = timedelta(hours=1.5)
    direction = Direction.COOLING


class MockPulseTubeCooling(MockProcedure):
    name = "Pulse tube cooling"
    image_url = "images/Pulse_Tube.mp4"
    penalty = timedelta(hours=12)
    direction = Direction.COOLING


class MockPulseTubeCoolingFinalization(MockProcedure):
    name = "Pulse tube cooling finalization"
    image_url = "images/Pulse_Tube.mp4"
    penalty = timedelta(hours=12)
    direction = Direction.COOLING


class MockPulseTubeCoolingFinalizationWithoutPPC(MockProcedure):
    name = "Pulse tube cooling without PPC"
    image_url = "images/Pulse_Tube.mp4"
    penalty = timedelta(hours=12)
    direction = Direction.COOLING


class MockPumpRough(MockProcedure):
    name = "Rough pumping vacuum can"
    image_url = "images/Vacuum_Pump.mp4"
    penalty = timedelta(minutes=30)
    direction = Direction.COOLING


class MockPumpTurbo(MockProcedure):
    name = "Pump vacuum can with booster pump"
    image_url = "images/Vacuum_Pump.mp4"
    penalty = timedelta(minutes=30)
    direction = Direction.COOLING


class MockStopCooling(MockProcedure):
    name = "Stop cooling and start recovering mixture"
    image_url = "images/Collect_mixture.mp4"
    penalty = timedelta(minutes=15)
    direction = Direction.WARMING


class MockStopVacuumPumping(MockProcedure):
    name = "Stop pumping vacuum can"
    image_url = "images/Pulse_Tube.mp4"
    penalty = timedelta(minutes=5)
    direction = Direction.COOLING


class MockVentVacuum(MockOperationProcedure):
    name = "System in atmospheric pressure"
    image_url = "images/System_Warm.mp4"
    operation_name = "Vent vacuum can"


class MockWaitUntilWarm(MockProcedure):
    name = "Wait until system warm"
    image_url = "images/Warmup.mp4"
    penalty = timedelta(hours=18)
    direction = Direction.WARMING
