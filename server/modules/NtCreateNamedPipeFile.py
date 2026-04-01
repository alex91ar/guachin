NAME = "NtCreateNamedPipeFile"
DESCRIPTION = "Direct Syscall to create a native named pipe with custom access"
PARAMS = [
    {"name":"pipe_name", "description":"NT path (e.g. \\Device\\NamedPipe\\HackerPipe)", "type":"str"},
    {"name":"desired_access", "description":"Access mask (e.g. 0xC0100000)", "type":"hex"},
]

def NtCreateNamedPipeFile(agent_id, pipe_name, desired_access):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, build_object_attributes, push_syscall
    import struct
    
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtCreateNamedPipeFile")
    scratchpad = agent.scratchpad

    # Memory Layout for Syscall
    # 1. FileHandle (8 bytes)
    h_file_data, object_attributes_ptr = build_ptr(scratchpad, b"\x00" * 8)

    # 2. ObjectAttributes (48 bytes)
    object_attributes_data, status_block_ptr = build_object_attributes(object_attributes_ptr, pipe_name)
    # 3. IoStatusBlock (16 bytes)
    status_block_data, next_ptr = build_ptr(status_block_ptr, b"\x00" * 16)

    params = [
        scratchpad,              # P1:  R10 (&FileHandle)
        desired_access,          # P2:  RDX (Dynamic Access Mask)
        object_attributes_ptr,   # P3:  R8  (&ObjAttr)
        status_block_ptr,        # P4:  R9  (&IoStatusBlock)
        0x03,                    # P5:  [RSP+0x28] ShareAccess
        0x03,                    # P6:  [RSP+0x30] CreateDisposition (FILE_CREATE)
        0x20,                    # P7:  [RSP+0x38] CreateOptions (SYNCHRONOUS)
        0x0,                     # P8:  [RSP+0x40] NamedPipeType
        0x0,                     # P9:  [RSP+0x48] ReadMode
        0x0,                     # P10: [RSP+0x50] CompletionMode
        0xFFFFFFFFFFFFFFFF,      # P11: [RSP+0x58] MaxInstances
        0,                       # P12: [RSP+0x60] InboundQuota
        0,                       # P13: [RSP+0x68] OutboundQuota
        0x0                      # P14: [RSP+0x70] DefaultTimeout
    ]

    shellcode = push_syscall(syscall, params, agent.debug)
    data = h_file_data + object_attributes_data + object_attributes_data + status_block_data
    
    # Trace/Print all parameters for debugging and audit
    print(f"NtCreateNamedPipeFile Parameters:")
    for i, p in enumerate(params, 1):
        print(f"  P{i:02}: {hex(p) if isinstance(p, int) else p}")
    
    return data, shellcode

def createNamedPipe(agent_id, pipe_name, desired_access):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    
    data, shellcode = NtCreateNamedPipeFile(agent_id, pipe_name, desired_access)
    write_scratchpad(agent_id, data)
    
    # Execute the Syscall
    response_retval = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')
    
    # Read back the Handle
    handle_raw = read_scratchpad(agent_id, 8)
    hPipe = int.from_bytes(handle_raw, 'little')
    
    print(f"retval: {hex(response_retval)}, hPipe: {hex(hPipe)}")
    return response_retval, hPipe

def function(agent_id, args):
    # args: [pipe_name, desired_access]
    pipe_name = args[0]
    access = args[1]
    
    retval, hPipe = createNamedPipe(agent_id, pipe_name, access)
    return {"retval": retval, "PIPE_HANDLE": hPipe}