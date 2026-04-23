NAME = "NtOpenProcess"
DESCRIPTION = "Opens a handle to a process for manipulation, memory access, or property queries via native syscall."
PARAMS = [
    {"name": "pid", "description": "The Process ID (PID) to open", "type": "hex"},
    {"name": "desired_access", "description": "Access mask (e.g., 0x1FFFFF for AllAccess, 0x1000 for QueryLimited)", "type": "hex", "optional": True, "default": "0x1000"}
]
DEPENDENCIES = []
DEFAULT = True

def NtOpenProcess_Payload(agent_id, pid, desired_access):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_syscall, build_ptr, build_object_attributes
    
    agent = Agent.by_id(agent_id)
    scratchpad = agent.scratchpad
    
    # 1. Build OBJECT_ATTRIBUTES structure (Initializes to default/null)
    # The pointer where we store the handle will start at 'scratchpad' offset 0.
    print(scratchpad)
    process_handle_data, object_attribute_ptr = build_ptr(scratchpad, b"\x00"*8)
    
    obj_attr_data, client_id_ptr = build_object_attributes(object_attribute_ptr, "", 0)
    
    # 2. Build CLIENT_ID structure: [UniqueProcess(8)][UniqueThread(8)]
    # UniqueThread is usually 0 when opening a process by PID.
    client_id_data = int.to_bytes(pid, 8, 'little') + int.to_bytes(0, 8, 'little')
    print(client_id_ptr)
    client_data, next_ptr = build_ptr(client_id_ptr, client_id_data)

    syscall_id = Syscall.sys(agent.id, "NtOpenProcess")
    
    # Syscall Signature:
    # NTSTATUS NtOpenProcess(
    #   PHANDLE            ProcessHandle,
    #   ACCESS_MASK        DesiredAccess,
    #   POBJECT_ATTRIBUTES ObjectAttributes,
    #   PCLIENT_ID         ClientId
    # );
    
    params = [
        scratchpad,         # Output pointer for ProcessHandle
        desired_access,     # DesiredAccess
        object_attribute_ptr,       # Pointer to OBJECT_ATTRIBUTES
        client_id_ptr       # Pointer to CLIENT_ID
    ]
    
    # Return everything to be written to scratchpad and the shellcode
    # Headers/Structs are written starting at &scratchpad + 8 to keep offset 0 clear for the handle
    return process_handle_data + obj_attr_data + client_data, push_syscall(syscall_id, params, agent.debug)

def function(agent_id, args):
    from services.orders import send_and_wait, read_scratchpad, write_scratchpad
    import struct

    # 1. Parse Arguments
    pid = args[0]
    access = args[1]

    # 2. Generate and Execute Shellcode
    data, shellcode = NtOpenProcess_Payload(agent_id, pid, access)
    
    # Write the structures (OBJECT_ATTRIBUTES and CLIENT_ID) into scratchpad
    write_scratchpad(agent_id, data)
    
    # Execute the syscall
    response_bytes = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response_bytes, 'little')

    h_process = 0
    if ntstatus == 0:
        # Success: Read the 64-bit handle written to the beginning of the scratchpad
        handle_raw = read_scratchpad(agent_id, 8)
        h_process = int.from_bytes(handle_raw, 'little')

    return {
        "retval": hex(ntstatus),
        "handle": hex(h_process),
        "params": {
            "pid": hex(pid),
            "access": hex(access)
        }
    }