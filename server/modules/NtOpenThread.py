NAME = "NtOpenThread"
DESCRIPTION = "Opens the access token associated with a process for privilege manipulation or duplication."
PARAMS = [
    {"name": "h_process", "description": "Handle to the process", "type": "hex"},
    {"name": "h_thread", "description": "Handle to the thread", "type": "hex"},
    {"name": "dwDesiredAccess", "description": "Token access flags (e.g., 0x28 for Adjust/Query)", "type": "hex", "optional": True, "default": "0x1FFFFF"},
]
DEPENDENCIES = []
DEFAULT = True

def NtOpenThread_Payload(agent_id, h_process, h_thread, dwDesiredAccess):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_syscall, build_ptr, build_object_attributes
    
    agent = Agent.by_id(agent_id)
    scratchpad = agent.scratchpad
    token_data, client_ptr = build_object_attributes(scratchpad, "", 0)
    client_data, next_ptr = build_ptr(client_ptr, int.to_bytes(h_process, 8, 'little') + int.to_bytes(h_thread, 8, 'little'))

    func_addr = Syscall.sys(agent.id, "NtOpenThread")
    
    # Signature: BOOL OpenProcessToken(HANDLE ProcessHandle, DWORD DesiredAccess, PHANDLE TokenHandle);
    params = [
        h_thread,       # RCX: ProcessHandle
        dwDesiredAccess, # RDX: DesiredAccess
        scratchpad,     # R8:  TokenHandle (Pointer where the output handle will be written)
        client_ptr
    ]
    
    return token_data + client_data, push_syscall(func_addr, params, agent.debug)

def function(agent_id, args):
    from services.orders import send_and_wait, read_scratchpad, write_scratchpad
    import struct

    # 1. Parse Arguments
    h_process = args[0]
    h_thread = args[1]
    access_str = args[2] if len(args) > 1 else "0x1FFFFF"
    dwDesiredAccess = access_str

    # 3. Generate and Execute Shellcode
    data, shellcode = NtOpenThread_Payload(agent_id, h_process,h_thread, dwDesiredAccess)
    write_scratchpad(agent_id, data)
    response_bytes = send_and_wait(agent_id, shellcode)
    
    # BOOL return: 1 is success, 0 is failure
    success_val = int.from_bytes(response_bytes, 'little')

    h_token = 0
    if success_val == 0:
        # 4. Read the 64-bit handle written to our allocated memory
        token_raw = read_scratchpad(agent_id, 8)
        h_token = int.from_bytes(token_raw, 'little')

    # 5. Cleanup

    if success_val != 0:
        return {
            "retval": -1, 
            "error": "NtOpenThread returned FALSE. check handle permissions."
        }

    return {
        "retval": 0,
        "h_token": hex(h_token),
        "h_process": hex(h_process),
        "access": hex(dwDesiredAccess)
    }