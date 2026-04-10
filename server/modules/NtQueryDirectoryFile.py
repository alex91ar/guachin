NAME = "NtQueryDirectoryFile"
DESCRIPTION = "Enumerate files and directories into a specific buffer address"
PARAMS = [
    {"name":"file_handle", "description":"Handle of an open directory", "type":"bytes"},
    {"name":"buffer_ptr", "description":"Memory address to write results into", "type":"hex"},
    {"name":"buffer_size", "description":"Size of the provided buffer", "type":"int"},
]



def NtQueryDirectoryFile(agent_id, handle, buffer_ptr, buffer_size):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtQueryDirectoryFile")
    scratchpad = agent.scratchpad # Used here only for the 16-byte IoStatusBlock

    # Parameter Setup
    FileHandle = handle
    Event = 0x0
    ApcRoutine = 0x0
    ApcContext = 0x0
    
    # 1. IoStatusBlock (16 bytes) - We always Need this for status feedback
    # We place it at the start of the scratchpad
    IoStatusBlock_data, next_ptr = build_ptr(scratchpad, b"\x00" * 16)
    
    # Static parameters for Directory Queries
    Length = buffer_size
    FileInformationClass = 0x3 # FileBothDirectoryInformation
    ReturnSingleEntry = 0x0     # FALSE (get all entries that fit)
    RestartScan = 0x1           # TRUE (start search from the beginning)
    FileName = 0x0

    # NtQueryDirectoryFile strictly requires 11 parameters in x64
    params = [
        FileHandle,           # P1: R10
        Event,                # P2: RDX
        ApcRoutine,           # P3: R8
        ApcContext,           # P4: R9
        scratchpad,           # P5: [RSP+0x28] (Pointer to IoStatusBlock)
        buffer_ptr,           # P6: [RSP+0x30] (Your provided buffer address)
        Length,               # P7: [RSP+0x38]
        FileInformationClass, # P8: [RSP+0x40]
        ReturnSingleEntry,    # P9: [RSP+0x48]
        FileName,          # P10:[RSP+0x50] (Pointer to UNICODE_STRING or NULL)
        RestartScan           # P11:[RSP+0x58]
    ]

    # Generate the shellcode to trigger the syscall
    shellcode = push_syscall(syscall, params, agent.debug)
    
    # Only IoStatusBlock_data is written to the scratchpad here
    # Since the results go to buffer_ptr, we don't include them in 'data'
    data = IoStatusBlock_data
    
    #printf"NtQueryDirectoryFile(Handle={hex(FileHandle)}, Dest={hex(buffer_ptr)}, Size={Length})")
    return data, shellcode

def queryDirectoryToBuffer(agent_id, handle, buffer_ptr, buffer_size):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    
    # 1. Generate and write the syscall logic
    data, shellcode = NtQueryDirectoryFile(agent_id, handle, buffer_ptr, buffer_size)
    write_scratchpad(agent_id, data)
    
    # 2. Execute the syscall on the agent
    response_retval = int.from_bytes(send_and_wait(agent_id, shellcode), byteorder='little')
    
    # 3. Read the IoStatusBlock from the scratchpad to see how many bytes were actually written
    # The 'Information' field (offset 8-15) contains the number of bytes populated in buffer_ptr
    io_status_raw = read_scratchpad(agent_id, 16)
    bytes_written = int.from_bytes(io_status_raw[8:16], byteorder='little')
    
    #printf"retval: {hex(response_retval)}, Bytes Returned: {bytes_written}")
    return response_retval, bytes_written

def function(agent_id, args):
    # args: [handle, buffer_ptr, buffer_size]
    retval, bytes_count = queryDirectoryToBuffer(agent_id, args[0], args[1], args[2])
    
    return {
        "retval": retval, 
        "bytes_written": bytes_count,
        "location": hex(args[1])
    }