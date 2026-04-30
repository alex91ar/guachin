NAME = "QueryServiceConfig2W"
DESCRIPTION = "Retrieves the optional configuration parameters of the specified service (like Description)."
PARAMS = [
    {"name": "h_service", "description": "Handle to the service (from OpenServiceW)", "type": "hex"},
    {"name": "info_level", "description": "1 for Description, 2 for FailureActions", "type": "int", "optional": True, "default": 1},
    {"name": "buffer_size", "description": "Size of the buffer to allocate", "type": "hex", "optional": True, "default": "0x1000"}
]
DEPENDENCIES = []
DEFAULT = True

def QueryServiceConfig2W_Payload(agent_id, h_service, info_level, buffer_size):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr
    
    agent = Agent.by_id(agent_id)
    func_addr = Syscall.sys(agent.id, "QueryServiceConfig2W")
    scratchpad = agent.scratchpad

    # Memory Layout in scratchpad:
    # 0x00: pcbBytesNeeded (4 bytes)
    # 0x08: Output Buffer (starts here)
    
    # Initialize pointer area for pcbBytesNeeded
    header_data, buffer_ptr = build_ptr(scratchpad, b"\x00" * 8)

    # Signature:
    # BOOL QueryServiceConfig2W(
    #   SC_HANDLE hService,
    #   DWORD     dwInfoLevel,
    #   LPBYTE    lpBuffer,
    #   DWORD     cbBufSize,
    #   LPDWORD   pcbBytesNeeded
    # );
    
    params = [
        h_service,       # hService
        info_level,      # dwInfoLevel (1 = SERVICE_CONFIG_DESCRIPTION)
        scratchpad + 8,  # lpBuffer
        buffer_size,     # cbBufSize
        scratchpad       # pcbBytesNeeded
    ]
    
    shellcode = push_rtl(func_addr, params, agent.debug)
    return header_data, shellcode

def function(agent_id, args):
    from services.orders import send_and_wait, write_scratchpad, read_scratchpad
    import struct

    h_service = args[0]
    info_level = args[1] if len(args) > 1 else 1
    buffer_size = args[2] if len(args) > 2 else 4096

    # 1. Prepare and Execute
    data, shellcode = QueryServiceConfig2W_Payload(agent_id, h_service, info_level, buffer_size)
    write_scratchpad(agent_id, data)
    
    response_bytes = send_and_wait(agent_id, shellcode)
    success = int.from_bytes(response_bytes, 'little')

    meta = read_scratchpad(agent_id, 8)
    bytes_needed = struct.unpack("<I", meta[0:4])[0]

    if success == 0:
        return {
            "retval": -1,
            "bytes_needed": bytes_needed,
            "message": "Buffer too small. Re-run with recommended bytes_needed."
        }

    # 2. Parse results
    raw_buffer = read_scratchpad(agent_id, buffer_size + 8)
    
    # If InfoLevel == 1 (Description):
    # The buffer contains a SERVICE_DESCRIPTIONW struct: [LPWSTR lpDescription]
    # lpDescription is an absolute pointer to the string in the scratchpad.
    result_text = ""
    if info_level == 1:
        description_ptr = struct.unpack_from("<Q", raw_buffer, 8)[0]
        if description_ptr:
            from models.agent import Agent
            agent = Agent.by_id(agent_id)
            offset = description_ptr - agent.scratchpad
            # Extract and decode UTF-16 string
            str_data = raw_buffer[offset:].split(b'\x00\x00')[0]
            result_text = str_data.decode('utf-16le', errors='ignore')

    return {
        "retval": 0,
        "description": result_text if info_level == 1 else "Parsed as non-description level",
        "raw_hex": raw_buffer[8:8+bytes_needed].hex()
    }