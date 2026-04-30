NAME = "StartServiceA"
DESCRIPTION = "Starts a service that is currently in the stopped state."
PARAMS = [
    {"name": "h_service", "description": "Handle to the service (from OpenServiceW)", "type": "hex"}
]
DEPENDENCIES = []
DEFAULT = True

def StartServiceA_Payload(agent_id, h_service):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl
    
    agent = Agent.by_id(agent_id)
    func_addr = Syscall.sys(agent.id, "StartServiceA")
    
    # Signature:
    # BOOL StartServiceA(
    #   SC_HANDLE hService,
    #   DWORD     dwNumServiceArgs,
    #   LPCSTR    *lpServiceArgVectors
    # );
    
    params = [
        h_service, # hService
        0,         # dwNumServiceArgs (0 for no arguments)
        0          # lpServiceArgVectors (NULL proxy)
    ]
    
    shellcode = push_rtl(func_addr, params, agent.debug)
    return b"", shellcode

def function(agent_id, args):
    from services.orders import send_and_wait
    
    h_service = args[0]
    data, shellcode = StartServiceA_Payload(agent_id, h_service)
    
    response = send_and_wait(agent_id, shellcode)
    success = int.from_bytes(response, 'little')

    return {
        "retval": 0 if success != 0 else -1,
        "status": "Success" if success != 0 else "Failure"
    }