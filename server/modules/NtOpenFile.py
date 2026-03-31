NAME = "NtOpenFile"
DESCRIPTION = "Opens an existing file in the target agent"
PARAMS = [
    {"name":"filename", "description":"Complete path (e.g. \\??\\C:\\temp\\log.txt)", "type":"str"},
    {"name":"desired_access", "description":"Access level (default: GENERIC_READ)", "type":"hex"},
]

def NtOpenFile(agent_id, name, desired_access): # Default GENERIC_READ | SYNCHRONIZE
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, build_unicode_string, build_object_attributes, push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtOpenFile") # Using syscall 0x33
    scratchpad = agent.scratchpad # Base address of our memory buffer

    # Set up pointers on the scratchpad
    # 1. &FileHandle (8 bytes)
    filehandle_data, unicode_str_ptr = build_ptr(scratchpad, b"\x00" * 8)
    
    # 2. &UnicodeName (16 bytes for struct + string itself)
    unicode_str_data, object_attributes_ptr = build_unicode_string(unicode_str_ptr, name)
    
    # 3. &ObjectAttributes (48 bytes for struct)
    object_attributes_data, status_block_ptr = build_object_attributes(object_attributes_ptr, unicode_str_ptr)
    
    # 4. &IoStatusBlock (16 bytes)
    status_block_data, next_ptr = build_ptr(status_block_ptr, b"\x00" * 16)

    params = [
        scratchpad,              # P1: R10 (&FileHandle)
        desired_access,          # P2: RDX (Access Mask)
        object_attributes_ptr,   # P3: R8  (&ObjAttributes)
        status_block_ptr,        # P4: R9  (&IoStatusBlock)
        0x07,                    # P5: [RSP+0x28] (ShareAccess)
        0x20                     # P6: [RSP+0x30] (OpenOptions - Synchronous)
    ]

    # Generate the x64 shellcode for the syscall
    shellcode = push_syscall(syscall, params)
    
    # Combine the data chunks to be written to the agent's scratchpad memory
    data = filehandle_data + unicode_str_data + object_attributes_data + status_block_data
    
    print(f"NtOpenFile(FileHandle={hex(scratchpad)}, DesiredAccess={hex(desired_access)}, Name={name})")
    return data, shellcode

def openFile(agent_id, name, desired_access):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    
    # Get the raw data and syscall shellcode
    data, shellcode = NtOpenFile(agent_id, name, desired_access)
    
    # 1. Write the pointers and data structures to the agent's memory
    write_scratchpad(agent_id, data)
    
    # 2. Command the agent to execute the syscall shellcode
    response_ntstatus = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')
    
    # 3. Read back the handle from the first 8 bytes of the scratchpad
    # Handles are 4 bytes, but on x64 they're often stored in 8-byte slots.
    scratchpad_val = read_scratchpad(agent_id, 8)
    file_handle = int.from_bytes(scratchpad_val[:8], 'little')
    
    print(f"NTSTATUS: {hex(response_ntstatus)}, hFile: {hex(file_handle)}")
    return response_ntstatus, file_handle

def function(agent_id, args, dependencies=[]):
    # args: [file_name, (optional) desired_access]
    name = args[0]
    # If the user provides a second arg, use it as access, else default.
    access = args[1]
    
    ntstatus, file_handle = openFile(agent_id, name, access)
    return {"NTSTATUS": ntstatus, "FILE_HANDLE": file_handle}