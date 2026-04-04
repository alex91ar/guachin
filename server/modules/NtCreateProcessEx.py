NAME = "NtCreateProcessEx"
DESCRIPTION = "Create a process object from a section handle using Native API"
PARAMS = [
    {"name":"section_handle", "description":"Handle to the image section", "type":"hex"},
    {"name":"parent_process", "description":"Handle to parent process (usually -1 for current)", "type":"hex"}
]

def NtCreateProcessEx(agent_id, section_handle, parent_handle=0xFFFFFFFFFFFFFFFF):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, build_object_attributes, push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtCreateProcessEx")
    scratchpad = agent.scratchpad
    
    # 1. Prepare buffer for the new Process Handle
    process_handle_data, obj_attr_ptr = build_ptr(scratchpad, b"\x00"*8)
    
    # 2. Object Attributes (NULL for default)
    # We use build_ptr to represent a NULL pointer for ObjectAttributes if we don't need a name
    obj_attr_data = b"" 
    obj_attr_ptr = 0 # NULL
    
    params = [
        scratchpad,          # &ProcessHandle
        0x001F0FFF,          # DesiredAccess (PROCESS_ALL_ACCESS)
        obj_attr_ptr,        # ObjectAttributes (NULL)
        parent_handle,       # ParentProcess
        0x00000001,          # Flags (PROCESS_CREATE_FLAGS_INHERIT_HANDLES)
        section_handle,      # SectionHandle
        0,                   # DebugPort (NULL)
        0,                   # ExceptionPort (NULL)
        0                    # InJob (False)
    ]
    
    shellcode = push_syscall(syscall, params, agent.debug)
    # We only need to write the placeholder for the process handle
    return process_handle_data, shellcode

def createNativeProcess(agent_id, section_handle):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    
    data, shellcode = NtCreateProcessEx(agent_id, section_handle)
    write_scratchpad(agent_id, data)
    
    # Execute NtCreateProcessEx
    response_bytes = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response_bytes, 'little')
    
    # Read the handle written to scratchpad
    scratch_data = read_scratchpad(agent_id, 8)
    process_handle = int.from_bytes(scratch_data[:8], 'little')
    
    return ntstatus, process_handle