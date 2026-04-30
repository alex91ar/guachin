NAME = "OpenSCManagerW"
DESCRIPTION = "Establishes a connection to the service control manager on the specified computer."
PARAMS = [
    {"name": "machine_name", "description": "Name of the target computer (NULL for local)", "type": "str", "optional": True, "default": ""},
    {"name": "database_name", "description": "Name of the SCM database (NULL for default)", "type": "str", "optional": True, "default": ""},
    {"name": "desired_access", "description": "Access mask (e.g., 0xF003F for AllAccess, 0x4 for Enumerate)", "type": "hex", "optional": True, "default": "0x4"}
]
DEPENDENCIES = []
DEFAULT = True

def OpenSCManagerW_Payload(agent_id, machine_name, database_name, desired_access):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_rtl, build_ptr
    
    agent = Agent.by_id(agent_id)
    # Resolve advapi32!OpenSCManagerW
    func_addr = Syscall.sys(agent.id, "OpenSCManagerW")
    scratchpad = agent.scratchpad
    
    # 1. Handle String Parameters
    # If strings are provided, we store them in the scratchpad. 
    # For local/default, we pass NULL pointers (0).
    data = b""
    lpMachineName = 0
    lpDatabaseName = 0
    current_ptr = scratchpad + 8 # Leave first 8 bytes for returning the handle

    if machine_name:
        lpMachineName = current_ptr
        str_bytes = machine_name.encode('utf-16le') + b'\x00\x00'
        str_data, current_ptr = build_ptr(current_ptr, str_bytes)
        data += str_data

    if database_name:
        lpDatabaseName = current_ptr
        str_bytes = database_name.encode('utf-16le') + b'\x00\x00'
        str_data, current_ptr = build_ptr(current_ptr, str_bytes)
        data += str_data

    # Signature:
    # SC_HANDLE OpenSCManagerW(
    #   LPCWSTR lpMachineName,
    #   LPCWSTR lpDatabaseName,
    #   DWORD   dwDesiredAccess
    # );
    
    params = [
        lpMachineName,   # lpMachineName
        lpDatabaseName,  # lpDatabaseName
        desired_access   # dwDesiredAccess
    ]
    
    shellcode = push_rtl(func_addr, params, agent.debug)
    return data, shellcode

def function(agent_id, args):
    from services.orders import send_and_wait, write_scratchpad
    import struct

    # 1. Parse Arguments
    machine = args[0]
    database = args[1]
    access = args[2]
    # 2. Generate and Execute
    data, shellcode = OpenSCManagerW_Payload(agent_id, machine, database, access)
    
    if data:
        write_scratchpad(agent_id, data)
    
    response_bytes = send_and_wait(agent_id, shellcode)
    h_scm = int.from_bytes(response_bytes, 'little')

    if h_scm == 0:
        return {
            "retval": -1, 
            "message": "OpenSCManagerW failed. Check permissions (often requires Admin for AllAccess)."
        }

    return {
        "retval": 0,
        "handle": hex(h_scm),
        "params": {
            "machine": machine if machine else "local",
            "access": hex(access)
        }
    }