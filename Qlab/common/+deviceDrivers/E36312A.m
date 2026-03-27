classdef E36312A < deviceDrivers.lib.GPIBorEthernet
    % E36312A Driver for Keysight Triple Output Power Supply
    %
    % Author: Adapted for MATLAB deviceDrivers style
    %
    properties
        Voltage       % Set/get voltage of selected channel (V)
        Current       % Set/get current of selected channel (A)
        VoltageLimit  % Voltage compliance/protection
        CurrentLimit  % Current compliance/protection
        output        % Output state (0=off, 1=on)
        channel       % Selected channel (1,2,3)
        mode          % Mode: 'voltage' or 'current'
    end
    
    properties (Access = private)
        visaObj
        timeout = 5000; % ms
    end
    
    methods
        %% Constructor
        function obj = E36312A(resourceString)
            obj.visaObj = visadev(resourceString);
            obj.visaObj.Timeout = obj.timeout;

            idn = obj.query('*IDN?');
            fprintf('Connected to: %s\n', idn);
        end
        
        %% ========================
        %% Low-level helpers
        %% ========================
        function write(obj, cmd)
            writeline(obj.visaObj, cmd);
        end

        function out = read(obj)
            out = readline(obj.visaObj);
        end

        function out = query(obj, cmd)
            obj.write(cmd);
            out = obj.read();
        end
        
        %% ========================
        %% Channel control
        %% ========================
        function selectChannel(obj, ch)
            assert(ismember(ch,1:3),'Channel must be 1,2, or 3');
            obj.channel = ch;
            obj.write(sprintf('INST:NSEL %d', ch));
        end
        
        %% ========================
        %% Voltage / Current getters
        %% ========================
        function val = get.Voltage(obj)
            obj.selectChannel(obj.channel);
            val = str2double(obj.query('MEAS:VOLT?'));
        end
        
        function val = get.Current(obj)
            obj.selectChannel(obj.channel);
            val = str2double(obj.query('MEAS:CURR?'));
        end
        
        function val = get.output(obj)
            obj.selectChannel(obj.channel);
            val = str2double(obj.query('OUTP?'));
        end
        
        %% ========================
        %% Voltage / Current setters
        %% ========================
        function obj = set.Voltage(obj, val)
            obj.selectChannel(obj.channel);
            obj.write(sprintf('VOLT %.6f', val));
        end
        
        function obj = set.Current(obj, val)
            obj.selectChannel(obj.channel);
            obj.write(sprintf('CURR %.6f', val));
        end
        
        function obj = set.VoltageLimit(obj, val)
            obj.selectChannel(obj.channel);
            obj.write(sprintf('VOLT:PROT %.6f', val));
        end
        
        function obj = set.CurrentLimit(obj, val)
            obj.selectChannel(obj.channel);
            obj.write(sprintf('CURR:PROT %.6f', val));
        end
        
        function obj = set.output(obj, val)
            obj.selectChannel(obj.channel);
            if isnumeric(val) || islogical(val)
                val = num2str(val);
            end
            assert(ismember(val,{'0','1','ON','OFF'}),'Invalid output value');
            obj.write(sprintf('OUTP %s', val));
        end
        
        %% ========================
        %% Mode control
        %% ========================
        function VoltageMode(obj)
            obj.selectChannel(obj.channel);
            obj.mode = 'voltage';
            obj.write('SOUR:FUNC VOLT');
        end
        
        function CurrentMode(obj)
            obj.selectChannel(obj.channel);
            obj.mode = 'current';
            obj.write('SOUR:FUNC CURR');
        end
        
        %% ========================
        %% Voltage ramp / safe sweep
        %% ========================
        function rampVoltage(obj, target_V, step_V, pause_s)
            obj.selectChannel(obj.channel);
            current_V = obj.Voltage;
            
            if target_V > current_V
                sweep = current_V:step_V:target_V;
            else
                sweep = current_V:-step_V:target_V;
            end
            
            for v = sweep
                obj.Voltage = v;
                pause(pause_s);
            end
            
            obj.Voltage = target_V;
        end
        
        %% ========================
        %% Output control helpers
        %% ========================
        function outputOn(obj)
            obj.output = 1;
        end
        
        function outputOff(obj)
            obj.output = 0;
        end
        
        function allOff(obj)
            for ch = 1:3
                obj.selectChannel(ch);
                obj.outputOff();
            end
        end
        
        %% ========================
        %% Safe channel setup
        %% ========================
        function setChannel(obj, ch, voltage_V, current_A)
            obj.selectChannel(ch);
            obj.Current = current_A;   % limit first
            obj.Voltage = voltage_V;
            obj.outputOn();
        end
        
        %% ========================
        %% Reset / cleanup
        %% ========================
        function reset(obj)
            obj.write('*RST');
            obj.write('*CLS');
        end
        
        function delete(obj)
            try
                clear obj.visaObj
            catch
            end
        end
    end
end