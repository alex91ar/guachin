NAME = "CloseServiceHandle"
DESCRIPTION = "Closes a handle to a service control manager or a service object."
PARAMS = [
    {"name": "h_scm_or_service", "description": "The handle to close", "type": "hex"}
]

def function(agent_id, args):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl
    from services.orders import send_and_wait

    h_handle = args[0]
    agent = Agent.by_id(agent_id)
    
    # Resolve advapi32!CloseServiceHandle
    func_addr = Syscall.sys(agent.id, "CloseServiceHandle")
    
    params = [h_handle]
    shellcode = push_rtl(func_addr, params, agent.debug)
    
    response = send_and_wait(agent_id, shellcode)
    success = int.from_bytes(response, 'little')

    return {"retval": 0 if success != 0 else -1}