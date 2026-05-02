% CLASS SRS860 - Instrument driver for the SRS 860 lock-in

% Original Author for SR865: Evan Walsh (evanwalsh@seas.harvard.edu)
% Editor for SR860: Gun Suer (suer.g@northeastern.edu) 
% Modified for SR860 compatibility

% Copyright 2026 NEU Quantum Wave-Matter
%
% Licensed under the Apache License, Version 2.0

classdef (Sealed) SRS860 < deviceDrivers.lib.GPIB
    
    properties
        timeConstant
        inputCoupling
        sineAmp
        sineFreq
        DC
        scanMode
        scanTime
        scanInterval
        scanDC_start
        scanDC_end
    end

    properties (SetAccess=private)
        R
        theta
        X
        Y
        XNoise
        YNoise
        scanState
    end

    properties(Constant)
        timeConstantMap = containers.Map(num2cell(0:21), num2cell(kron(10.^(-6:4), [1, 3])));
        inputCouplingMap = containers.Map({'AC', 'DC'}, {uint32(0), uint32(1)});
        scanIntervalMap = containers.Map(num2cell(0:16), {.008, .016, .031, .078, .155, .469, .938, 1.875, 4.688, 9.375, 28.12, 56.25, 112.5, 337, 675, 1350, 2700});
    end
    
    methods
        function obj = SRS860()
        end
        
        % Filter time constant
        function val = get.timeConstant(obj)
            val = obj.timeConstantMap(uint32(str2double(obj.query('OFLT?'))));
        end
        function obj = set.timeConstant(obj, value)
            inverseMap = invertMap(obj.timeConstantMap);
            mapKeys = keys(inverseMap);
            [~, index] = min(abs(value - cell2mat(mapKeys)));
            obj.write('OFLT %d', inverseMap(mapKeys{index}));
        end
        
        % Input coupling
        function val = get.inputCoupling(obj)
            inverseMap = invertMap(obj.inputCouplingMap);
            val = inverseMap(uint32(str2double(obj.query('ICPL?'))));
        end
        function obj = set.inputCoupling(obj, value)
            assert(isKey(obj.inputCouplingMap, value), 'Oops! the input coupling must be one of "AC" or "DC"');
            obj.write('ICPL %d', obj.inputCouplingMap(value));
        end
        
        % Reference frequency (SR860 max = 500 kHz)
        function val = get.sineFreq(obj)
            val = str2double(obj.query('FREQ?'));
        end
        function obj = set.sineFreq(obj, value)
            assert(isnumeric(value) && (value >= 0.001) && (value <= 500000), ...
                'Oops! The reference frequency must be between 1 mHz and 500 kHz');
            obj.write('FREQ %E',value);
        end
        
        % Sine output amplitude (SR860 min = 1 µV)
        function val = get.sineAmp(obj)
            val = str2double(obj.query('SLVL?'));
        end
        function obj = set.sineAmp(obj, value)
            assert(isnumeric(value) && (value >= 0.000001) && (value <= 2.000000000), ...
                'Oops! The sine amplitude must be between 1 µV and 2 V');
            obj.write('SLVL %E',value);
        end
        
        % Sine output DC Offset
        function val = get.DC(obj)
            val = str2double(obj.query('SOFF?'));
        end
        function obj = set.DC(obj, value)
            assert(isnumeric(value) && (value >= -5.000000000) && (value <= 5.000000000), ...
                'Oops! The DC offset must be between -5 V and 5 V');
            obj.write('SOFF %E',value);
        end
        
        % Getter for X and Y at the same time
        function [X, Y] = get_XY(obj)
            values = textscan(obj.query('SNAP? 0, 1'), '%f', 'Delimiter', ',');
            X = values{1}(1);
            Y = values{1}(2);
        end
        
        % Getter for R and theta
        function [R, theta] = get_Rtheta(obj)
            values = textscan(obj.query('SNAP? 2, 3'), '%f', 'Delimiter', ',');
            R = values{1}(1);
            theta = values{1}(2);
        end
        
        % Getter for X and Y Noise
        function [XNoise, YNoise] = get_XYNoise(obj)
            values = textscan(obj.query('SNAP? 10, 11'), '%f', 'Delimiter', ',');
            XNoise = values{1}(1);
            YNoise = values{1}(2);
        end        
        
        % Individual getters
        function R = get.R(obj)
            R = str2double(obj.query('OUTP? 2'));
        end
        
        function theta = get.theta(obj)
            theta = str2double(obj.query('OUTP? 3'));
        end
        
        function X = get.X(obj)
            X = str2double(obj.query('OUTP? 0'));
        end
        
        function Y = get.Y(obj)
            Y = str2double(obj.query('OUTP? 1'));
        end

        function XNoise = get.XNoise(obj)
            XNoise = str2double(obj.query('OUTP? 10'));
        end
        
        function YNoise = get.YNoise(obj)
            YNoise = str2double(obj.query('OUTP? 11'));
        end        
        
        function auto_phase(obj)
            obj.write('APHS');
        end
        
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%        
% Scan Functions
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%        
        
        function val = get.scanMode(obj)
            val = str2double(obj.query('SCNEND?'));
        end
        
        function obj = set.scanMode(obj,val)
            obj.write('SCNEND %d',val)
        end
        
        function scanEnable(obj)
            obj.write('SCNENBL ON')
        end
        
        function scanDisable(obj)
            obj.write('SCNENBL OFF')
        end
        
        function scanRun(obj)
            obj.write('SCNRUN')
        end
        
        function scanReset(obj)
            obj.write('SCNRST')
        end
        
        function val = get.scanState(obj)
            val = str2double(obj.query('SCNSTATE?'));
        end
        
        function obj=set.scanTime(obj, value)
            assert(isnumeric(value) && (value >= 0) && (value <= 1728000), ...
                'Oops! The scan time must be between 0 and 1728000 s (20 days)');
            obj.write('SCNSEC %E', value)
        end

        function val=get.scanTime(obj)
            val=str2double(obj.query('SCNSEC?'));
        end
        
        function obj=set.scanInterval(obj, value)
            assert(isnumeric(value) && (value >= .008) && (value <= 2700), ...
                'Oops! The scan interval must be between 8 ms and 2700 s');
            inverseMap = invertMap(obj.scanIntervalMap);
            mapKeys = keys(inverseMap);
            [~, index] = min(abs(value - cell2mat(mapKeys)));
            obj.write('SCNINRVL %d', inverseMap(mapKeys{index}));
        end
        
        function val=get.scanInterval(obj)
            mapVal=str2double(obj.query('SCNINRVL?'));
            val=obj.scanIntervalMap(mapVal);
        end
        
        function scanDC_set(obj)
            obj.write('SCNPAR REFDC')
        end
        
        function obj=set.scanDC_start(obj, value)
            assert(isnumeric(value) && (value >= -5) && (value <= 5), ...
                'Oops! The DC voltage must be between -5 V and 5 V');
            obj.write('SCNDC BEGIN, %E',value);
        end
               
        function val=get.scanDC_start(obj)
            val=str2double(obj.query('SCNDC? BEGIN'));
        end

        function obj=set.scanDC_end(obj, value)
            assert(isnumeric(value) && (value >= -5) && (value <= 5), ...
                'Oops! The DC voltage must be between -5 V and 5 V');
            obj.write('SCNDC END, %E',value);
        end

        function val=get.scanDC_end(obj)
            val=str2double(obj.query('SCNDC? END'));
        end
        
        function clrbuff(obj)
           obj.write('SDC'); 
        end
        
    end 
end