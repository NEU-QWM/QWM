from core.sentinel.graph import DeviceGraph, GraphNode, ValveNode


class Valve(ValveNode):
    V001 = "V001"
    V003 = "V003"
    V004 = "V004"
    V005 = "V005"
    V101 = "V101"
    V102 = "V102"
    V104 = "V104"
    V105 = "V105"
    V106 = "V106"
    V107 = "V107"
    V108 = "V108"
    V109 = "V109"
    V110 = "V110"
    V111 = "V111"
    V112 = "V112"
    V113 = "V113"
    V114 = "V114"
    V201G = "V201G"
    V202 = "V202"
    V203 = "V203"
    V204 = "V204"
    V205 = "V205"
    V206 = "V206"
    V301 = "V301"
    V302 = "V302"
    V303 = "V303"
    V304 = "V304"
    V305 = "V305"
    V306 = "V306"
    V401 = "V401"
    V402 = "V402"
    V403 = "V403"
    V404 = "V404"
    V405 = "V405"
    V406 = "V406"
    V407 = "V407"
    V501H = "V501H"
    V502H = "V502H"
    V503H = "V503H"
    V504H = "V504H"
    V505H = "V505H"
    V601G = "V601G"
    V602 = "V602"
    VCOM = "VCOM"


class Other(GraphNode):
    AIR = "AIR"
    AUX = "AUX"
    B1a = "B1a"
    B1b = "B1b"
    B1c = "B1c"
    B2 = "B2"
    N2VENT = "N2VENT"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"
    P6 = "P6"
    P7 = "P7"
    P8 = "P8"
    R1a = "R1a"
    R1b = "R1b"
    R2 = "R2"
    TEST = "TEST"
    TRAP1 = "TRAP1"
    TRAP2 = "TRAP2"
    Tank = "Tank"
    VENT = "VENT"
    VacuumCan = "VacuumCan"


