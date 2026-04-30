NAME = "EnumServicesStatusExW"
DESCRIPTION = "Enumerates services in the specified service control manager database."
PARAMS = [
    {"name": "h_scm", "description": "Handle to the SCM database (from OpenSCManagerW)", "type": "hex"},
    {"name": "service_type", "description": "Type of services to list (0x30 for WIN32)", "type": "hex", "optional": True, "default": "0x30"},
    {"name": "service_state", "description": "State of services to list (0x3 for ALL)", "type": "hex", "optional": True, "default": "0x3"},
    {"name": "buffer_size", "description": "Size of the buffer to allocate for results", "type": "hex", "optional": True, "default": "0x10000"}
]
DEPENDENCIES = []
DEFAULT = True

def EnumServicesStatusExW_Payload(agent_id, h_scm, service_type, service_state, buffer_size):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr
    
    agent = Agent.by_id(agent_id)
    func_addr = Syscall.sys(agent.id, "EnumServicesStatusExW")
    scratchpad = agent.scratchpad

    # Memory Layout in scratchpad:
    # 0x00: pcbBytesNeeded (4 bytes)
    # 0x04: lpServicesReturned (4 bytes)
    # 0x08: lpResumeHandle (4 bytes)
    # 0x10: Output Buffer (Variable size)
    
    # Initialize the pointers area with zeros
    header_data, buffer_ptr = build_ptr(scratchpad, b"\x00" * buffer_size)

    # Signature:
    # BOOL EnumServicesStatusExW(
    #   SC_HANDLE    hSCManager,
    #   SC_ENUM_TYPE InfoLevel,         (Always 0 / SC_ENUM_PROCESS_INFO)
    #   DWORD        dwServiceType,
    #   DWORD        dwServiceState,
    #   LPBYTE       lpBuffer,
    #   DWORD        cbBufSize,
    #   LPDWORD      pcbBytesNeeded,
    #   LPDWORD      lpServicesReturned,
    #   LPDWORD      lpResumeHandle,
    #   LPCWSTR      pszGroupName       (NULL = 0)
    # );
    
    params = [
        h_scm,              # hSCManager
        0,                  # InfoLevel
        service_type,       # dwServiceType
        service_state,      # dwServiceState
        scratchpad + 24,    # lpBuffer
        buffer_size,        # cbBufSize
        scratchpad,         # pcbBytesNeeded
        scratchpad + 8,     # lpServicesReturned
        scratchpad + 16,     # lpResumeHandle
        0                   # pszGroupName
    ]
    
    shellcode = push_rtl(func_addr, params, agent.debug)
    return header_data, shellcode

def function(agent_id, args):
    from services.orders import send_and_wait, write_scratchpad, read_scratchpad
    import struct

    h_scm = args[0]
    service_type = args[1]
    service_state = args[2]
    buffer_size = args[3]

    # 1. Prepare and Execute
    data, shellcode = EnumServicesStatusExW_Payload(agent_id, h_scm, service_type, service_state, buffer_size)
    write_scratchpad(agent_id, data)
    
    response_bytes = send_and_wait(agent_id, shellcode)
    success = int.from_bytes(response_bytes, 'little')

    # 2. Extract Results from Metadata Pointers
    # pcbBytesNeeded (0:4), lpServicesReturned (4:8)
    meta = read_scratchpad(agent_id, buffer_size)
    count = int.from_bytes(meta[8:16], byteorder='little')

    # 3. Read the actual buffer (offset 16 onwards)
    print(count)
    raw_buffer = meta
    
    return {
        "retval": 0,
        "count": count,
        "raw_buffer": raw_buffer
    }