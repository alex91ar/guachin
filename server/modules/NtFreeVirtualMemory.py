NAME = "NtFreeVirtualMemory"
DESCRIPTION = "Deallocates a region of virtual memory in the target agent"
PARAMS = [
    {"name":"base_address", "description":"Address of the memory to free", "type":"hex"},
    {"name":"size", "description":"Size of the memory to free (0 for MEM_RELEASE)", "type":"int"},
]

def NtFreeVirtualMemory(agent_id, base_address, size=0):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtFreeVirtualMemory") # Using syscall 0x1E
    scratchpad = agent.scratchpad # Base address of our memory buffer

    # Set up pointers on the scratchpad
    # 1. &BaseAddress (8 bytes) - Input/Output! 
    # Must point to a variable containing the address we want to free.
    base_addr_data, region_size_ptr = build_ptr(scratchpad, int.to_bytes(base_address, 8, 'little'))
    
    # 2. &RegionSize (8 bytes) - Input/Output!
    # Must point to a variable containing the size.
    # Note: For MEM_RELEASE, the size must be set to 0.
    region_size_data, next_ptr = build_ptr(region_size_ptr, int.to_bytes(size, 8, 'little'))
    
    # Define our FreeType
    FreeType = 0x8000 # MEM_RELEASE (Frees the entire allocation)

    # NtFreeVirtualMemory uses 4 parameters in x64 (all in registers)
    # R10, RDX, R8, R9
    params = [
        0xFFFFFFFFFFFFFFFF, # P1: R10 (ProcessHandle = -1 for current)
        scratchpad,         # P2: RDX (&BaseAddress)
        region_size_ptr,    # P3: R8  (&RegionSize)
        FreeType            # P4: R9  (FreeType)
    ]

    # Generate the x64 shellcode for the syscall
    shellcode = push_syscall(syscall, params, agent.debug)
    
    # Combine the data chunks to be written to the agent's scratchpad memory
    data = base_addr_data + region_size_data
    
    print(f"NtFreeVirtualMemory(Handle=-1, pAddr={hex(scratchpad)}, pSize={hex(region_size_ptr)}, FreeType={hex(FreeType)})")
    return data, shellcode

def freeMemory(agent_id, base_address, size):
    from services.orders import write_scratchpad, send_and_wait
    
    # 1. Generate the raw data and syscall shellcode
    data, shellcode = NtFreeVirtualMemory(agent_id, base_address, size)
    
    # 2. Write the pointer structures to the agent's memory
    write_scratchpad(agent_id, data)
    
    # 3. Command the agent to execute the syscall shellcode
    response_retval = int.from_bytes(send_and_wait(agent_id, shellcode), 'little')
    
    print(f"retval for NtFreeVirtualMemory: {hex(response_retval)}")
    return response_retval

def function(agent_id, args):
    # args: [base_address, (optional) size]
    base_address = args[0]
    size = args[1] if len(args) > 1 else 0
    
    retval = freeMemory(agent_id, base_address, size)
    return {"retval": retval}