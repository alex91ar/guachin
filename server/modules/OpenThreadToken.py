NAME = "OpenThreadToken"
DESCRIPTION = "Open a handle to a thread by thread id using kernel32!OpenThread"
PARAMS = [
    {"name": "thread_id", "description": "Target Thread ID", "type": "hex"},
    {"name": "dwDesiredAccess", "description": "Access flags", "type": "hex", "optional": True, "default": "0x1FFFFF"},
]
DEPENDENCIES = []
DEFAULT = True

def OpenThreadToken_Payload(agent_id, thread_id, dwDesiredAccess):
    """
    Generates the shellcode to call OpenThreadToken.
    Signature: HANDLE OpenProcess(DWORD dwDesiredAccess, BOOL bInheritHandle, DWORD dwProcessId);
    """
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr
    
    agent = Agent.by_id(agent_id)
    scratchpad = agent.scratchpad
    # Resolve kernel32!OpenProcess through your syscall/export resolver
    func_addr = Syscall.sys(agent.id, "OpenThreadToken")
    thread_data, next_ptr = build_ptr(scratchpad, b"\x00"*8)
    
    # x64 Calling Convention: RCX, RDX, R8
    params = [
        thread_id, # RCX: dwDesiredAccess (e.g., PROCESS_ALL_ACCESS)
        dwDesiredAccess,               # RDX: bInheritHandle (False)
        0,              # R8:  dwProcessId
        scratchpad
    ]
    
    # Generate the shellcode to adjust stack and call the function address
    shellcode = push_rtl(func_addr, params, agent.debug)
    
    return thread_data, shellcode

def open_threadToken_internal(agent_id, thread_id, dwDesiredAccess):
    """
    Handles the communication with the agent to execute the OpenProcess call.
    """
    from services.orders import send_and_wait, read_scratchpad, write_scratchpad
    
    # 1. Generate the shellcode
    thread_data, shellcode = OpenThreadToken_Payload(agent_id, thread_id, dwDesiredAccess)
    
    # 2. Send shellcode to agent and w  ait for the Return Value (RAX)
    # The return value is the HANDLE (64-bit address/pointer size)
    write_scratchpad(agent_id, thread_data)
    response_bytes = send_and_wait(agent_id, shellcode)

    ret = int.from_bytes(response_bytes, 'little')
    h_thread = int.from_bytes(read_scratchpad(agent_id, 8), 'little')
    
    return ret, h_thread

def function(agent_id, args):
    """
    Entry point for the tool defined in the framework.
    """
    # Parse arguments
    thread_id = args[0]
    # Decode hex string for access rights (Default: PROCESS_ALL_ACCESS)
    access_str = args[1] if len(args) > 1 else "0x1FFFFF"

    
    # Execute the logical flow
    ret, h_thread = open_threadToken_internal(agent_id, thread_id, access_str)
    
    if ret != 0:
        return {
            "retval": 0,
            "token": hex(h_thread),
        }

    return {
        "retval": -1,
        "access_requested": hex(access_str)
    }