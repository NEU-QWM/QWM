classdef (Sealed) SG22000 < deviceDrivers.lib.uWSource
% DS Instruments SG22000PRO Signal Generator
% % % Author(s): Gun Suer
% Generated on: Thursday April 16 2026
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    properties (Access = public)
        output
        frequency   % Hz
        power       % dBm
        phase       % deg
        mod
        alc
        pulse
        pulseSource
    end

    properties (Access = private)
        interface
        connected = false;
    end

    % =========================================================
    % CONNECTION MANAGEMENT
    % =========================================================
    methods
        function connect(obj, ip)
            obj.interface = tcpclient(ip, 10001);
            obj.connected = true;
        end

        function disconnect(obj)
            % AUTHORITATIVE DISCONNECT
            % After this, NO COMMANDS ARE ALLOWED

            if ~isempty(obj.interface)
                try
                    clear obj.interface
                catch
                end
            end

            obj.interface = [];
            obj.connected = false;
        end

        function val = isConnected(obj)
            val = obj.connected && ~isempty(obj.interface);
        end
    end

    % =========================================================
    % HARD SAFETY LAYER (CORE PROTECTION)
    % =========================================================
    methods (Access = private)

        function assertConnected(obj)
            if isempty(obj.interface) || ~obj.connected
                error('SG22000 is disconnected. Call connect() first.');
            end
        end

        function write(obj, cmd)
            obj.assertConnected();
            writeline(obj.interface, cmd);
        end

        function val = query(obj, cmd)
            obj.assertConnected();
            writeline(obj.interface, cmd);
            pause(0.05);
            val = strtrim(readline(obj.interface));
        end

        function val = parseNum(~, str)
            if isempty(str)
                val = NaN;
                return;
            end

            tokens = regexp(str, '[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', 'match');

            if isempty(tokens)
                val = NaN;
            else
                val = str2double(tokens{1});
            end
        end
    end

    % =========================================================
    % FREQUENCY (Hz)
    % =========================================================
    methods
        function val = get.frequency(obj)
            raw = obj.query('FREQ:CW?');
            val = obj.parseNum(raw);
        end

        function obj = set.frequency(obj, value)
            obj.assertConnected();
            assert(isnumeric(value), 'Frequency must be in Hz');
            obj.write(sprintf('FREQ:CW %f', value));
        end
    end

    % =========================================================
    % POWER (dBm)
    % =========================================================
    methods
        function val = get.power(obj)
            raw = obj.query('POWER?');
            val = obj.parseNum(raw);
        end

        function obj = set.power(obj, value)
            obj.assertConnected();
            assert(isnumeric(value), 'Power must be numeric (dBm)');
            obj.write(sprintf('POWER %f', value));
        end
    end

    % =========================================================
    % OUTPUT CONTROL
    % =========================================================
    methods
        function val = get.output(obj)
            val = obj.query('OUTP:STAT?');
        end

        function obj = set.output(obj, value)
            obj.assertConnected();
            obj.write(sprintf('OUTP:STAT %s', obj.cast_bool(value)));
        end
    end

    % =========================================================
    % PHASE
    % =========================================================
    methods
        function val = get.phase(obj)
            raw = obj.query('PHASE?');
            val = obj.parseNum(raw);
        end

        function obj = set.phase(obj, value)
            obj.assertConnected();
            assert(isnumeric(value), 'Phase must be numeric (deg)');
            obj.write(sprintf('PHASE %f', value));
        end
    end

    % =========================================================
    % UNUSED FEATURES (SAFE PLACEHOLDERS)
    % =========================================================
    methods
        function val = get.mod(obj), val = []; end
        function val = get.alc(obj), val = []; end
        function val = get.pulse(obj), val = []; end
        function val = get.pulseSource(obj), val = []; end
    end

    % =========================================================
    % STATIC UTILITIES
    % =========================================================
    methods (Static)
        function out = cast_bool(in)
            if isnumeric(in)
                in = logical(in);
            end

            if islogical(in)
                if in
                    out = 'ON';
                else
                    out = 'OFF';
                end
                return
            end

            in = upper(string(in));

            if any(in == ["ON","1","TRUE"])
                out = 'ON';
            elseif any(in == ["OFF","0","FALSE"])
                out = 'OFF';
            else
                error('Invalid boolean input');
            end
        end
    end
end