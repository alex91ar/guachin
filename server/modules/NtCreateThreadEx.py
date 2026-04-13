NAME = "NtCreateThreadEx"
DESCRIPTION = "Directly create a thread in a local or remote process via native syscall"
PARAMS = [
    {"name":"process_handle", "description":"Handle to the target process", "type":"hex"},
    {"name":"start_address", "description":"EntryPoint or memory location to start execution", "type":"hex"},
    {"name":"argument", "description":"Optional parameter to pass to the thread (NULL = 0)", "type":"hex"}
]
DEFAULT = True

def NtCreateThreadEx_Shellcode(agent_id, process_handle, start_address, argument):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall_id = Syscall.sys(agent_id, "NtCreateThreadEx")
    scratchpad = agent.scratchpad
    
    # 1. Prepare buffer in scratchpad for the new Thread Handle (8 bytes)
    thread_handle_data, next_ptr = build_ptr(scratchpad, b"\x00"*8)
    
    # Syscall Parameters (NTDLL Standard):
    # 1. PHANDLE ThreadHandle (Returns the handle here)
    # 2. ACCESS_MASK DesiredAccess (THREAD_ALL_ACCESS = 0x1FFFFF)
    # 3. POBJECT_ATTRIBUTES ObjectAttributes (NULL = 0)
    # 4. HANDLE ProcessHandle (Target Process)
    # 5. PVOID StartRoutine (Address where execution starts)
    # 6. PVOID Argument (Passed as RCX on x64)
    # 7. ULONG CreateFlags (0 = Start immediately)
    # 8. SIZE_T ZeroBits (0)
    # 9. SIZE_T StackSize (0 = OS Default)
    # 10. SIZE_T MaxStackSize (0 = OS Default)
    # 11. PVOID AttributeList (NULL = 0)
    
    params = [
        scratchpad,          # &ThreadHandle
        0x001FFFFF,          # DesiredAccess
        0,                   # ObjectAttributes
        process_handle,      # ProcessHandle
        start_address,       # StartRoutine
        argument,            # Argument
        0,                   # CreateFlags
        0,                   # ZeroBits
        0,                   # StackSize
        0,                   # MaxStackSize
        0                    # AttributeList
    ]
    
    #printf"[*] NtCreateThreadEx(ProcessHandle={hex(process_handle)}, StartAddress={hex(start_address)}, Arg={hex(argument)})")
    
    shellcode = push_syscall(syscall_id, params, agent.debug)
    return thread_handle_data, shellcode

def function(agent_id, args):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    
    process_handle = args[0]
    start_address = args[1]
    argument = args[2] if len(args) > 2 else 0
    
    # Using the get_session context for any DB-specific operations if needed
    data, shellcode = NtCreateThreadEx_Shellcode(agent_id, process_handle, start_address, argument)
    
    # 1. Prepare scratchpad with handle placeholder for the response
    write_scratchpad(agent_id, data)
    
    # 2. Trigger the syscall execution
    response = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response, 'little')
    
    # 3. Read the resulting Thread Handle from the scratchpad
    h_data = read_scratchpad(agent_id, 8)
    thread_handle = int.from_bytes(h_data, 'little')
        
    return {
        "retval": ntstatus, 
        "thread_handle": thread_handle
    }