NAME = "NtCreateSection"
DESCRIPTION = "Create a section object for a file (mapped as SEC_IMAGE for execution)"
PARAMS = [
    {"name":"file_handle", "description":"Handle to the executable file", "type":"hex"},
    {"name":"desired_access", "description":"Access mask (e.g., 0xF001F - SECTION_ALL_ACCESS)", "type":"hex"}
]

def NtCreateSection_Shellcode(agent_id, file_handle, desired_access):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall_id = Syscall.sys(agent_id, "NtCreateSection")
    scratchpad = agent.scratchpad
    
    # 1. Prepare buffer in scratchpad for the new Section Handle (8 bytes)
    section_handle_data, next_ptr = build_ptr(scratchpad, b"\x00"*8)
    
    # Syscall Parameters:
    # 1. PHANDLE SectionHandle (where handle is returned)
    # 2. ACCESS_MASK DesiredAccess (SECTION_ALL_ACCESS = 0xF001F)
    # 3. POBJECT_ATTRIBUTES ObjectAttributes (NULL = 0)
    # 4. PLARGE_INTEGER MaximumSize (0 for entire file)
    # 5. ULONG SectionPageProtection (PAGE_READONLY = 0x02, kernel handles mapping for SEC_IMAGE)
    # 6. ULONG AllocationAttributes (SEC_IMAGE = 0x01000000)
    # 7. HANDLE FileHandle
    
    params = [
        scratchpad,          # &SectionHandle
        desired_access,      # DesiredAccess
        0,                   # ObjectAttributes
        0,                   # MaximumSize (NULL)
        0x02,                # SectionPageProtection (PAGE_READONLY)
        0x01000000,          # AllocationAttributes (SEC_IMAGE)
        file_handle          # FileHandle from NtOpenFile
    ]
    
    shellcode = push_syscall(syscall_id, params, agent.debug)
    return section_handle_data, shellcode

def function(agent_id, args):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    file_handle = args[0]
    desired_access = args[1]
    data, shellcode = NtCreateSection_Shellcode(agent_id, file_handle, desired_access)
    
    # 1. Prepare scratchpad with handle placeholder
    write_scratchpad(agent_id, data)
    
    # 2. Trigger syscall
    response = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response, 'little')
    print(f"NtCreateSection ntstatus = {ntstatus}. ")
    # 3. Read the resulting Section Handle
    h_data = read_scratchpad(agent_id, 4)
    section_handle = int.from_bytes(h_data, 'little')
    print(f"NtCreateSection section_handle = {section_handle}. ")
        
    return {"retval": ntstatus, "section_handle": section_handle}