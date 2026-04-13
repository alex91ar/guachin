NAME = "NtFlushBuffersFile"
DESCRIPTION = "Enumerate file metadata (size, attributes, times, path) using native ntdll.NtFlushBuffersFile."
PARAMS = [
    {"name":"file_handle", "description":"Handle to the open file or volume (must have WRITE access)", "type":"hex"}
]

# Dependencies: 
# 1. NtFlushBuffersFile (to perform the flush)
DEPENDENCIES = []
DEFAULT = True

def NtFlushBuffersFile_Shellcode(agent_id, file_handle):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    import struct

    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtFlushBuffersFile")
    scratchpad = agent.scratchpad
    
    # 1. Prepare IO_STATUS_BLOCK (8 bytes mandatory)
    # The kernel needs a pointer to write the operation's completion status.
    io_status_data, io_status_ptr = build_ptr(scratchpad, b"\x00" * 8)

    # 2. Setup Syscall Parameters:
    # args: [FileHandle, IoStatusBlock]
    params = [
        file_handle,           # Handle to the file/volume
        io_status_ptr          # &IoStatusBlock (Now in scratchpad)
    ]
    
    #printf"[*] NtFlushBuffersFile(Handle={hex(file_handle)}, IoStatus={hex(io_status_ptr)})")
    
    shellcode = push_syscall(syscall, params, agent.debug)
    
    # Combined data to write to scratchpad: [IO_STATUS_BLOCK]
    return io_status_data, shellcode

def function(agent_id, args):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    import struct
    
    file_handle = args[0]

    # 1. GENERATE DATA AND SHELLCODE
    data, shellcode = NtFlushBuffersFile_Shellcode(agent_id, file_handle)
    
    # 2. WRITE TO AGENT SCRATCHPAD
    write_scratchpad(agent_id, data)
    
    # 3. TRIGGER SYSCALL
    response = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response, 'little')
    
    # 4. READ RESULTS FROM SCRATCHPAD
    # We read the IO_STATUS_BLOCK (8 bytes) to check for additional info if needed
    result_content = read_scratchpad(agent_id, 8)
    
    if ntstatus == 0:
        msg = f"Success: Buffers for handle {hex(file_handle)} flushed to disk."
    else:
        msg = f"Error: NtFlushBuffersFile failed with {hex(ntstatus)}"

    return {
        "Result": msg,
        "NTSTATUS": hex(ntstatus),
        "Handle": hex(file_handle),
        "StatusBlockHex": result_content.hex()
    }