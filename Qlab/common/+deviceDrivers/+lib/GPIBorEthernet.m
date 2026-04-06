classdef GPIBorEthernet < hgsetget
    
    properties (Access = protected)
        interface
        buffer_size = 1048576;   % 1 MB buffer
        DEFAULT_PORT = 5025;     % TCP/IP port
        timeout = 360;            % default timeout in seconds (adjust as needed)
    end
    
    properties (SetAccess=private)
        identity    % standard *IDN? response
        isConnected
    end

    methods
        function delete(obj)
            if obj.isConnected
                obj.disconnect();
            end
        end
        
        function connect(obj, address)
            % determine whether to use GPIB or TCPIP by the form of the address
            if ~obj.isConnected
                ip_re = '\d+\.\d+\.\d+\.\d+';
                gpib_re = '^\d+$';

                if ischar(address) && ~isempty(regexp(address, ip_re, 'once'))
                    % Create a TCPIP object
                    obj.interface = tcpip(address, obj.DEFAULT_PORT);
                elseif ischar(address) && ~isempty(regexp(address, gpib_re, 'once'))
                    % create a GPIB object
                    obj.interface = gpib('ni', 0, str2double(address));
                elseif isnumeric(address)
                    obj.interface = gpib('ni', 0, address);
                else
                    % Probably a hostname
                    obj.interface = tcpip(address, obj.DEFAULT_PORT);
                end

                obj.interface.InputBufferSize = obj.buffer_size;
                obj.interface.OutputBufferSize = obj.buffer_size;
                obj.interface.Timeout = obj.timeout;  % <-- Set the timeout here
                fopen(obj.interface);
            end
        end
        
        function disconnect(obj)
            if ~isempty(obj.interface)
                flushoutput(obj.interface);
                flushinput(obj.interface);
                fclose(obj.interface);
                delete(obj.interface);
                obj.interface = [];
            end
        end
        
        function val = get.isConnected(obj)
            val = ~isempty(obj.interface) && strcmp(obj.interface.Status, 'open');
        end
        
        function write(obj, varargin)
            fprintf(obj.interface, sprintf(varargin{:}));
        end
        
        function val = query(obj, string)
            val = strtrim(query(obj.interface, string));
        end
        
        function val = read(obj)
            val = fgetl(obj.interface);
        end
        
        %typically available SCPI commands
        function val = get.identity(obj)
            val = obj.query('*IDN?');
        end
        
        function reset(obj)
            obj.write('*RST');
        end
        
        % binary read/write functions
        function binblockwrite(obj, varargin)
            binblockwrite(obj.interface, varargin{:});
        end
        
        function val = binblockread(obj, varargin)
            val = binblockread(obj.interface, varargin{:});
        end
    end
end