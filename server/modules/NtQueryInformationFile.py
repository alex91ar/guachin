NAME = "NtQueryInformationFile"
DESCRIPTION = "Enumerate file metadata (size, attributes, times, path) using native ntdll.NtQueryInformationFile."
PARAMS = [
    {"name":"file_handle", "description":"Handle to the open file", "type":"hex"},
    {"name":"info_class", "description":"FileInformationClass (e.g. 5 for Standard, 4 for Basic)", "type":"int"},
    {"name":"buffer_size", "description":"Size of the structure to return (e.g. 24 for class 5, 40 for class 4)", "type":"int"}
]

# Dependencies: 
# 1. NtQueryInformationFile (to query EOF)
DEPENDENCIES = []

def NtQueryInformationFile_Shellcode(agent_id, file_handle, info_class, buffer_size):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    import struct

    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtQueryInformationFile")
    scratchpad = agent.scratchpad
    
    # 1. Prepare Buffer for FileInformation (Variable size based on class)
    # We allocate the size requested by the user
    query_data, next_ptr = build_ptr(scratchpad, b"\x00" * buffer_size)

    # 2. Prepare IO_STATUS_BLOCK (8 bytes mandatory)
    # Struct: [Status Pointer / Information Pointer]
    io_status_data, io_status_ptr = build_ptr(next_ptr, b"\x00" * 8)

    # 3. Setup Syscall Parameters:
    # args: [FileHandle, IoStatusBlock, FileInformation, Length, FileInformationClass]
    params = [
        file_handle,           # Handle
        io_status_ptr,         # &IoStatusBlock
        scratchpad,            # &FileInformation (Our buffer starts at scratchpad head)
        buffer_size,           # Length
        info_class             # FileInformationClass
    ]
    
    print(f"[*] NtQueryInformationFile(Handle={hex(file_handle)}, Class={info_class}, BufSize={buffer_size})")
    
    shellcode = push_syscall(syscall, params, agent.debug)
    
    # Combined data to write to scratchpad: [QUERY_BUF] + [IO_STATUS_BLOCK]
    return query_data + io_status_data, shellcode

def function(agent_id, args):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    import struct
    
    file_handle = args[0]
    info_class = args[1]
    buffer_size = args[2]

    # 1. GENERATE DATA AND SHELLCODE
    data, shellcode = NtQueryInformationFile_Shellcode(agent_id, file_handle, info_class, buffer_size)
    
    # 2. WRITE TO AGENT SCRATCHPAD
    write_scratchpad(agent_id, data)
    
    # 3. TRIGGER SYSCALL
    response = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response, 'little')
    
    # 4. READ RESULTS FROM SCRATCHPAD
    # We read the entire buffer requested by the user
    result_content = read_scratchpad(agent_id, buffer_size)
    
    # Read the IO_STATUS_BLOCK Information member (at scratchpad + buffer_size + 8)
    # This often contains how many bytes were actually written or certain class-specific flags
    # ...

    return {
        "retval": ntstatus,
        "BufferHex": result_content
    }