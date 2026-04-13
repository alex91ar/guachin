NAME = "NtCreateProcessEx"
DESCRIPTION = "Create a process object from a section handle using Native API"
PARAMS = [
    {"name":"section_handle", "description":"Handle to the image section", "type":"hex"},
    {"name":"flags", "description":"Flags", "type":"hex"},
]
DEFAULT = True

def NtCreateProcessEx(agent_id, section_handle, flags):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtCreateProcessEx")
    scratchpad = agent.scratchpad
    
    # 1. Prepare buffer for the new Process Handle
    process_handle_data, obj_attr_ptr = build_ptr(scratchpad, b"\x00"*8)
    
    
    params = [
        scratchpad,          # &ProcessHandle
        0x001F0FFF,          # DesiredAccess (PROCESS_ALL_ACCESS)
        0,        # ObjectAttributes (NULL)
        0xFFFFFFFFFFFFFFFF,          # ParentProcess
        flags,          # Flags (PROCESS_CREATE_FLAGS_INHERIT_HANDLES)
        section_handle,      # SectionHandle
        0,                   # DebugPort (NULL)
        0,                   # ExceptionPort (NULL)
        0                    # InJob (False)
    ]
    #printf"[*] NtCreateProcessEx(ProcessHandle={hex(scratchpad)}, Access=0x1F0FFF, ObjectAttributes=0, flags={hex(flags)}, Section={hex(section_handle)}, debug_port=0, exceptionport=0, injob=0)")
    shellcode = push_syscall(syscall, params, agent.debug)
    # We only need to write the placeholder for the process handle
    return process_handle_data, shellcode

def function(agent_id, args):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    section_handle = args[0]
    flags = args[1]
    #printf"Preparing NtCreateProcessEx {section_handle}")
    data, shellcode = NtCreateProcessEx(agent_id, section_handle, flags)
    write_scratchpad(agent_id, data)
    
    # Execute NtCreateProcessEx
    response_bytes = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response_bytes, 'little')
    
    # Read the handle written to scratchpad
    scratch_data = read_scratchpad(agent_id, 8)
    process_handle = int.from_bytes(scratch_data[:8], 'little')
    
    return {"retval": ntstatus, "process_handle": process_handle}