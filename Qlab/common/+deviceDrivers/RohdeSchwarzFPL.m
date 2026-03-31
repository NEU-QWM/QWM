classdef RohdeSchwarzFPL < handle
   properties
       center_frequency
       span
       resolution_bw
       video_bw
       sweep_mode
       video_averaging
       number_averages
       sweep_points
       socket
   end
   
   methods
       % Constructor
       function obj = RohdeSchwarzFPL()
       end
   
       function connect(obj, address)
           obj.socket = visa('ni', ['TCPIP::', address, '::INSTR']);
           fopen(obj.socket);
       end
       
       function disconnect(obj)
           fclose(obj.socket);
       end
       
       function delete(obj)
           delete(obj.socket)
       end
       
       function Write(obj, writeStr)
           fprintf(obj.socket, writeStr);
       end
       
       function val = Query(obj, queryStr)
           fprintf(obj.socket, queryStr);
           val = fscanf(obj.socket);
       end
       
       function sweep(obj)
           % Take a single sweep
           obj.Write(':INIT:CONT OFF');
           obj.Write(':INIT:IMM');
       end
       
       function reset(obj)
           % Reset instrument
           obj.Write('*RST;');
       end
       
       function val = peakAmplitude(obj)
           obj.Write(':CALC:MARK1:MAX');
           val = str2double(obj.Query(':CALC:MARK1:Y?'));
       end
       
       function val = peakFrequency(obj)
           obj.Write(':CALC:MARK1:MAX');
           val = str2double(obj.Query(':CALC:MARK1:X?'));
       end
       
       function [xdata, ydata] = downloadTrace(obj)
           obj.Write(':FORM:DATA REAL,32');
           obj.Write(':FORM:BORD SWAP');
           fprintf(obj.socket, 'TRAC:DATA? TRACE1');
           ydata = binblockread(obj.socket, 'float32');
           fread(obj.socket,1); % clear buffer
           
           center_freq = obj.center_frequency;
           curSpan = obj.span;
           xdata = linspace(center_freq - curSpan/2, center_freq + curSpan/2, length(ydata));
       end
       
       % instrument meta-setter
       function setAll(obj, settings)
           fields = fieldnames(settings);
           for j = 1:length(fields)
               name = fields{j};
               if ismember(name, methods(obj))
                   feval(['obj.' name], settings.(name));
               elseif ismember(name, properties(obj))
                   obj.(name) = settings.(name);
               end
           end
       end
       
       % property accessors
       
       function val = get.center_frequency(obj)
           val = str2double(obj.Query(':FREQ:CENT?'));
       end
       
       function val = get.span(obj)
           val = str2double(obj.Query(':FREQ:SPAN?'));
       end
       
       function val = get.resolution_bw(obj)
           val = str2double(obj.Query(':BAND:RES?'));
       end
       
       function val = get.video_bw(obj)
           val = str2double(obj.Query(':BAND:VID?'));
       end
       
       function val = get.sweep_mode(obj)
           val = obj.Query(':INIT:CONT?');
       end
       
       function val = get.video_averaging(obj)
           val = obj.Query(':AVER:STAT?');
       end
       
       function val = get.number_averages(obj)
           val = str2double(obj.Query(':AVER:COUN?'));
       end
       
       function val = get.sweep_points(obj)
           val = str2double(obj.Query(':SWE:POIN?'));
       end
       
       % property setters
       
       function set.center_frequency(obj, value)
           assert(isnumeric(value), 'Invalid input');
           obj.Write(sprintf(':FREQ:CENT %E', value));
       end
       
       function set.span(obj, value)
           assert(isnumeric(value), 'Invalid input');
           obj.Write(sprintf(':FREQ:SPAN %E', value));
       end
       
       function set.resolution_bw(obj, value)
           if strcmp(value, 'auto')
               obj.Write(':BAND:RES:AUTO ON');
           else
               assert(value > 1 && value < 10e6);
               obj.Write(sprintf(':BAND:RES %E', value));
           end
       end
       
       function set.video_bw(obj, value)
           if strcmp(value, 'auto')
               obj.Write(':BAND:VID:AUTO ON');
           else
               assert(value > 1 && value < 10e6);
               obj.Write(sprintf(':BAND:VID %E', value));
           end
       end
       
       function set.sweep_mode(obj, value)
           checkMapObj = containers.Map({'single','continuous','cont'},...
               {'OFF','ON','ON'});
           if ~checkMapObj.isKey(lower(value))
               error('Invalid input');
           end
           
           obj.Write(sprintf(':INIT:CONT %s', checkMapObj(lower(value))));
       end
       
       function set.video_averaging(obj, value)
           if value
               obj.Write(':AVER ON');
           else
               obj.Write(':AVER OFF');
           end
       end
       
       function set.number_averages(obj, value)
           assert(value > 1 && value < 65535, 'Invalid input');
           obj.Write(sprintf(':AVER:COUN %d', value));
       end
       
       function set.sweep_points(obj, value)
           assert(value > 101 && value < 100001, 'Invalid input');
           obj.Write(sprintf(':SWE:POIN %d', value));
       end
   end
end