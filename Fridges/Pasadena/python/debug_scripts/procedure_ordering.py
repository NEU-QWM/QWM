from configuration.sm.dilution_systems.statemachine import config, IdleCirculating, IdleFourKelvin
from core.state_machine.procedure import Manual

sm = config.sm()

# Examples:
sm.operations.get_procedures(Manual)

sm.operations.get_procedures(IdleCirculating)

sm.operations.get_procedures(IdleFourKelvin)
