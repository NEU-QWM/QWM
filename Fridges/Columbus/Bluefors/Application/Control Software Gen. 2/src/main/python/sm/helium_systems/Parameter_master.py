# This list contains the parameter set needed to run state machine 'dilution systems'
# This can be copied to system-configuration.yaml as needed
#
"""
stateMachine:
  name: dilution-systems
  settings:
  # SM GENERIC
    persistenceMaxTimeout: 60
    # PumpRough parameters
    dilutionRefrigeratorEvacuatedPressure: 0.01
    roughPumpingMaxTime: 10800
    turboPumpingMaxTime: 10800
    pumpRoughFinalPressure: 0.001
    # PumpTurbo parameters
    vacuumPressureErrorTolerance: 1.05
    # If actualPressure < vacuumPressureErrorTolerance * desiredPressure, all is well.
    pumpTurboFinalPressure: 0.00005
    turboPumpMaxSpeedStartup: 50
    serviceBoosterPumpAvailable: True
    # Pulse tube cooling parameters
    pulseTubeCoolingMaxTime: 259200 # 3 days
    pulseTubeCoolingFinalTemperature: 25
    pulseTubeCoolingTargetPressure: 0.0000003 # bar
    # Pulse pre-cooling parameters
    ppcCycleDuration: 5400
    ppcPumpingTime: 15
    ppcInletTime: 8
    ppcPressureLimit: 0.05 # for blocked dilution refrigerator unit
    # Condensing parameters
    initialTankPressure: 0.9
    vacuumPressureLimit: 5.e-8
    condensingTriggerHeatswitches: 0.04
    systemBlockedTimer: 10800
    condensingPressureDropMaxTime: 7200
    condensingPressureDifferenceMaxTime: 7200
    stillHeatingPower: 0.008
    # Warmup parameters
    numberOf4KHeaters: 2
    serviceEmptyPressure: 0.01
    coolingStoppingTime: 900  # 15 minutes
    # Collect mixture
    mixtureCollectingPressureLimit: 0.05
    collectExtraMixtureTimeLimit: 1800
    softVacuumCycles: 2
    p2PressureLimitMixtureInTank: 5.e-5
    p4PressureLimitMixtureInTank: 0.08
    collectMixtureTimeLimit: 36000  # 10 hours
    tankPressureStabilizationTime: 1800
    pressureStabilizationSqLimit: 0.000005
    tankPressureStabilizationMaxTime: 36000  # 10 hours
    4KHeaterTemperatureLimit: 300
    stillHeaterTemperatureLimit: 287
    warmupMaxTime: 129600  # 36 hours
    systemWarmTemperature: 290 # Threshold for system being warm
    systemVentedPressure: 0.990 #Threshold for system being vented to atmospheric pressure
    numberOf4KHeaters # How many 4K heaters system has
"""
