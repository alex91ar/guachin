NAME = "services"
DESCRIPTION = "Get all services"
PARAMS = [
]
DEPENDENCIES = ["OpenSCManagerW", "EnumServicesStatusExW", "CloseServiceHandle"]
DEFAULT = True

def parse_enum_services(scratchpad, raw_buffer, count):
    import struct

    if raw_buffer is None:
        raise ValueError("raw_buffer is None")

    if isinstance(raw_buffer, (bytes, bytearray)):
        blob = bytes(raw_buffer)
    elif isinstance(raw_buffer, str):
        raw_buffer = (
            raw_buffer
            .replace("0x", "")
            .replace(" ", "")
            .replace("\n", "")
            .replace("\r", "")
        )
        blob = bytes.fromhex(raw_buffer)
    else:
        blob = bytes(raw_buffer)

    # ENUM_SERVICE_STATUS_PROCESSW x64
    # LPWSTR lpServiceName      Q
    # LPWSTR lpDisplayName      Q
    # SERVICE_STATUS_PROCESS    9 DWORDs
    # padding                   4 bytes
    fmt = "<QQIIIIIIIIII"
    struct_size = struct.calcsize(fmt)

    state_names = {
        1: "Stopped",
        2: "Start Pending",
        3: "Stop Pending",
        4: "Running",
        5: "Continue Pending",
        6: "Pause Pending",
        7: "Paused",
    }

    def read_utf16le_string(ptr):
        if not ptr:
            return ""

        offset = ptr - scratchpad

        if offset < 0 or offset >= len(blob):
            return ""

        # Pointers to WCHAR strings should be 2-byte aligned.
        # If scratchpad math lands odd, decoding will produce chopped/garbled strings.
        if offset % 2 != 0:
            offset -= 1

        end = offset

        while end + 1 < len(blob):
            if blob[end] == 0 and blob[end + 1] == 0:
                break
            end += 2

        data = blob[offset:end]

        try:
            return data.decode("utf-16le", errors="replace").rstrip("\x00")
        except Exception:
            return ""

    services = []

    max_items = min(count, len(blob) // struct_size)

    for i in range(max_items):
        offset = i * struct_size + 24
        fields = struct.unpack_from(fmt, blob, offset)

        ptr_name = fields[0]
        ptr_display = fields[1]

        service_type = fields[2]
        current_state = fields[3]
        controls_accepted = fields[4]
        win32_exit_code = fields[5]
        service_specific_exit_code = fields[6]
        checkpoint = fields[7]
        wait_hint = fields[8]
        pid = fields[9]
        service_flags = fields[10]
        service_name = read_utf16le_string(ptr_name)
        display_name = read_utf16le_string(ptr_display)

        services.append({
            "name": service_name,
            "service_name": service_name,
            "display_name": display_name,
            "status": state_names.get(current_state, f"Unknown ({current_state})"),
            "state": current_state,
            "pid": pid,
            "service_type": service_type,
            "controls_accepted": controls_accepted,
            "win32_exit_code": win32_exit_code,
            "service_specific_exit_code": service_specific_exit_code,
            "checkpoint": checkpoint,
            "wait_hint": wait_hint,
            "service_flags": service_flags,
        })

    return services

def function(agent_id, args):
    from services.orders import send_and_wait, read_scratchpad
    from models.agent import Agent
    scratchpad = Agent.by_id(agent_id).scratchpad
    retopenSC = OpenSCManagerW(agent_id, ["", "", "0x4"])
    if retopenSC["retval"] == 0:
        enumServicesStatus = EnumServicesStatusExW(agent_id, [retopenSC["handle"], "0x30", "0x3", "0x10000"])
        if(enumServicesStatus["retval"] == 0):
            print(enumServicesStatus)
            ret_struct = parse_enum_services(scratchpad, enumServicesStatus["raw_buffer"], enumServicesStatus["count"])
        CloseServiceHandle(agent_id, [retopenSC["handle"]])
        if enumServicesStatus["retval"] == 0:
            return{
                "retval":0,
                "ret_struct":ret_struct
            }
        else:
            return{
                "retval":-1
            }
