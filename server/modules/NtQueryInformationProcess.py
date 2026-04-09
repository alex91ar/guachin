NAME = "NtQueryInformationProcess"
DESCRIPTION = "Enumerate process metadata (PEB address, ExitStatus, etc.) via native syscall"
PARAMS = [
    {"name":"process_handle", "description":"Handle to the target process", "type":"hex"},
    {"name":"info_class", "description":"ProcessInformationClass (0 for BasicInformation)", "type":"int"},
    {"name":"buffer_size", "description":"Size of the structure to return (e.g., 48 for BasicInfo on x64)", "type":"int"}
]

def NtQueryInformationProcess_Shellcode(agent_id, process_handle, info_class, buffer_size):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall_id = Syscall.sys(agent_id, "NtQueryInformationProcess")
    scratchpad = agent.scratchpad
    
    # 1. Prepare buffer in scratchpad for the return data structure
    # For ProcessBasicInformation (Class 0), the struct size is 48 bytes on x64
    query_buffer_data, next_ptr = build_ptr(scratchpad, b"\x00" * buffer_size)
    
    # Syscall Parameters (NTDLL Standard):
    # 1. HANDLE ProcessHandle
    # 2. PROCESSINFOCLASS ProcessInformationClass
    # 3. PVOID ProcessInformation (Pointer to our buffer in scratchpad)
    # 4. ULONG ProcessInformationLength
    # 5. PULONG ReturnLength (Optional NULL = 0)
    
    params = [
        process_handle,      # ProcessHandle
        info_class,          # ProcessInformationClass
        scratchpad,          # &ProcessInformation (Buffer starts at beginning of scratchpad)
        buffer_size,         # ProcessInformationLength
        0                    # ReturnLength (NULL)
    ]
    
    print(f"[*] NtQueryInformationProcess(Handle={hex(process_handle)}, Class={info_class}, BufSize={buffer_size})")
    
    shellcode = push_syscall(syscall_id, params, agent.debug)
    return query_buffer_data, shellcode

def function(agent_id, args):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    import struct

    process_handle = args[0]
    info_class = args[1]
    buffer_size = args[2]

    data, shellcode = NtQueryInformationProcess_Shellcode(agent_id, process_handle, info_class, buffer_size)
    
    # 1. Prepare scratchpad with null bytes to receive the structure
    write_scratchpad(agent_id, data)
    
    # 2. Trigger the syscall execution
    response = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response, 'little')
    
    # 3. Read the returned structure from the scratchpad
    result_content = read_scratchpad(agent_id, buffer_size)
    print(result_content)
    # Optional: Manual parsing logic if class is ProcessBasicInformation (0)
    # Struct: [ExitStatus(4)][PEB_Base(8)][Affinity(8)][Priority(8)][PID(8)][InheritedPID(8)]
    peb_base = 0
    if ntstatus == 0 and info_class == 0 and len(result_content) >= 16:
        peb_base = struct.unpack_from("<Q", result_content, 8)[0]
    return {
        "retval": ntstatus, 
        "peb_base": peb_base,
        "raw_buffer": result_content.hex()
    }