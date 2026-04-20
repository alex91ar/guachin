NAME = "OpenProcessToken"
DESCRIPTION = "Impersonates the security context of a logged-on user using a token handle."
PARAMS = [
    {"name":"hProcess", "description": "Handle to a process", "type":"hex"},
    {"name": "dwDesiredAccess", "description": "Access flags", "type": "hex", "optional": True, "default": "0x28"}
]
DEPENDENCIES = []
DEFAULT = True

def openprocesstoken(agent_id, h_process,desired_access):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr
    
    agent = Agent.by_id(agent_id)
    scratchpad = agent.scratchpad
    print(scratchpad)
    
    # Resolve advapi32!ImpersonateLoggedOnUser address
    # Ensure advapi32.dll is loaded by the agent before this call
    func_addr = Syscall.sys(agent.id, "OpenProcessToken")
    token_data, next_ptr = build_ptr(scratchpad, b"\x00"*8)
    
    # ImpersonateLoggedOnUser(HANDLE hToken)
    # x64 Calling Convention: hToken is passed in RCX
    params = [
        h_process,
        desired_access,
        scratchpad
    ]

    # Generate the library call shellcode using the RTL helper
    shellcode = push_rtl(func_addr, params, agent.debug)
    
    return token_data, shellcode

def OpenProcessToken_internal(agent_id, h_process,desired_access):
    from services.orders import send_and_wait, write_scratchpad, read_scratchpad
    
    # Generate the shellcode for the specific token handle
    data, shellcode = openprocesstoken(agent_id, h_process,desired_access)
    
    # Execute and retrieve the BOOL return value (nonzero = success)
    write_scratchpad(agent_id, data)
    response = send_and_wait(agent_id, shellcode)
    ret = read_scratchpad(agent_id, 8)
    ret = int.from_bytes(ret, 'little')
    ret_val = int.from_bytes(response, 'little')

    return {"retval": ret_val, "token":hex(ret)}

def function(agent_id, args):
    # 'args' should contain the 'hToken' integer value
    h_process = args[0]
    desired_access =args[1]
        
    result = OpenProcessToken_internal(agent_id, h_process,desired_access)
    return result