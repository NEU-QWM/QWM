classdef RS_ZNB3020 < deviceDrivers.lib.GPIBorEthernet
%RS_ZNB3020 Driver for Rohde & Schwarz ZNB3020 VNA
%
% Author(s): adapted from AgilentE8363C
%

    properties (Access = public)
        sweep_data;
        marker1_state;      % Values: ['off', 'on']
        marker1_x;          % Values: numeric
        marker1_y;
        marker2_state;      % Values: ['off', 'on']
        marker2_x;          % Values: numeric
        marker2_y;
        measurements;
        select_measurement; % Values: string
        trace_source;       % Values: string
        output;             % Values: ['off', 'on']
        average_counts;     % Values: numeric
        averaging;          % Values: ['off', 'on']
        sweep_center;       % Values: numeric
        sweep_span;         % Values: numeric
        sweep_mode;         % Values: ['continuous', 'groups', 'hold', 'single']
        sweep_points;       % Values: numeric
        power;              % Values: numeric
        averaging_complete;
        averaging_completed;
        nerr;
        err;
        trigger_source;     % Values: ['external', 'immediate', 'manual']
        frequency;          % Frequency, for use in CW mode
        visa_timeout = 120; % Increased timeout for low bw measurement
    end

    methods (Access = public)
        function obj = RS_ZNB3020()
            % Constructor
        end

        %% Instrument-specific methods
        function clear(obj)
            obj.write('*CLS');
        end

        function wait(obj)
            obj.write('*WAI');
        end

        function abort(obj)
            obj.write(':ABORt');
        end

        function [frequencies, s21] = getTrace(obj)
            % Get trace data
            measurement = obj.measurements;
            commaPos = strfind(measurement, ',');
            obj.select_measurement = measurement(2:commaPos(1)-1);
            obj.write('INIT1:IMM');
            obj.write('*WAI');
            s21 = obj.sweep_data;
            center_freq = obj.sweep_center;
            span = obj.sweep_span;
            frequencies = linspace(center_freq - span/2, center_freq + span/2, length(s21));
        end

        function reaverage(obj)
            obj.abort();
            obj.average_clear();
            obj.wait();
            obj.block_for_averaging();
        end

        function marker1_search(obj, value)
            gpib_string = 'CALC1:MARK1:FUNC:EXEC';
            checkMapObj = containers.Map(...
                {'compression','lpeak','ltarget','maximum','minimum','npeak','rpeak','rtarget','target'},...
                {'COMP','LPE','LTAR','MAX','MIN','NPE','RPE','RTAR','TAR'});
            if ~checkMapObj.isKey(value)
                error('Invalid input');
            end
            obj.write([gpib_string ' ' checkMapObj(value)]);
        end

        function markers_off(obj)
            obj.write('CALC1:MARK:AOFF');
        end

        function define_measurement(obj, valuea, valueb)
            gpib_string = ['CALC1:PAR:DEF ''' valuea ''',' valueb];
            obj.write(gpib_string);
        end

        function delete_all_measurements(obj)
            obj.write('CALC1:PAR:DEL:ALL');
        end

        function delete_measurement(obj, value)
            gpib_string = ['CALC1:PAR:DEL ''' value ''''];
            obj.write(gpib_string);
        end

        function send_trigger(obj)
            obj.write('INIT1:IMM');
        end

        function average_clear(obj)
            obj.write('SENS1:AVER:CLE');
        end

        function block_for_averaging(obj)
            obj.write('INIT1:IMM');
            obj.write('*WAI');
        end

        function CWMode(obj)
            obj.write('*RST');
            obj.write('SENS1:SWE:TYPE CW');
        end
    end

    methods % Instrument parameter accessors
        %% Getters
        function val = get.sweep_data(obj)
            textdata = obj.query('CALC1:DATA? SDATA');
            data = str2num(textdata); %#ok<ST2NM>
            val = data(1:2:end) + 1i*data(2:2:end);
        end

        function val = get.marker1_state(obj)
            val = obj.query('CALC1:MARK1:STAT?');
        end

        function val = get.marker1_x(obj)
            val = str2double(obj.query('CALC1:MARK1:X?'));
        end

        function val = get.marker1_y(obj)
            val = str2double(obj.query('CALC1:MARK1:Y?'));
        end

        function val = get.marker2_state(obj)
            val = obj.query('CALC1:MARK2:STAT?');
        end

        function val = get.marker2_x(obj)
            val = str2double(obj.query('CALC1:MARK2:X?'));
        end

        function val = get.marker2_y(obj)
            val = str2double(obj.query('CALC1:MARK2:Y?'));
        end

        function val = get.measurements(obj)
            val = obj.query('CALC1:PAR:CAT?');
        end

        function val = get.select_measurement(obj)
            val = obj.query('CALC1:PAR:SEL?');
        end

        function val = get.output(obj)
            val = obj.query('OUTP?');
        end

        function val = get.average_counts(obj)
            val = str2double(obj.query('SENS1:AVER:COUN?'));
        end

        function val = get.averaging(obj)
            val = obj.query('SENS1:AVER:STAT?');
        end

        function val = get.sweep_center(obj)
            val = str2double(obj.query('SENS1:FREQ:CENT?'));
        end

        function val = get.sweep_span(obj)
            val = str2double(obj.query('SENS1:FREQ:SPAN?'));
        end

        function val = get.sweep_mode(obj)
            val = obj.query('SENS1:SWE:MODE?');
        end

        function val = get.sweep_points(obj)
            val = str2double(obj.query('SENS1:SWE:POIN?'));
        end

        function val = get.power(obj)
            val = str2double(obj.query('SOUR1:POW?'));
        end

        function val = get.averaging_complete(obj)
            val = obj.query('*OPC?');
        end

        function val = get.averaging_completed(obj)
            val = obj.query('*OPC?');
        end

        function val = get.nerr(obj)
            val = obj.query('SYST:ERR:COUN?');
        end

        function val = get.err(obj)
            val = obj.query('SYST:ERR?');
        end

        function val = get.trigger_source(obj)
            val = obj.query('TRIG:SOUR?');
        end

        function val = get.frequency(obj)
            val = str2double(obj.query('SENS1:FREQ?'));
        end

        %% Setters
        function obj = set.select_measurement(obj, value)
            obj.write(['CALC1:PAR:SEL ' value]);
        end

        function obj = set.marker1_state(obj, value)
            checkMapObj = containers.Map({'off','on'},{'OFF','ON'});
            if ~checkMapObj.isKey(value), error('Invalid input'); end
            obj.write(['CALC1:MARK1:STAT ' checkMapObj(value)]);
            obj.marker1_state = value;
        end

        function obj = set.marker1_x(obj, value)
            obj.write(['CALC1:MARK1:X ' num2str(value)]);
            obj.marker1_x = value;
        end

        function obj = set.marker2_state(obj, value)
            checkMapObj = containers.Map({'off','on'},{'OFF','ON'});
            if ~checkMapObj.isKey(value), error('Invalid input'); end
            obj.write(['CALC1:MARK2:STAT ' checkMapObj(value)]);
            obj.marker2_state = value;
        end

        function obj = set.marker2_x(obj, value)
            obj.write(['CALC1:MARK2:X ' num2str(value)]);
            obj.marker2_x = value;
        end

        function obj = set.trace_source(obj, value)
            obj.write(['DISP:WIND1:TRAC1:FEED ' value]);
            obj.trace_source = value;
        end

        function obj = set.output(obj, value)
            checkMapObj = containers.Map({'off','on'},{'OFF','ON'});
            if ~checkMapObj.isKey(value), error('Invalid input'); end
            obj.write(['OUTP ' checkMapObj(value)]);
            obj.output = value;
        end

        function obj = set.average_counts(obj, value)
            obj.write(['SENS1:AVER:COUN ' num2str(value)]);
            obj.average_counts = value;
        end

        function obj = set.averaging(obj, value)
            checkMapObj = containers.Map({'off','on'},{'OFF','ON'});
            if ~checkMapObj.isKey(value), error('Invalid input'); end
            obj.write(['SENS1:AVER:STAT ' checkMapObj(value)]);
            obj.averaging = value;
        end

        function obj = set.sweep_center(obj, value)
            obj.write(['SENS1:FREQ:CENT ' num2str(value)]);
            obj.sweep_center = value;
        end

        function obj = set.sweep_span(obj, value)
            obj.write(['SENS1:FREQ:SPAN ' num2str(value)]);
            obj.sweep_span = value;
        end

        function obj = set.sweep_mode(obj, value)
            checkMapObj = containers.Map({'continuous','groups','hold','single'},{'CONT','GRO','HOLD','SING'});
            if ~checkMapObj.isKey(value), error('Invalid input'); end
            obj.write(['SENS1:SWE:MODE ' checkMapObj(value)]);
            obj.sweep_mode = value;
        end

        function obj = set.sweep_points(obj, value)
            obj.write(['SENS1:SWE:POIN ' num2str(value)]);
            obj.sweep_points = value;
        end

        function obj = set.power(obj, value)
            obj.write(['SOUR1:POW ' num2str(value)]);
            obj.power = value;
        end

        function obj = set.trigger_source(obj, value)
            checkMapObj = containers.Map({'external','immediate','manual'},{'EXT','IMM','MAN'});
            if ~checkMapObj.isKey(value), error('Invalid input'); end
            obj.write(['TRIG:SOUR ' checkMapObj(value)]);
            obj.trigger_source = value;
        end

        function obj = set.frequency(obj, value)
            obj.write(['SENS1:FREQ ' num2str(value)]);
            obj.frequency = value;
        end

    end

end