from core.device import device
from typing import Literal

NumericMappings = Literal[
    "P1_PRESSURE",
    "P2_PRESSURE",
    "P3_PRESSURE",
    "P4_PRESSURE",
    "P5_PRESSURE",
    "P6_PRESSURE",
    "4K_TEMPERATURE",
    "50K_TEMPERATURE",
    "B1A_SPEED",
    "B1B_SPEED",
    "B1C_SPEED",
    "B2_SPEED",
    "COOLING_WATER_TEMPERATURE",
    "FLOW_VALUE" "R1",
    "SM_SIMPLE_TEMPERATURE",
    "STILL_TEMPERATURE",
    "Valves",
    "boosterBasePressureLimit",
    "boosterPumpingMaxTime",
    "boosterStartPressureLimit",
    "coolingWaterLimitToStartPumping",
    "heaterPowerOffTemp",
    "heaterPowerOnTemp",
    "initialValueWaitTime",
    "name",
    "roughPumpingMaxTime",
    "statemachine.persistenceMaxTimeout",
    "temperatureCs2testOverWarning",
    "zeroCirculationFlowLimit",
]
BooleanMappings = Literal[
    "B1_ENABLED",
    "HEATSWITCH_MXC_ENABLED",
    "P1_ENABLED",
    "PULSE_TUBE_ENABLED",
    "HEATSWITCH_STILL_ENABLED",
]
DictMappings = Literal[
    "statemachine.currentOperation", "statemachine.currentProcedure", "currentOperation", "currentProcedure"
]