graph = DeviceGraph.create(
    node_classes=[Valve, Other],
    pairwise_graph=(
        # V001
        (Valve.V001, Valve.V003),
        (Valve.V001, Valve.V004),
        (Valve.V001, Valve.V114),
        (Valve.V001, Valve.V204),
        (Valve.V001, Valve.V205),
        (Valve.V001, Valve.V206),
        (Valve.V001, Valve.V301),
        (Valve.V001, Valve.V302),
        # V003
        (Valve.V003, Valve.V001),
        (Valve.V003, Valve.V004),
        (Valve.V003, Valve.V005),
        (Valve.V003, Valve.V301),
        (Valve.V003, Valve.V302),
        (Valve.V003, Other.Tank),
        # V004
        (Valve.V004, Valve.V001),
        (Valve.V004, Valve.V003),
        (Valve.V004, Valve.V005),
        (Valve.V004, Valve.V301),
        (Valve.V004, Valve.V302),
        (Valve.V004, Other.Tank),
        # V005
        (Valve.V005, Valve.V001),
        (Valve.V005, Valve.V003),
        (Valve.V005, Valve.V004),
        (Valve.V005, Valve.V304),
        (Valve.V005, Valve.V305),
        (Valve.V005, Valve.V403),
        (Valve.V005, Valve.V402),
        (Valve.V005, Valve.V407),
        (Valve.V005, Other.Tank),
        # V101
        (Valve.V101, Other.VacuumCan),
        (Valve.V101, Valve.V102),
        (Valve.V101, Valve.V104),
        (Valve.V101, Valve.V112),
        # V102
        (Valve.V102, Valve.V101),
        (Valve.V102, Valve.V104),
        (Valve.V102, Valve.V112),
        (Valve.V102, Other.TEST),
        # V104
        (Valve.V104, Valve.V101),
        (Valve.V104, Valve.V102),
        (Valve.V104, Valve.V112),
        (Valve.V104, Valve.V105),
        (Valve.V104, Valve.V107),
        (Valve.V104, Valve.V108),
        (Valve.V104, Valve.V109),
        (Valve.V104, Valve.V110),
        (Valve.V104, Valve.V111),
        (Valve.V104, Valve.V113),
        (Valve.V104, Valve.V114),
        (Valve.V104, Valve.V303),
        (Valve.V104, Valve.V306),
        (Valve.V104, Valve.V404),
        (Valve.V104, Valve.V406),
        # V105
        (Valve.V105, Valve.V104),
        (Valve.V105, Other.R2),
        (Valve.V105, Valve.V106),
        (Valve.V105, Valve.V107),
        (Valve.V105, Valve.V108),
        (Valve.V105, Valve.V109),
        (Valve.V105, Valve.V110),
        (Valve.V105, Valve.V111),
        (Valve.V105, Valve.V113),
        (Valve.V105, Valve.V114),
        (Valve.V105, Valve.V303),
        (Valve.V105, Valve.V306),
        (Valve.V105, Valve.V404),
        (Valve.V105, Valve.V406),
        # V106
        (Valve.V106, Valve.V105),
        (Valve.V106, Other.B2),
        (Valve.V106, Other.R2),
        # V107
        (Valve.V107, Valve.V104),
        (Valve.V107, Valve.V105),
        (Valve.V107, Valve.V108),
        (Valve.V107, Valve.V109),
        (Valve.V107, Valve.V110),
        (Valve.V107, Valve.V111),
        (Valve.V107, Valve.V113),
        (Valve.V107, Valve.V114),
        (Valve.V107, Valve.V303),
        (Valve.V107, Valve.V306),
        (Valve.V107, Valve.V404),
        (Valve.V107, Valve.V406),
        # V108
        (Valve.V108, Valve.V104),
        (Valve.V108, Valve.V105),
        (Valve.V108, Valve.V107),
        (Valve.V108, Valve.V109),
        (Valve.V108, Valve.V110),
        (Valve.V108, Valve.V111),
        (Valve.V108, Valve.V113),
        (Valve.V108, Valve.V114),
        (Valve.V108, Valve.V303),
        (Valve.V108, Valve.V306),
        (Valve.V108, Valve.V404),
        (Valve.V108, Valve.V406),
        (Valve.V108, Other.AUX),
        # V109
        (Valve.V109, Valve.V104),
        (Valve.V109, Valve.V105),
        (Valve.V109, Valve.V107),
        (Valve.V109, Valve.V108),
        (Valve.V109, Valve.V110),
        (Valve.V109, Valve.V111),
        (Valve.V109, Valve.V113),
        (Valve.V109, Valve.V114),
        (Valve.V109, Valve.V303),
        (Valve.V109, Valve.V306),
        (Valve.V109, Valve.V404),
        (Valve.V109, Valve.V406),
        (Valve.V109, Valve.V602),
        # V110
        (Valve.V110, Valve.V104),
        (Valve.V110, Valve.V105),
        (Valve.V110, Valve.V107),
        (Valve.V110, Valve.V108),
        (Valve.V110, Valve.V109),
        (Valve.V110, Valve.V111),
        (Valve.V110, Valve.V113),
        (Valve.V110, Valve.V114),
        (Valve.V110, Valve.V303),
        (Valve.V110, Valve.V306),
        (Valve.V110, Valve.V404),
        (Valve.V110, Valve.V406),
        (Valve.V110, Other.VENT),
        # V111
        (Valve.V111, Valve.V104),
        (Valve.V111, Valve.V105),
        (Valve.V111, Valve.V107),
        (Valve.V111, Valve.V108),
        (Valve.V111, Valve.V109),
        (Valve.V111, Valve.V110),
        (Valve.V111, Valve.V113),
        (Valve.V111, Valve.V114),
        (Valve.V111, Valve.V303),
        (Valve.V111, Valve.V306),
        (Valve.V111, Valve.V404),
        (Valve.V111, Valve.V406),
        (Valve.V111, Other.N2VENT),
        # V112
        (Valve.V112, Valve.V101),
        (Valve.V112, Valve.V102),
        (Valve.V112, Valve.V104),
        (Valve.V112, Valve.V201G),
        (Valve.V112, Valve.V202),
        (Valve.V112, Other.B1a),
        (Valve.V112, Other.B1b),
        (Valve.V112, Other.B1c),
        # V113
        (Valve.V113, Valve.V104),
        (Valve.V113, Valve.V105),
        (Valve.V113, Valve.V107),
        (Valve.V113, Valve.V108),
        (Valve.V113, Valve.V109),
        (Valve.V113, Valve.V110),
        (Valve.V113, Valve.V111),
        (Valve.V113, Valve.V114),
        (Valve.V113, Valve.V203),
        (Valve.V113, Valve.V303),
        (Valve.V113, Valve.V306),
        (Valve.V113, Valve.V401),
        (Valve.V113, Valve.V403),
        (Valve.V113, Valve.V405),
        (Valve.V113, Valve.V502H),
        (Valve.V113, Valve.V503H),
        # V114
        (Valve.V114, Valve.V001),
        (Valve.V114, Valve.V104),
        (Valve.V114, Valve.V105),
        (Valve.V114, Valve.V107),
        (Valve.V114, Valve.V108),
        (Valve.V114, Valve.V109),
        (Valve.V114, Valve.V110),
        (Valve.V114, Valve.V111),
        (Valve.V114, Valve.V113),
        (Valve.V114, Valve.V204),
        (Valve.V114, Valve.V205),
        (Valve.V114, Valve.V206),
        (Valve.V114, Valve.V303),
        (Valve.V114, Valve.V306),
        (Valve.V114, Valve.V404),
        (Valve.V114, Valve.V406),
        # V201G
        (Valve.V201G, Valve.V112),
        (Valve.V201G, Valve.V202),
        (Valve.V201G, Valve.V501H),  # comment if double condensing line valves
        (Valve.V201G, Valve.V502H),  # comment if double condensing line valves
        (Valve.V201G, Valve.V504H),
        (Valve.V201G, Valve.V505H),
        (Valve.V201G, Other.B1a),
        (Valve.V201G, Other.B1b),
        (Valve.V201G, Other.B1c),
        # V202
        (Valve.V202, Valve.V112),
        (Valve.V202, Valve.V201G),
        (Valve.V202, Valve.V203),
        (Valve.V202, Valve.V501H),  # comment if double condensing line valves
        (Valve.V202, Valve.V502H),  # comment if double condensing line valves
        (Valve.V202, Valve.V504H),
        (Valve.V202, Valve.V505H),
        (Valve.V202, Other.B1a),
        (Valve.V202, Other.B1b),
        (Valve.V202, Other.B1c),
        # V203
        (Valve.V203, Valve.V113),
        (Valve.V203, Valve.V201G),
        (Valve.V203, Valve.V202),
        (Valve.V203, Valve.V401),
        (Valve.V203, Valve.V403),
        (Valve.V203, Valve.V405),
        (Valve.V203, Valve.V501H),  # comment if double condensing line valves
        (Valve.V203, Valve.V502H),
        (Valve.V203, Valve.V503H),
        (Valve.V203, Valve.V504H),
        (Valve.V203, Valve.V505H),
        # V204
        (Valve.V204, Valve.V001),
        (Valve.V204, Valve.V114),
        (Valve.V204, Valve.V205),
        (Valve.V204, Valve.V206),
        (Valve.V204, Other.B1a),
        # V205
        (Valve.V205, Valve.V001),
        (Valve.V205, Valve.V114),
        (Valve.V205, Valve.V204),
        (Valve.V205, Valve.V206),
        (Valve.V205, Other.B1b),
        # V206
        (Valve.V206, Valve.V001),
        (Valve.V206, Valve.V114),
        (Valve.V206, Valve.V204),
        (Valve.V206, Valve.V205),
        (Valve.V206, Other.B1c),
        # V301
        (Valve.V301, Valve.V001),
        (Valve.V301, Valve.V003),
        (Valve.V301, Valve.V004),
        (Valve.V301, Valve.V302),
        (Valve.V301, Other.R1b),
        # V302
        (Valve.V302, Valve.V001),
        (Valve.V302, Valve.V003),
        (Valve.V302, Valve.V004),
        (Valve.V302, Valve.V301),
        (Valve.V302, Other.R1a),
        # V303
        (Valve.V303, Valve.V104),
        (Valve.V303, Valve.V105),
        (Valve.V303, Valve.V107),
        (Valve.V303, Valve.V108),
        (Valve.V303, Valve.V109),
        (Valve.V303, Valve.V110),
        (Valve.V303, Valve.V111),
        (Valve.V303, Valve.V113),
        (Valve.V303, Valve.V114),
        (Valve.V303, Valve.V304),
        (Valve.V303, Valve.V404),
        (Valve.V303, Valve.V406),
        (Valve.V303, Other.R1a),
        # V304
        (Valve.V304, Valve.V005),
        (Valve.V304, Valve.V303),
        (Valve.V304, Valve.V305),
        (Valve.V304, Valve.V402),
        (Valve.V304, Valve.V403),
        (Valve.V304, Valve.V407),
        (Valve.V304, Other.R1a),
        # V305
        (Valve.V305, Valve.V005),
        (Valve.V305, Valve.V304),
        (Valve.V305, Valve.V306),
        (Valve.V305, Valve.V402),
        (Valve.V305, Valve.V403),
        (Valve.V305, Valve.V407),
        (Valve.V304, Other.R1b),
        # V306
        (Valve.V306, Valve.V104),
        (Valve.V306, Valve.V105),
        (Valve.V306, Valve.V107),
        (Valve.V306, Valve.V108),
        (Valve.V306, Valve.V109),
        (Valve.V306, Valve.V110),
        (Valve.V306, Valve.V111),
        (Valve.V306, Valve.V114),
        (Valve.V306, Valve.V303),
        (Valve.V306, Valve.V305),
        (Valve.V306, Valve.V404),
        (Valve.V306, Valve.V406),
        (Valve.V306, Other.R1b),
        # V401
        (Valve.V401, Valve.V113),
        (Valve.V401, Valve.V203),
        (Valve.V401, Valve.V403),
        (Valve.V401, Valve.V405),
        (Valve.V401, Valve.V502H),
        (Valve.V401, Valve.V503H),
        (Valve.V401, Other.TRAP1),
        # V402
        (Valve.V402, Valve.V005),
        (Valve.V402, Valve.V304),
        (Valve.V402, Valve.V305),
        (Valve.V402, Valve.V403),
        (Valve.V402, Valve.V404),
        (Valve.V402, Valve.V407),
        (Valve.V402, Other.TRAP1),
        # V403
        (Valve.V403, Valve.V005),
        (Valve.V403, Valve.V113),
        (Valve.V403, Valve.V203),
        (Valve.V403, Valve.V304),
        (Valve.V403, Valve.V305),
        (Valve.V403, Valve.V401),
        (Valve.V403, Valve.V402),
        (Valve.V403, Valve.V405),
        (Valve.V403, Valve.V407),
        (Valve.V403, Valve.V502H),
        (Valve.V403, Valve.V503H),
        # V404
        (Valve.V404, Valve.V104),
        (Valve.V404, Valve.V105),
        (Valve.V404, Valve.V107),
        (Valve.V404, Valve.V108),
        (Valve.V404, Valve.V109),
        (Valve.V404, Valve.V110),
        (Valve.V404, Valve.V111),
        (Valve.V404, Valve.V113),
        (Valve.V404, Valve.V114),
        (Valve.V404, Valve.V303),
        (Valve.V404, Valve.V306),
        (Valve.V404, Valve.V402),
        (Valve.V404, Valve.V406),
        (Valve.V404, Other.TRAP1),
        # V405
        (Valve.V405, Valve.V113),
        (Valve.V405, Valve.V203),
        (Valve.V405, Valve.V401),
        (Valve.V405, Valve.V403),
        (Valve.V405, Valve.V502H),
        (Valve.V405, Valve.V503H),
        (Valve.V405, Other.TRAP2),
        # V406
        (Valve.V406, Valve.V104),
        (Valve.V406, Valve.V105),
        (Valve.V406, Valve.V107),
        (Valve.V406, Valve.V108),
        (Valve.V406, Valve.V109),
        (Valve.V406, Valve.V110),
        (Valve.V406, Valve.V111),
        (Valve.V406, Valve.V113),
        (Valve.V406, Valve.V114),
        (Valve.V406, Valve.V303),
        (Valve.V406, Valve.V306),
        (Valve.V406, Valve.V404),
        (Valve.V406, Valve.V407),
        (Valve.V406, Other.TRAP2),
        # V407
        (Valve.V407, Valve.V005),
        (Valve.V407, Valve.V304),
        (Valve.V407, Valve.V305),
        (Valve.V407, Valve.V402),
        (Valve.V407, Valve.V403),
        (Valve.V407, Valve.V406),
        (Valve.V407, Other.TRAP2),
        # V501H
        (Valve.V501H, Valve.V201G),  # comment if double condensing line valves
        (Valve.V501H, Valve.V202),  # comment if double condensing line valves
        (Valve.V501H, Valve.V203),  # comment if double condensing line valves
        (Valve.V501H, Valve.V502H),
        (Valve.V502H, Valve.V504H),
        (Valve.V502H, Valve.V505H),
        (Valve.V501H, Valve.VCOM),
        # V502H
        (Valve.V502H, Valve.V113),
        (Valve.V502H, Valve.V201G),  # comment if double condensing line valves
        (Valve.V502H, Valve.V202),  # comment if double condensing line valves
        (Valve.V502H, Valve.V203),
        (Valve.V502H, Valve.V401),
        (Valve.V502H, Valve.V403),
        (Valve.V502H, Valve.V405),
        (Valve.V502H, Valve.V501H),
        (Valve.V502H, Valve.V503H),
        (Valve.V502H, Valve.V504H),
        (Valve.V502H, Valve.V505H),
        # V503H
        (Valve.V503H, Valve.V113),
        (Valve.V503H, Valve.V203),
        (Valve.V503H, Valve.V401),
        (Valve.V503H, Valve.V403),
        (Valve.V503H, Valve.V405),
        (Valve.V503H, Valve.V502H),
        (Valve.V503H, Valve.VCOM),
        # V504H
        (Valve.V504H, Valve.V201G),
        (Valve.V504H, Valve.V202),
        (Valve.V504H, Valve.V203),
        (Valve.V504H, Valve.V501H),
        (Valve.V504H, Valve.V502H),
        (Valve.V504H, Valve.V505H),
        # V505H
        (Valve.V505H, Valve.V201G),
        (Valve.V505H, Valve.V202),
        (Valve.V505H, Valve.V203),
        (Valve.V505H, Valve.V501H),
        (Valve.V505H, Valve.V502H),
        (Valve.V505H, Valve.V505H),
        # V601G
        (Valve.V601G, Valve.V602),
        (Valve.V601G, Other.P8),
        (Valve.V601G, Other.VacuumCan),
        # V602
        (Valve.V602, Valve.V109),
        (Valve.V602, Valve.V602),
        (Valve.V602, Other.P8),
        # AIR
        (Other.AIR, Other.R2),
        # AUX
        (Other.AUX, Valve.V108),
        # B1a
        (Other.B1a, Valve.V112),
        (Other.B1a, Valve.V201G),
        (Other.B1a, Valve.V202),
        (Other.B1a, Valve.V204),
        (Other.B1a, Other.B1b),
        (Other.B1a, Other.B1c),
        # B1b
        (Other.B1b, Valve.V112),
        (Other.B1b, Valve.V201G),
        (Other.B1b, Valve.V202),
        (Other.B1b, Valve.V205),
        (Other.B1b, Other.B1a),
        (Other.B1b, Other.B1c),
        # B1c
        (Other.B1c, Valve.V112),
        (Other.B1c, Valve.V201G),
        (Other.B1c, Valve.V202),
        (Other.B1c, Valve.V206),
        (Other.B1c, Other.B1a),
        (Other.B1c, Other.B1b),
        # B2
        (Other.B2, Valve.V106),
        (Other.B2, Valve.V107),
        # N2VENT
        (Other.N2VENT, Valve.V111),
        # P1
        (Other.P1, Valve.V101),
        (Other.P1, Other.VacuumCan),
        # P2
        (Other.P2, Valve.V112),
        (Other.P2, Valve.V201G),
        (Other.P2, Valve.V202),
        (Other.P2, Other.B1a),
        (Other.P2, Other.B1b),
        (Other.P2, Other.B1c),
        # P3
        (Other.P3, Valve.V201G),
        (Other.P3, Valve.V202),
        (Other.P3, Valve.V203),
        (Other.P3, Valve.V501H),
        (Other.P3, Valve.V502H),
        # P4
        (Other.P4, Valve.V005),
        (Other.P4, Valve.V304),
        (Other.P4, Valve.V305),
        (Other.P4, Valve.V402),
        (Other.P4, Valve.V403),
        (Other.P4, Valve.V407),
        # P5
        (Other.P5, Valve.V003),
        (Other.P5, Valve.V004),
        (Other.P5, Valve.V005),
        (Other.P5, Other.Tank),
        # P6
        (Other.P6, Valve.V104),
        (Other.P6, Valve.V105),
        (Other.P6, Valve.V107),
        (Other.P6, Valve.V108),
        (Other.P6, Valve.V109),
        (Other.P6, Valve.V110),
        (Other.P6, Valve.V111),
        (Other.P6, Valve.V113),
        (Other.P6, Valve.V114),
        (Other.P6, Valve.V303),
        (Other.P6, Valve.V306),
        (Other.P6, Valve.V404),
        (Other.P6, Valve.V406),
        # P7
        (Other.P7, Valve.V001),
        (Other.P7, Valve.V003),
        (Other.P7, Valve.V004),
        (Other.P7, Valve.V301),
        (Other.P7, Valve.V302),
        # P8
        (Other.P8, Valve.V601G),
        (Other.P8, Valve.V602),
        # R1a
        (Other.R1a, Valve.V302),
        (Other.R1a, Valve.V303),
        (Other.R1a, Valve.V304),
        # R1b
        (Other.R1b, Valve.V301),
        (Other.R1b, Valve.V305),
        (Other.R1b, Valve.V306),
        # R2
        (Other.R2, Valve.V105),
        (Other.R2, Valve.V106),
        (Other.R2, Other.AIR),
        # TANK
        (Other.Tank, Valve.V003),
        (Other.Tank, Valve.V004),
        (Other.Tank, Valve.V005),
        # TEST
        (Other.TEST, Valve.V102),
        # TRAP1
        (Other.TRAP1, Valve.V401),
        (Other.TRAP1, Valve.V402),
        (Other.TRAP1, Valve.V404),
        # TRAP2
        (Other.TRAP2, Valve.V405),
        (Other.TRAP2, Valve.V406),
        (Other.TRAP2, Valve.V407),
        # VacuumCan
        (Other.VacuumCan, Valve.V101),
        (Other.VacuumCan, Valve.V601G),
        # VENT
        (Other.VENT, Valve.V110),
    ),
)
