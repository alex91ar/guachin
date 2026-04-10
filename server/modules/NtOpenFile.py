NAME = "NtOpenFile"
DESCRIPTION = "Opens an existing file in the target agent"
PARAMS = [
    {"name":"filename", "description":"Complete path (e.g. \\??\\C:\\temp\\log.txt)", "type":"str"},
    {"name":"desired_access", "description":"Access level mask", "type":"hex"},
    {"name":"share_access", "description":"Share access mask", "type":"hex"},
    {"name":"open_options", "description":"Open options mask", "type":"hex"},
    {"name":"attributes", "description":"Attributes for the OBJECT_ATTRIBUTES struct", "type":"hex"}
]

def NtOpenFile(agent_id, name, desired_access, share, options, attributes): # Default GENERIC_READ | SYNCHRONIZE
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, build_object_attributes, push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtOpenFile") # Using syscall 0x33
    scratchpad = agent.scratchpad # Base address of our memory buffer

    # Set up pointers on the scratchpad
    # 1. &FileHandle (8 bytes)
    filehandle_data, object_attributes_ptr = build_ptr(scratchpad, b"\x00" * 8)
        
    # 2. &ObjectAttributes (48 bytes for struct)
    object_attributes_data, status_block_ptr = build_object_attributes(object_attributes_ptr, name, attributes)
    
    # 3. &IoStatusBlock (16 bytes)
    status_block_data, next_ptr = build_ptr(status_block_ptr, b"\x00" * 16)
    share_access = share
    open_options = options
    params = [
        scratchpad,              # P1: R10 (&FileHandle)
        desired_access,          # P2: RDX (Access Mask)
        object_attributes_ptr,   # P3: R8  (&ObjAttributes)
        status_block_ptr,        # P4: R9  (&IoStatusBlock)
        share_access,            # P5: [RSP+0x28] (ShareAccess)
        open_options             # P6: [RSP+0x30] (OpenOptions - Synchronous)
    ]

    # Generate the x64 shellcode for the syscall
    shellcode = push_syscall(syscall, params, agent.debug)
    
    # Combine the data chunks to be written to the agent's scratchpad memory
    data = filehandle_data + object_attributes_data + status_block_data
    # --- Helpers for decoding flags ---
    def decode_access(mask):
        flags = {
            0x80000000: "GENERIC_READ",
            0x40000000: "GENERIC_WRITE",
            0x20000000: "GENERIC_EXECUTE",
            0x10000000: "GENERIC_ALL",
            0x00010000: "DELETE",
            0x00100000: "SYNCHRONIZE",
        }
        return " | ".join(name for bit, name in flags.items() if mask & bit) or "0"

    def decode_share(mask):
        flags = {
            0x1: "FILE_SHARE_READ",
            0x2: "FILE_SHARE_WRITE",
            0x4: "FILE_SHARE_DELETE",
        }
        return " | ".join(name for bit, name in flags.items() if mask & bit) or "0"

    def decode_open(mask):
        flags = {
            0x20: "FILE_SYNCHRONOUS_IO_NONALERT",
            0x40: "FILE_SYNCHRONOUS_IO_ALERT",
            0x4000: "FILE_NON_DIRECTORY_FILE",
            0x0001: "FILE_DIRECTORY_FILE",
        }
        return " | ".join(name for bit, name in flags.items() if mask & bit) or "0"

    # --- Final debug print ---
    '''
    print(
        f"""
    NtOpenFile(
    FileHandle_ptr      = {hex(scratchpad)}
    DesiredAccess       = {hex(desired_access)} ({decode_access(desired_access)})
    ObjectAttributes    = {hex(object_attributes_ptr)}
        -> Name           = "{name}"
    IoStatusBlock_ptr   = {hex(status_block_ptr)}
    ShareAccess         = {hex(share_access)} ({decode_share(share_access)})
    OpenOptions         = {hex(open_options)} ({decode_open(open_options)})
    )
    """.strip()
        )
    '''
    return data, shellcode

def openFile(agent_id, name, desired_access, share, options, attributes):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    
    # Get the raw data and syscall shellcode
    data, shellcode = NtOpenFile(agent_id, name, desired_access, share, options, attributes)
    
    # 1. Write the pointers and data structures to the agent's memory
    write_scratchpad(agent_id, data)
    
    # 2. Command the agent to execute the syscall shellcode
    response_retval = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')
    
    # 3. Read back the handle from the first 8 bytes of the scratchpad
    # Handles are 4 bytes, but on x64 they're often stored in 8-byte slots.
    scratchpad_val = read_scratchpad(agent_id, 8)
    file_handle = int.from_bytes(scratchpad_val[:8], 'little')
    
    #print(f"retval: {hex(response_retval)}, hFile: {hex(file_handle)}")
    return response_retval, file_handle

def function(agent_id, args):
    # args: [file_name, (optional) desired_access]
    name = args[0]
    # If the user provides a second arg, use it as access, else default.
    access = args[1]
    share = args[2]
    options = args[3]
    attributes = args[4]
    
    retval, file_handle = openFile(agent_id, name, access, share, options, attributes)
    #print(f"NtOpenFile return values internally {retval} {type(retval)}, {file_handle} {type(file_handle)}")
    return {"retval": retval, "FILE_HANDLE": file_handle}