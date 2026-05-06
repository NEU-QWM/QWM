%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%     What and How?      %%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Graphene SPD Software
% version 1.0 in Nov 2019 by BBN Graphene Trio: Jess Crossno, Evan Walsh,
% and KC Fong
%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

function [data] = VNA_vs_PumpFreq(FreqList, InitialWaitTime)
pause on;
% PumpSource = deviceDrivers.AgilentN5183A();
% PumpSource.connect('19');
% FreqList = FreqList*1e-9; 
%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%% 
%
% Adapted to DS Instruments SG22000PRO
% April 16, 2026
% Gun Suer
%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
PumpSource = deviceDrivers.SG22000();
PumpSource.connect('172.31.255.67');

%%%%%%%%%%%%%%%%%%%%%     RUN THE EXPERIMENT      %%%%%%%%%%%%%%%%%%%%%%%%%
PumpSource.frequency = FreqList(1);
PumpSource.output = '1';
pause(InitialWaitTime);
for k=1:length(FreqList)
    datetime('now')
    sprintf('The %dth data point with freq %e', k, FreqList(k))
    PumpSource.frequency = FreqList(k);
    result = GetVNASpec_VNA();
    data.S(k,:) = result.S;
end
data.Freq = result.Freq;
PumpSource.output = '0';
pause(InitialWaitTime);
result = GetVNASpec_VNA();
data.S0 = result.S;
PumpSource.output = '0';

%%%%%%%%%%%%%%%%%%%%    BACK TO DEFAULT, CLEAN UP     %%%%%%%%%%%%%%%%%%%%%%%%%
pause off;
PumpSource.disconnect();
clear VNA;
end