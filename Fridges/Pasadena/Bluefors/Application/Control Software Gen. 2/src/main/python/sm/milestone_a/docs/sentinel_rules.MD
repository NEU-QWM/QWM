## Here are sentinel rules for test_case1

Any following rule true should generate error or warning when asked from service.


1. (temperature(T1) > 100C)
   1. Warning("Temperature of pump T1 above 100C")

2. (pressure(P2) > 10mbar) and (state(T1) == on)
   1. Warning("Pressure for pump T1 too high for stable operation")

3. (pressure(P2) > 20mbar) and (state(T1) == on)
   1. Error("Pressure for pump T1 too high for operation")

4. (flow(Flow1) > xxx) and (state(T1) == on)
   1. Warning("Flow in system exceptionally high"

5. (temperature(Cooling_water_meter) > 30)
   1. Warning("Cooling water line above 30C from pump T1")

6. (flow(Cooling_water_meter) < xx and not(state==idle or state==manual))
   1. Warning("Cooling water line flow too low")


