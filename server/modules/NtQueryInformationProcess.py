NAME = "NtQueryInformationProcess"
DESCRIPTION = "Enumerate process metadata (PEB address, ExitStatus, etc.) via native syscall"
PARAMS = [
    {"name":"process_handle", "description":"Handle to the target process", "type":"hex"},
    {"name":"info_class", "description":"ProcessInformationClass (0 for BasicInformation)", "type":"int"},
    {"name":"buffer_size", "description":"Size of the structure to return (e.g., 48 for BasicInfo on x64)", "type":"int"}
]
DEFAULT = True

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
    
    #printf"[*] NtQueryInformationProcess(Handle={hex(process_handle)}, Class={info_class}, BufSize={buffer_size})")
    
    shellcode = push_syscall(syscall_id, params, agent.debug)
    return query_buffer_data, shellcode

def function(agent_id, args):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    import struct

    process_handle = int(args[0], 0) if isinstance(args[0], str) else args[0]
    info_class = int(args[1], 0) if isinstance(args[1], str) else args[1]
    buffer_size = int(args[2], 0) if isinstance(args[2], str) else args[2]

    data, shellcode = NtQueryInformationProcess_Shellcode(
        agent_id,
        process_handle,
        info_class,
        buffer_size
    )

    write_scratchpad(agent_id, data)

    response = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response, "little", signed=False)

    result_content = read_scratchpad(agent_id, buffer_size)

    parsed = {}

    # ProcessBasicInformation = 0
    #
    # x64 PROCESS_BASIC_INFORMATION:
    # NTSTATUS ExitStatus;              4
    # padding                           4
    # PPEB PebBaseAddress;              8
    # ULONG_PTR AffinityMask;           8
    # KPRIORITY BasePriority;           4
    # padding                           4
    # ULONG_PTR UniqueProcessId;        8
    # ULONG_PTR InheritedFromUniqueProcessId; 8
    #
    # Total: 48 bytes
    print(result_content)
    if ntstatus == 0 and info_class == 0 and len(result_content) >= 48:
        exit_status = struct.unpack_from("<i", result_content, 0)[0]
        peb_base = struct.unpack_from("<Q", result_content, 8)[0]
        affinity_mask = struct.unpack_from("<Q", result_content, 16)[0]
        base_priority = struct.unpack_from("<i", result_content, 24)[0]
        unique_process_id = struct.unpack_from("<Q", result_content, 32)[0]
        inherited_from_pid = struct.unpack_from("<Q", result_content, 40)[0]

        parsed = {
            "info_class": "ProcessBasicInformation",
            "exit_status": exit_status,
            "peb_base": peb_base,
            "peb_base_hex": f"0x{peb_base:x}",
            "affinity_mask": affinity_mask,
            "affinity_mask_hex": f"0x{affinity_mask:x}",
            "base_priority": base_priority,
            "unique_process_id": unique_process_id,
            "unique_process_id_hex": f"0x{unique_process_id:x}",
            "inherited_from_unique_process_id": inherited_from_pid,
            "inherited_from_unique_process_id_hex": f"0x{inherited_from_pid:x}",
        }

    return {
        "retval": ntstatus,
        "retval_hex": f"0x{ntstatus:x}",
        "parsed": parsed
    }