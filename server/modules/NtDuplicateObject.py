NAME = "NtDuplicateObject"
DESCRIPTION = "Duplicate a handle from a source process into a target process via native syscall."
PARAMS = [
    {"name":"source_process_handle", "description":"Handle to the process owning the handle", "type":"hex"},
    {"name":"source_handle", "description":"The handle value to duplicate", "type":"hex"},
    {"name":"target_process_handle", "description":"Handle to the process that will receive the new handle (-1 for current)", "type":"hex"},
    {"name":"desired_access", "description":"Access mask for new handle (0 for same as original)", "type":"hex"},
    {"name":"options", "description":"DUPLICATE_SAME_ACCESS (2) or DUPLICATE_CLOSE_SOURCE (1)", "type":"int"}
]
DEFAULT = True

def NtDuplicateObject_Shellcode(agent_id, src_proc, src_handle, tgt_proc, access, options):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall_id = Syscall.sys(agent_id, "NtDuplicateObject")
    scratchpad = agent.scratchpad
    
    # Syscall Parameters (NTDLL Standard):
    # 1. HANDLE SourceProcessHandle
    # 2. HANDLE SourceHandle
    # 3. HANDLE TargetProcessHandle
    # 4. PHANDLE TargetHandle (Pointer to where the new handle value is written)
    # 5. ACCESS_MASK DesiredAccess
    # 6. ULONG HandleAttributes
    # 7. ULONG Options
    
    params = [
        src_proc,            # SourceProcessHandle
        src_handle,          # SourceHandle
        tgt_proc,            # TargetProcessHandle
        scratchpad,          # &TargetHandle (Write new handle into scratchpad)
        access,              # DesiredAccess
        0,                   # HandleAttributes
        options              # Options (e.g., 2 for DUPLICATE_SAME_ACCESS)
    ]
    
    shellcode = push_syscall(syscall_id, params, agent.debug)
    return shellcode

def function(agent_id, args):
    from services.orders import send_and_wait, read_scratchpad
    import struct

    # 1. Trigger syscall
    shellcode = NtDuplicateObject_Shellcode(agent_id, args[0], args[1], args[2], args[3], args[4])
    response = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response, 'little')
    
    # 2. Read the new handle value from the scratchpad
    new_handle_raw = read_scratchpad(agent_id, 8)
    new_handle = 0
    if ntstatus == 0:
        new_handle = struct.unpack("<Q", new_handle_raw)[0]

    return {
        "retval": ntstatus,
        "new_handle": hex(new_handle)
    }