NAME = "QueryServiceConfigW"
DESCRIPTION = "Retrieves the primary configuration parameters (BinaryPath, StartType, AccountName, etc.)"
PARAMS = [
    {"name": "h_service", "description": "Handle to the service (from OpenServiceW)", "type": "hex"},
    {"name": "buffer_size", "description": "Size of the buffer to allocate (default 8KB)", "type": "hex", "optional": True, "default": 8192}
]
DEPENDENCIES = []
DEFAULT = True

def QueryServiceConfigW_Payload(agent_id, h_service, buffer_size):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr
    
    agent = Agent.by_id(agent_id)
    func_addr = Syscall.sys(agent.id, "QueryServiceConfigW")
    scratchpad = agent.scratchpad

    # Memory Layout in scratchpad:
    # 0x00: pcbBytesNeeded (4 bytes)
    # 0x08: Output Buffer (starts here)
    
    header_data, buffer_ptr = build_ptr(scratchpad, b"\x00" * 8)

    # Signature:
    # BOOL QueryServiceConfigW(
    #   SC_HANDLE              hService,
    #   LPQUERY_SERVICE_CONFIGW lpServiceConfig,
    #   DWORD                  cbBufSize,
    #   LPDWORD                pcbBytesNeeded
    # );
    
    params = [
        h_service,       # hService
        scratchpad + 8,  # lpServiceConfig
        buffer_size,     # cbBufSize
        scratchpad       # pcbBytesNeeded
    ]
    
    shellcode = push_rtl(func_addr, params, agent.debug)
    return header_data, shellcode

def function(agent_id, args):
    from services.orders import send_and_wait, write_scratchpad, read_scratchpad
    from models.agent import Agent
    import struct

    h_service = args[0]
    buffer_size = args[1] if len(args) > 1 else 8192
    agent = Agent.by_id(agent_id)

    data, shellcode = QueryServiceConfigW_Payload(agent_id, h_service, buffer_size)
    write_scratchpad(agent_id, data)
    
    response_bytes = send_and_wait(agent_id, shellcode)
    success = int.from_bytes(response_bytes, 'little')


    # x64 QUERY_SERVICE_CONFIGW Structure (36 bytes + internal padding -> 48 bytes total)
    # DWORD  dwServiceType;        (4)
    # DWORD  dwStartType;          (4)
    # DWORD  dwErrorControl;       (4)
    # padding                      (4)
    # LPWSTR lpBinaryPathName;     (8)
    # LPWSTR lpLoadOrderGroup;     (8)
    # DWORD  dwTagId;              (4)
    # padding                      (4)
    # LPWSTR lpDependencies;       (8)
    # LPWSTR lpServiceStartName;   (8)
    
    raw_buffer = read_scratchpad(agent_id, buffer_size + 8)
    def resolve_path(ptr):
        if not ptr or ptr < agent.scratchpad: return "None"
        offset = ptr - agent.scratchpad
        str_start = raw_buffer[offset:]
        end = str_start.find(b"\x00\x00")
        string_w = str_start[:end+1]
        print(offset)
        print(str_start)
        return string_w.decode('utf-16le', errors='ignore')
    
    def resolve_account(ptr):
        if not ptr or ptr < agent.scratchpad: return "None"
        offset = ptr - agent.scratchpad
        start = raw_buffer.find(b"\x00\x00", offset)
        start = raw_buffer.find(b"\x00\x00", start+2)
        start = raw_buffer.find(b"\x00\x00", start+2)
        start = raw_buffer.find(b"\x00\x00", start+2)
        start = raw_buffer.find(b"\x00\x00", start+2)
        start = raw_buffer.find(b"\x00\x00", start+2)
        start = raw_buffer.find(b"\x00\x00", start+2)
        str_start = raw_buffer[start:]
        end = str_start.find(b"\x00\x00")
        string_w = str_start[:end+1]
        print(offset)
        print(str_start)
        return string_w.decode('utf-16le', errors='ignore')

    # Offsets in the returned struct (raw_buffer[8:] because header is 8 bytes)
    bin_path_ptr = struct.unpack_from("<Q", raw_buffer, 8 + 16)[0]
    start_type = struct.unpack_from("<I", raw_buffer, 8 + 4)[0]
    account_ptr = struct.unpack_from("<Q", raw_buffer, 8 + 40)[0]

    return {
        "retval": 0,
        "binary_path": resolve_path(bin_path_ptr),
        "account_name": resolve_account(account_ptr),
        "start_type": start_type, # 2=Auto, 3=Manual, 4=Disabled
        "service_type": struct.unpack_from("<I", raw_buffer, 8 + 0)[0]
    }