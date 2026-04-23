NAME = "NtQueryObject"
DESCRIPTION = "Retrieve information about a specific handle (Name, Type, Access) via native syscall"
PARAMS = [
    {"name":"handle", "description":"The handle to query", "type":"hex"},
    {"name":"info_class", "description":"ObjectInformationClass (1 for Name, 2 for Type)", "type":"int"}
]
DEFAULT = True

def NtQueryObject_Shellcode(agent_id, handle, info_class):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall_id = Syscall.sys(agent_id, "NtQueryObject")
    scratchpad = agent.scratchpad
    
    # 1. Prepare buffer in scratchpad
    # ObjectNameInformation can be long (MAX_PATH+), 1024 bytes is usually safe.
    buffer_size = 1024
    
    # Syscall Parameters (NTDLL Standard):
    # 1. HANDLE Handle
    # 2. OBJECT_INFORMATION_CLASS ObjectInformationClass
    # 3. PVOID ObjectInformation (Pointer to our buffer in scratchpad)
    # 4. ULONG ObjectInformationLength
    # 5. PULONG ReturnLength (Optional NULL = 0)
    
    params = [
        handle,              # Handle
        info_class,          # ObjectInformationClass
        scratchpad,          # &ObjectInformation
        buffer_size,         # ObjectInformationLength
        0                    # ReturnLength (NULL)
    ]
    
    shellcode = push_syscall(syscall_id, params, agent.debug)
    return shellcode

def function(agent_id, args):
    from models.agent import Agent
    from services.orders import send_and_wait, read_scratchpad
    import struct
    scratchpad = Agent.by_id(agent_id).scratchpad
    handle = args[0]
    info_class = args[1]
    
    # Define a default buffer size to read back
    buffer_size = 1024
    
    shellcode = NtQueryObject_Shellcode(agent_id, handle, info_class)
    
    # 1. Trigger the syscall execution
    response = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response, 'little')
    
    # 2. Read the results from scratchpad
    result_content = read_scratchpad(agent_id, buffer_size)
    
    # Parsing logic for ObjectNameInformation (Class 1) or ObjectTypeInformation (Class 2)
    # Both return a UNICODE_STRING structure first: [Length(2)][MaxLen(2)][Padding(4)][BufferPtr(8)]
    # On x64, the BufferPtr points to the strings immediately following in the scratchpad.
    name_str = ""
    if ntstatus == 0 and len(result_content) >= 16:
        # UNICODE_STRING header is 16 bytes on x64
        u_len = struct.unpack_from("<H", result_content, 0)[0]
        # The string content starts immediately after the header at offset 16 in our scratchpad
        # because the ntdll writes the whole structure and its buffer starting at &scratchpad
        offset = int.from_bytes(result_content[8:16], 'little') - scratchpad
        name_str = result_content[offset:offset+u_len].decode('utf-16le', errors='ignore')
    return {
        "retval": ntstatus,
        "object_info": name_str,
        "raw_buffer": result_content.hex()
    }