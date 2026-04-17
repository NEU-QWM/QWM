%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%     What and How?      %%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Graphene Sweeping Software
% version 2.0 in July 2016 by BBN Graphene Trio: Jess Crossno, Evan Walsh,
% and KC Fong
%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

function [data] = VNA_vs_JPAParameters_TestPower(TestPowerList, AveragingNumberList, JPAPumpPowerList, JPAPumpFreqList, JPAFluxBiasList, InitialWaitTime)
pause on;
% PumpSource = deviceDrivers.AgilentN5183A();
% PumpSource.connect('19');
% Yoko = deviceDrivers.YokoGS200();
% Yoko.connect('2');
%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%% 
%
% Adapted to Keithley 2400 and DS Instruments SG22000PRO
% April 16, 2026
% Gun Suer
%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
PumpSource = deviceDrivers.SG22000();
PumpSource.connect('172.31.255.67');
Keithley = deviceDrivers.Keithley2400;
Keithley.connect('24');

%%%%%%%%%%%%%%%%%%%%%     RUN THE EXPERIMENT      %%%%%%%%%%%%%%%%%%%%%%%%%
for k = 1:length(JPAPumpPowerList)
    sprintf('Set to %e A, and pump frequency and power at %e GHz and %e dBm, respectively', JPAFluxBiasList(k), JPAPumpFreqList(k)*1e-9, JPAPumpPowerList(k))
    PumpSource.frequency = JPAPumpFreqList(k);
    PumpSource.power = JPAPumpPowerList(k);
    Keithley.value = JPAFluxBiasList(k);
    result = VNA_vs_TestPower(TestPowerList, AveragingNumberList, InitialWaitTime);
    data.S(k,:,:) = result.S;
    PumpSource.output = 'OFF';
    pause on; 
    pause(InitialWaitTime);
    result = GetVNASpec_VNA();
    data.S0(k,:) = result.S;
    PumpSource.output = 'ON';
end
data.Freq = result.Freq;

%%%%%%%%%%%%%%%%%%%%    BACK TO DEFAULT, CLEAN UP     %%%%%%%%%%%%%%%%%%%%%%%%%
pause off;
PumpSource.disconnect(); Keithley.disconnect();
clear PumpSource total_num k Keithley
end