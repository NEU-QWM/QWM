classdef RS_ZNB3020 < deviceDrivers.lib.GPIBorEthernet
%RS_ZNB3020
%
%
% Author(s): adapted from AgilentE8363C
%

    % Device properties correspond to instrument parameters
    properties (Access = public)
        sweep_data;
        marker1_state;		% Values: ['off', 'on']
        marker1_x;		% Values: (numeric)
        marker1_y;
        marker2_state;		% Values: ['off', 'on']
        marker2_x;		% Values: (numeric)
        marker2_y;
        measurements;
        select_measurement;		% Values: (string)
        trace_source;		% Values: (string)
        output;		% Values: ['off', 'on']
        average_counts;		% Values: (numeric)
        averaging;		% Values: ['off', 'on']
        sweep_center;		% Values: (numeric)
        sweep_span;		% Values: (numeric)
        sweep_mode;		% Values: ['continuous', 'groups', 'hold', 'single']
        sweep_points;		% Values: (numeric)
        power;		% Values: (numeric)
        averaging_complete;
        averaging_completed;
        nerr;
        err;
        trigger_source;		% Values: ['external', 'immediate', 'manual']
        frequency;          % frequency, for use in CW mode
    end % end device properties


    methods (Access = public)
        function obj = RS_ZNB3020()
            %RS_ZNB3020 constructor
        end

        % Instrument-specific methods
        function clear(obj)
        %CLEAR
            gpib_string = '*CLS';
            obj.write(gpib_string);
        end

        function wait(obj)
        %WAIT
            gpib_string = '*WAI';
            obj.write(gpib_string);
        end

        function abort(obj)
        %ABORT
            gpib_string = ':ABORt';
            obj.write(gpib_string);
        end
        
        function [frequencies, s21] = getTrace(obj)
            % select measurement
            % get measurement name
            measurement = obj.measurements;
            % take the part before the comma
            commaPos = strfind(measurement, ',');
            obj.select_measurement = measurement(2:commaPos(1)-1);

            % trigger sweep
            obj.write('INIT1:IMM');
            obj.write('*WAI');

            s21 = obj.sweep_data;
            
            center_freq = obj.sweep_center;
            span = obj.sweep_span;
            frequencies = linspace(center_freq - span/2, center_freq + span/2, length(s21));
        end
        
        function reaverage(obj)
            % reaverage
            obj.abort();
            obj.average_clear();
            
            obj.wait();
            obj.block_for_averaging();
        end

        function marker1_search(obj, value)
        %MARKER1_SEARCH
            gpib_string = 'CALC1:MARK1:FUNC:EXEC';
            checkMapObj = containers.Map(...
                {'compression','lpeak','ltarget','maximum','minimum','npeak','rpeak','rtarget','target'},...
                {'COMP','LPE','LTAR','MAX','MIN','NPE','RPE','RTAR','TAR'});
            if not (checkMapObj.isKey(value))
                error('Invalid input');
            end

            gpib_string = [gpib_string ' ' checkMapObj(value)];
            obj.write(gpib_string);
        end

        function markers_off(obj)
        %MARKERS_OFF
            gpib_string = 'CALC1:MARK:AOFF';
            obj.write(gpib_string);
        end

        function define_measurement(obj, valuea, valueb)
        %DEFINE_MEASUREMENT
            gpib_string = 'CALC1:PAR:DEF';
            gpib_string = [gpib_string ' ''' valuea ''',' valueb];
            obj.write(gpib_string);
        end

        function delete_all_measurements(obj)
        %DELETE_ALL_MEASUREMENTS
            gpib_string = 'CALC1:PAR:DEL:ALL';
            obj.write(gpib_string);
        end

        function delete_measurement(obj, value)
        %DELETE_MEASUREMENT
            gpib_string = 'CALC1:PAR:DEL';
            gpib_string = [gpib_string ' ''' value ''''];
            obj.write(gpib_string);
        end

        function send_trigger(obj)
        %SEND_TRIGGER
            gpib_string = 'INIT1:IMM';
            obj.write(gpib_string);
        end

        function average_clear(obj)
        %AVERAGE_CLEAR
            gpib_string = 'SENS1:AVER:CLE';
            obj.write(gpib_string);
        end
        
        function block_for_averaging(obj)
        %BLOCK_FOR_AVERAGING
            obj.write('INIT1:IMM');
            obj.write('*WAI');
        end
        
        function CWMode(obj)
            % reset the device
            obj.write('*RST');
            % put the analyzer in CW mode
            obj.write('SENS1:SWE:TYPE CW');
        end
        
    end % end methods

    methods % Instrument parameter accessors

        function val = get.sweep_data(obj)
            gpib_string = 'CALC1:DATA';
            textdata = obj.query([gpib_string '? SDATA']);
            data = str2num(textdata);
            val = data(1:2:end) + 1i*data(2:2:end);
        end

        function val = get.marker1_state(obj)
            gpib_string = 'CALC1:MARK1:STAT';
            val = obj.query([gpib_string '?']);
        end

        function val = get.marker1_x(obj)
            gpib_string = 'CALC1:MARK1:X';
            val = obj.query([gpib_string '?']);
        end

        function val = get.marker1_y(obj)
            gpib_string = 'CALC1:MARK1:Y';
            val = obj.query([gpib_string '?']);
        end

        function val = get.marker2_state(obj)
            gpib_string = 'CALC1:MARK2:STAT';
            val = obj.query([gpib_string '?']);
        end

        function val = get.marker2_x(obj)
            gpib_string = 'CALC1:MARK2:X';
            val = obj.query([gpib_string '?']);
        end

        function val = get.marker2_y(obj)
            gpib_string = 'CALC1:MARK2:Y';
            val = obj.query([gpib_string '?']);
        end

        function val = get.measurements(obj)
            gpib_string = 'CALC1:PAR:CAT';
            val = obj.query([gpib_string '?']);
        end

        function val = get.select_measurement(obj)
            gpib_string = 'CALC1:PAR:SEL';
            val = obj.query([gpib_string '?']);
        end

        function val = get.output(obj)
            gpib_string = 'OUTP';
            val = obj.query([gpib_string '?']);
        end

        function val = get.average_counts(obj)
            gpib_string = 'SENS1:AVER:COUN';
            val = str2double(obj.query([gpib_string '?']));
        end

        function val = get.averaging(obj)
            gpib_string = 'SENS1:AVER:STAT';
            val = obj.query([gpib_string '?']);
        end

        function val = get.sweep_center(obj)
            gpib_string = 'SENS1:FREQ:CENT';
            val = str2double(obj.query([gpib_string '?']));
        end

        function val = get.sweep_span(obj)
            gpib_string = 'SENS1:FREQ:SPAN';
            val = str2double(obj.query([gpib_string '?']));
        end

        function val = get.sweep_mode(obj)
            gpib_string = 'SENS1:SWE:MODE';
            val = obj.query([gpib_string '?']);
        end

        function val = get.sweep_points(obj)
            gpib_string = 'SENS1:SWE:POIN';
            val = str2double(obj.query([gpib_string '?']));
        end

        function val = get.power(obj)
            gpib_string = 'SOUR1:POW';
            val = obj.query([gpib_string '?']);
        end

        function val = get.averaging_complete(obj)
            gpib_string = '*OPC';
            val = obj.query([gpib_string '?']);
        end

        function val = get.averaging_completed(obj)
            gpib_string = '*OPC';
            val = obj.query([gpib_string '?']);
        end

        function val = get.nerr(obj)
            gpib_string = 'SYST:ERR:COUN';
            val = obj.query([gpib_string '?']);
        end

        function val = get.err(obj)
            gpib_string = 'SYST:ERR';
            val = obj.query([gpib_string '?']);
        end

        function val = get.trigger_source(obj)
            gpib_string = 'TRIG:SOUR';
            val = obj.query([gpib_string '?']);
        end

        function val = get.frequency(obj)
            gpib_string = 'SENS1:FREQ';
            val = obj.query([gpib_string '?']);
        end

        function obj = set.select_measurement(obj, value)
            gpib_string = 'CALC1:PAR:SEL';
            gpib_string = [gpib_string ' ' value];
            obj.write(gpib_string);
        end

    end % end instrument parameter accessors

end % end classdef