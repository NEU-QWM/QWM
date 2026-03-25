classdef E36312A < handle
    % Copyright 2026 Northeastern University
    %
    % Instrument driver for the Keysight E36312A Triple Output Power Supply

    properties
        visaObj
        timeout = 5000;   % ms
    end

    methods
        %% Constructor
        function obj = E36312A(resourceString)
            obj.visaObj = visadev(resourceString);
            obj.visaObj.Timeout = obj.timeout;

            obj.write("*IDN?");
            idn = obj.read();
            fprintf("Connected to: %s\n", idn);
        end

        %% Low-level VISA helpers
        function write(obj, cmd)
            writeline(obj.visaObj, cmd);
        end

        function out = read(obj)
            out = readline(obj.visaObj);
        end

        %% Reset
        function reset(obj)
            obj.write("*RST");
            obj.write("*CLS");
        end

        %% Select channel (1, 2, or 3)
        function selectChannel(obj, ch)
            validateattributes(ch, {'numeric'}, {'scalar','>=',1,'<=',3});
            obj.write(sprintf("INST:NSEL %d", ch));
        end

        %% ========================
        %% CURRENT CONTROL
        %% ========================

        function setCurrent(obj, ch, current_A)
            obj.selectChannel(ch);
            obj.write(sprintf("CURR %.6f", current_A));
        end

        function setCurrent_mA(obj, ch, current_mA)
            obj.setCurrent(ch, current_mA / 1000);
        end

        function i = measureCurrent(obj, ch)
            obj.selectChannel(ch);
            obj.write("MEAS:CURR?");
            i = str2double(obj.read());
        end

        function i_mA = measureCurrent_mA(obj, ch)
            i_mA = obj.measureCurrent(ch) * 1000;
        end

        %% ========================
        %% VOLTAGE CONTROL
        %% ========================

        function setVoltage(obj, ch, voltage_V)
            obj.selectChannel(ch);
            obj.write(sprintf("VOLT %.6f", voltage_V));
        end

        function setVoltage_mV(obj, ch, voltage_mV)
            obj.setVoltage(ch, voltage_mV / 1000);
        end

        function v = measureVoltage(obj, ch)
            obj.selectChannel(ch);
            obj.write("MEAS:VOLT?");
            v = str2double(obj.read());
        end

        function v_mV = measureVoltage_mV(obj, ch)
            v_mV = obj.measureVoltage(ch) * 1000;
        end

        %% Voltage ramp (safe sweeping)
        function rampVoltage(obj, ch, target_V, step_V, pause_s)
            obj.selectChannel(ch);

            current_V = obj.measureVoltage(ch);

            if target_V > current_V
                sweep = current_V:step_V:target_V;
            else
                sweep = current_V:-step_V:target_V;
            end

            for v = sweep
                obj.write(sprintf("VOLT %.6f", v));
                pause(pause_s);
            end

            % Ensure exact final value
            obj.write(sprintf("VOLT %.6f", target_V));
        end

        %% ========================
        %% OUTPUT CONTROL
        %% ========================

        function outputOn(obj, ch)
            obj.selectChannel(ch);
            obj.write("OUTP ON");
        end

        function outputOff(obj, ch)
            obj.selectChannel(ch);
            obj.write("OUTP OFF");
        end

        function allOff(obj)
            for ch = 1:3
                obj.selectChannel(ch);
                obj.write("OUTP OFF");
            end
        end

        %% ========================
        %% SAFE CHANNEL SETUP
        %% ========================

        function setChannel(obj, ch, voltage_V, current_A)
            obj.setCurrent(ch, current_A);   % limit first
            obj.setVoltage(ch, voltage_V);
            obj.outputOn(ch);
        end

        %% ========================
        %% Destructor
        %% ========================

        function delete(obj)
            try
                clear obj.visaObj
            catch
            end
        end
    end
end