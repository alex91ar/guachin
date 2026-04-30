NAME = "OpenServiceW"
DESCRIPTION = "Opens an existing service to obtain a handle for manipulation."
PARAMS = [
    {"name": "h_scm", "description": "Handle to SCM (from OpenSCManagerW)", "type": "hex"},
    {"name": "service_name", "description": "Name of the service to open", "type": "str"},
    {"name": "desired_access", "description": "Access mask (e.g., 0x10 for Start, 0x20 for Stop, 0xF01FF for AllAccess)", "type": "hex", "optional": True, "default": "0xF01FF"}
]
DEPENDENCIES = []
DEFAULT = True

def OpenServiceW_Payload(agent_id, h_scm, service_name, desired_access):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr
    
    agent = Agent.by_id(agent_id)
    func_addr = Syscall.sys(agent.id, "OpenServiceW")
    scratchpad = agent.scratchpad
    
    # Encode service name as UTF-16
    name_bytes = service_name.encode('utf-16le') + b'\x00\x00'
    name_data, next_ptr = build_ptr(scratchpad, name_bytes)

    # Signature:
    # SC_HANDLE OpenServiceW(
    #   SC_HANDLE hSCManager,
    #   LPCWSTR   lpServiceName,
    #   DWORD     dwDesiredAccess
    # );
    
    params = [
        h_scm,          # hSCManager
        scratchpad,     # lpServiceName (Pointer to our string in scratchpad)
        desired_access  # dwDesiredAccess
    ]
    
    shellcode = push_rtl(func_addr, params, agent.debug)
    return name_data, shellcode

def function(agent_id, args):
    from services.orders import send_and_wait, write_scratchpad
    
    h_scm = args[0]
    service_name = args[1]
    access = args[2]

    data, shellcode = OpenServiceW_Payload(agent_id, h_scm, service_name, access)
    write_scratchpad(agent_id, data)
    
    response = send_and_wait(agent_id, shellcode)
    h_service = int.from_bytes(response, 'little')

    if h_service == 0:
        return {"retval": -1, "message": "OpenServiceW failed. Service might not exist or insufficient permissions."}

    return {"retval": 0, "h_service": hex(h_service)}