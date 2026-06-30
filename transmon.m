% Calculate transmon properties for an NbSe2/WSe2/NbSe2 Josephson junction
% with layer number NL (integer), external capacitance Cext (in fF), to
% achieve a desired target value for a given property (string format).
% Choices of properties include 'ratio' (EJ/EC), 'f01' (qubit frequency),
% 'alpha' (anharmonicity), 'area' (junction area), 'Ic' (critical
% current, in A), and 'Rn' (normal state resistance, in Ohms). The results
% will be displayed in the command window in appropriate units (indicated
% below).
% Jesse Balgley, 10/31/2023, revised 08/26/2024

function transmon(NL,Cext,property,target)

% Fundamental constants
ee = 1.6e-19; % elementary charge in C
hh = 6.63e-34; % Planck's constant in J*s
hbar = 1.054e-34; % reduced Planck constant in J*s
phi0 = hbar/(2*ee); % reduced flux quantum
epsilon0 = 8.85e-12; % permittivity of free space in F/m

% WSe2 properties
kappa_th = 7.8; % theoretical dielectric constant of WSe2, DOI: 10.1038/s41699-018-0050-x
kappa_exp = 6.6; % experimental microwave dielectric constant of WSe2
kappa = kappa_th;
t = 0.65e-9; % thickness of WSe2 monolayer (in m)
jc = [-1.02960664515343 25.4877749256053]; % jc vs layer # exponential dependence as of 12/20/2023
% jc = [-0.982077347020507 24.8984304925335]; % jc vs layer # exponential dependence as of 08/26/2024
RnA = [0.863421269574061 -30.4559224020546]; % RnA vs layer # exponential dependence as of 08/26/2024
% RnA = [4.12609459499836	-25.4474046496483]; % RnA vs layer # for hBN
% RsgA = [1.37108782801149 -33.1831115622768]; % Rsg*A vs layer # exponential dependence as of 2/22/2024
beta = [0.675519010673828 -3.87881299678496]; % beta_mccumber vs layer # exponential dependence for > 7L

% Setting up the calculation
A_calc = (0:0.001:10000)*1e-12; % range of area to calculate qubit properties (in m^2)
NL_calc = NL; % input WSe2 thickness (in number of layers)
C_ext = Cext*1e-15; % input external shunt capacitance (in F)

C_calc = kappa*epsilon0*A_calc./(NL_calc*t)+C_ext; % total capacitance
EC_calc = ee^2./(2.*C_calc); % charging energy
EJ_calc = phi0*exp(NL_calc*jc(1)+jc(2)).*A_calc; % Josephson energy
f01_calc = (sqrt(8*EJ_calc.*EC_calc)-EC_calc)/hh; % qubit frequency
Q_calc = exp(NL_calc*beta(1) + beta(2));

% This block finds the closest value to the target for the desired property
% and returns the index of that value to compute the remaining properties.
if strcmpi(property,'ratio') == 1
    [~,ind_min] = min(abs((EJ_calc./EC_calc)-abs(target)));
elseif strcmpi(property,'f01') == 1
    [~,ind_min] = min(abs((f01_calc/1e9)-abs(target)));
elseif strcmpi(property,'alpha') == 1
    [~,ind_min] = min(abs((EC_calc/hh/1e6)-abs(target)));
elseif strcmpi(property,'EC') == 1
    [~,ind_min] = min(abs((EC_calc/hh/1e6)-abs(target)));
elseif strcmpi(property,'area') == 1
    [~,ind_min] = min(abs((A_calc/1e-12)-abs(target)));
elseif strcmpi(property,'Ic') == 1
    [~,ind_min] = min(abs((exp(NL_calc*jc(1)+jc(2)).*A_calc)-abs(target)));
elseif strcmpi(property,'EJ') == 1
    [~,ind_min] = min(abs((EJ_calc/hh/1e9) - abs(target)));
elseif strcmpi(property,'Rn') == 1
    [~,ind_min] = min(abs((exp(NL_calc*RnA(1)+RnA(2))./A_calc)-abs(target)));
else
    disp('Invalid property. Please try again.')
    return
end

% Tabulate all relevant qubit properties
qubit.NL = NL_calc; % WSe2 thickness (in number of layers)
qubit.A = A_calc(ind_min)/1e-12; % junction area (in um^2)
qubit.C_ext = C_ext/1e-15; % external capacitance (in fF)
qubit.C_jn = (C_calc(ind_min)-C_ext)/1e-15; % junction capacitance (in fF)
qubit.C_tot = C_calc(ind_min)/1e-15; % total capacitance (in fF)
qubit.EC = EC_calc(ind_min)/hh/1e9; % charging energy (in GHz)
qubit.p_jn = 100*qubit.C_jn/qubit.C_tot; % junction participation ratio (in %)
qubit.Ic = exp(NL_calc*jc(1)+jc(2)).*A_calc(ind_min); % junction critical current (in nA)
qubit.EJ = EJ_calc(ind_min)/hh/1e9; % Josephson energy (in GHz)
qubit.Rn = exp(NL_calc*RnA(1)+RnA(2))./A_calc(ind_min); % junction normal state resistance (in Ohms)
qubit.f01 = f01_calc(ind_min)/1e9; % qubit frequency (in GHz)
qubit.alpha = -EC_calc(ind_min)/hh/1e6; % qubit anharmonicity (in MHz)
qubit.ratio = EJ_calc(ind_min)/EC_calc(ind_min); % EJ/EC ratio
qubit.Q = Q_calc;
qubit.beta = Q_calc^2;
qubit.Rsg = Q_calc/(qubit.C_jn*1e-15)/(2*pi*qubit.f01*1e9);
% qubit.Rsg = exp(NL_calc*RsgA(1)+RsgA(2))./A_calc(ind_min); % junction subgap resistance (in Ohms)
disp(qubit)

end