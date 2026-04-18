NAME = "OpenThread"
DESCRIPTION = "Open a handle to a thread by thread id using kernel32!OpenThread"
PARAMS = [
    {"name": "thread_id", "description": "Target Thread ID", "type": "hex"},
    {"name": "dwDesiredAccess", "description": "Access flags", "type": "hex", "optional": True, "default": "0x1FFFFF"},
]
DEPENDENCIES = []
DEFAULT = True

def OpenThread_Payload(agent_id, thread_id, dwDesiredAccess):
    """
    Generates the shellcode to call OpenProcess.
    Signature: HANDLE OpenProcess(DWORD dwDesiredAccess, BOOL bInheritHandle, DWORD dwProcessId);
    """
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl
    
    agent = Agent.by_id(agent_id)
    # Resolve kernel32!OpenProcess through your syscall/export resolver
    func_addr = Syscall.sys(agent.id, "OpenThread")
    
    # x64 Calling Convention: RCX, RDX, R8
    params = [
        dwDesiredAccess, # RCX: dwDesiredAccess (e.g., PROCESS_ALL_ACCESS)
        0,               # RDX: bInheritHandle (False)
        thread_id              # R8:  dwProcessId
    ]
    
    # Generate the shellcode to adjust stack and call the function address
    shellcode = push_rtl(func_addr, params, agent.debug)
    
    return shellcode

def open_thread_internal(agent_id, thread_id, dwDesiredAccess):
    """
    Handles the communication with the agent to execute the OpenProcess call.
    """
    from services.orders import send_and_wait
    
    # 1. Generate the shellcode
    shellcode = OpenThread_Payload(agent_id, thread_id, dwDesiredAccess)
    
    # 2. Send shellcode to agent and wait for the Return Value (RAX)
    # The return value is the HANDLE (64-bit address/pointer size)
    response_bytes = send_and_wait(agent_id, shellcode)
    h_process = int.from_bytes(response_bytes, 'little')
    
    return h_process

def function(agent_id, args):
    """
    Entry point for the tool defined in the framework.
    """
    # Parse arguments
    thread_id = args[0]
    # Decode hex string for access rights (Default: PROCESS_ALL_ACCESS)
    access_str = args[1] if len(args) > 1 else "0x1FFFFF"
    if type(access_str) != int:
        dwDesiredAccess = int(access_str, 16)
    else:
        dwDesiredAccess = access_str
    
    # Execute the logical flow
    h_thread = open_thread_internal(agent_id, thread_id, dwDesiredAccess)
    
    if h_thread != 0:
        return {
            "success": 0,
            "h_thread": hex(h_thread),
        }

    return {
        "success": -1,
        "access_requested": hex(dwDesiredAccess)
    }