NAME = "CreatePipe"
DESCRIPTION = "Create an anonymous pipe pair using kernel32!CreatePipe"
PARAMS = [
]
DEPENDENCIES = []
DEFAULT = True

def build_security_attributes(base_address):
    import struct
    """
    Build a SECURITY_ATTRIBUTES structure for x64 Windows.

    Layout:
        DWORD  nLength;              // 4
        DWORD  padding;              // 4 (to align pointer)
        PVOID  lpSecurityDescriptor; // 8
        BOOL   bInheritHandle;       // 4
        DWORD  padding;              // 4
    Total: 24 bytes
    """
    nLength = 24
    inherit = 1

    data = struct.pack(
        "<I I Q I I",
        nLength,                # DWORD
        0,                      # padding
        0,   # 8-byte pointer
        inherit,                # BOOL
        0                       # trailing padding
    )

    return bytearray(data), base_address + nLength

def CreatePipe(agent_id):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr
    import struct

    agent = Agent.by_id(agent_id)
    # Resolve kernel32!CreatePipe address
    func_addr = Syscall.sys(agent.id, "CreatePipe")
    scratchpad = agent.scratchpad

    # Memory Layout on Scratchpad:
    # 0x00: hReadPipe (8 bytes)
    # 0x08: hWritePipe (8 bytes)
    
    # 1. Prepare placeholders for the two Handles
    hRead_data, hWrite_ptr = build_ptr(scratchpad, b"\x00" * 8)
    hWrite_data, sa_ptr = build_ptr(hWrite_ptr, b"\x00" * 8)
    sa_data, next_ptr = build_security_attributes(sa_ptr)
    buffer_size = 0
    
    # 4 Parameters for CreatePipe (x64 ABI)
    params = [
        scratchpad,  # P1: phReadPipe (Pointer to 0x00)
        hWrite_ptr,  # P2: phWritePipe (Pointer to 0x08)
        sa_ptr,           # P3: lpPipeAttributes (NULL = Default Security)
        buffer_size  # P4: nSize (Buffer size)
    ]

    # Generate the library call shellcode
    shellcode = push_rtl(func_addr, params, agent.debug)
    
    # Combine the data to be written to the scratchpad
    data = hRead_data + hWrite_data + sa_data
    
    #printf"CreatePipe(hRead={hex(scratchpad)}, hWrite={hex(hWrite_ptr)}, lpPipeAttributes = {hex(sa_ptr)}, size={buffer_size})")
    return data, shellcode

def createAnonymousPipe(agent_id):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad

    # 1. Generate core logic and scratchpad data
    data, shellcode = CreatePipe(agent_id)
    write_scratchpad(agent_id, data)
    
    # 2. Execute the library call
    # Returns TRUE (1) on success, FALSE (0) on failure
    success = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')

    # 3. Read the resulting handles back from the scratchpad
    # Handles are 4 bytes, but we read 8-byte slots for x64 alignment
    handles_raw = read_scratchpad(agent_id, 32)
    hRead = int.from_bytes(handles_raw[0:8], 'little')
    hWrite = int.from_bytes(handles_raw[16:24], 'little')

    #printf"CreatePipe Success: {bool(success)}, Read: {hex(hRead)}, Write: {hex(hWrite)}")
    return success, hRead, hWrite

def function(agent_id, args):
    success, hRead, hWrite = createAnonymousPipe(agent_id)
    
    return {
        "retval": bool(success),
        "READ_HANDLE": hRead,
        "WRITE_HANDLE": hWrite
    }