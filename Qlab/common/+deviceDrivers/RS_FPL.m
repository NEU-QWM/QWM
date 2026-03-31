%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Rohde & Schwarz FPL Spectrum Analyzer (26.5 GHz)
% Created 2026 following AgilentN9020A driver syntax
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

classdef RS_FPL < deviceDrivers.lib.GPIBorEthernet

    % Device properties
    properties (Access = public)
        ByteOrder
        Identify
        OperationComplete
        SAFreqCenter
        SAFreqStart
        SAFreqStop
        SASpan
        SARBW
        SARBWAuto
        SAVBW
        SAVBWAuto
        SARefLevel
        SASweepPoints
        SASweepSingle
        SAMarkerXAxis
        SAMarkerYAxis
    end

    methods (Access = public)

        function res = QuerySCPI(obj, cmd)
            interface = get(obj, 'interface');
            res = query(interface, cmd);
        end

        function WriteSCPI(obj, cmd)
            interface = get(obj, 'interface');
            fprintf(interface, cmd);
        end

        function SAInitiate(obj)
            interface = get(obj,'interface');
            fprintf(interface, ':INIT:IMM');
        end

        function SYSPreset(obj)
            interface = get(obj,'interface');
            fprintf(interface, ':SYST:PRES');
        end

        function SAFreqRange(obj, range)
            interface = get(obj,'interface');
            fprintf(interface, [':FREQ:STAR ', num2str(range(1))]);
            fprintf(interface, [':FREQ:STOP ', num2str(range(2))]);
        end

        function SASetCenterFreq(obj, val)
            interface = get(obj,'interface');
            fprintf(interface, sprintf(':FREQ:CENT %d Hz', val));
        end

        function CF = SAGetCenterFreq(obj)
            interface = get(obj,'interface');
            CF = query(interface, ':FREQ:CENT?');
        end

        function SASetSpan(obj, val)
            interface = get(obj,'interface');
            fprintf(interface, sprintf(':FREQ:SPAN %d Hz', val));
        end

        function SPAN = SAGetSpan(obj)
            interface = get(obj,'interface');
            SPAN = query(interface, ':FREQ:SPAN?');
        end

        function SASetRBW(obj, val)
            interface = get(obj,'interface');
            fprintf(interface, sprintf(':BAND:RES %d Hz', val));
        end

        function RBW = SAGetRBW(obj)
            interface = get(obj,'interface');
            RBW = query(interface, ':BAND:RES?');
        end

        function SASetVBW(obj, val)
            interface = get(obj,'interface');
            fprintf(interface, sprintf(':BAND:VID %d Hz', val));
        end

        function VBW = SAGetVBW(obj)
            interface = get(obj,'interface');
            VBW = query(interface, ':BAND:VID?');
        end

        function SASetNoSweepPoints(obj, val)
            interface = get(obj,'interface');
            fprintf(interface, sprintf(':SWE:POIN %d', val));
        end

        function SP = SAGetNoSweepPoints(obj)
            interface = get(obj,'interface');
            SP = query(interface, ':SWE:POIN?');
        end

        function SASingleSweep(obj)
            interface = get(obj,'interface');
            fprintf(interface, ':INIT:CONT OFF');
            fprintf(interface, ':INIT:IMM;*WAI');
        end

        function SAContSweep(obj)
            interface = get(obj,'interface');
            fprintf(interface, ':INIT:CONT ON');
        end

        function SAMarkerPeak(obj)
            interface = get(obj,'interface');
            fprintf(interface, ':CALC:MARK1:MAX');
        end

        function freq = SAMarkerFreq(obj)
            interface = get(obj,'interface');
            freq = str2double(query(interface, ':CALC:MARK1:X?'));
        end

        function amp = SAMarkerAmp(obj)
            interface = get(obj,'interface');
            amp = str2double(query(interface, ':CALC:MARK1:Y?'));
        end

        function [freq, amp] = SAPeakAcqMax(obj)
            interface = get(obj,'interface');

            fprintf(interface, ':INIT:CONT OFF');
            fprintf(interface, ':INIT:IMM;*WAI');

            fprintf(interface, ':CALC:MARK1:MAX');
            freq = str2double(query(interface, ':CALC:MARK1:X?'));
            amp  = str2double(query(interface, ':CALC:MARK1:Y?'));

            fprintf(interface, ':INIT:CONT ON');
        end

        function [freq, amp] = SAGetTrace(obj)
            interface = get(obj,'interface');

            % Set binary format
            fprintf(interface, ':FORM:DATA REAL,32');
            fprintf(interface, ':FORM:BORD SWAP');

            % Trigger sweep
            fprintf(interface, ':INIT:IMM');
            opc = query(interface, '*OPC?');

            % Read trace
            fprintf(interface, ':TRAC:DATA? TRACE1');
            amp = binblockread(interface, 'float32');
            fread(interface,1);

            % Frequency axis
            SPAN = str2double(query(interface, ':FREQ:SPAN?'));
            CF   = str2double(query(interface, ':FREQ:CENT?'));
            SP   = str2double(query(interface, ':SWE:POIN?'));

            freq = linspace(CF - SPAN/2, CF + SPAN/2, SP);
        end

        function data = SATraceAcq(obj)
            interface = get(obj,'interface');

            fprintf(interface, ':FORM:DATA REAL,32');
            fprintf(interface, ':INIT:IMM');
            opc = query(interface, '*OPC?');

            fprintf(interface, ':TRAC:DATA? TRACE1');
            data = binblockread(interface, 'float32');
            fread(interface,1);
        end

    end

end