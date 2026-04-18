NAME = "NtSetInformationThread"
DESCRIPTION = "Set information for a thread"
PARAMS = [
    {"name":"thread_handle", "description":"Handle to the file", "type":"hex"},
    {"name":"info_class", "description":"FileInformationClass (e.g., 13 for Disposition/Delete)", "type":"hex"},
    {"name":"info_data", "description":"The buffer containing the info structure", "type":"hex"}
]
DEFAULT = True

def NtSetInformationThread(agent_id, file_handle, info_class, info_data):
    from models.agent import Agent
    from models.syscall import Syscall
    from services.binary import build_ptr, push_syscall
    
    agent = Agent.by_id(agent_id)
    syscall = Syscall.sys(agent.id, "NtSetInformationThread")
    scratchpad = agent.scratchpad
    
    # 1. Build IO_STATUS_BLOCK in scratchpad
    # Format: [8-byte Status/Pointer]
    io_status_data, info_buf_ptr = build_ptr(scratchpad, b"\x00" * 8)
    
    # 2. Place the Information Data (e.g., FILE_DISPOSITION_INFORMATION) in scratchpad
    # This follows the IO_STATUS_BLOCK
    info = int.to_bytes(info_data, 8, 'little')
    info_buffer_data, next_ptr = build_ptr(info_buf_ptr, info)
    
    params = [
        file_handle,      # FileHandle
        scratchpad,       # &IoStatusBlock (at the start of scratchpad)
        info_buf_ptr,     # &FileInformation (the actual info structure)
        len(info),   # Length
        info_class        # FileInformationClass
    ]
    
    shellcode = push_syscall(syscall, params, agent.debug)
    data = io_status_data + info_buffer_data
    
    #printf"NtSetInformationFile(FileHandle={hex(file_handle)}, IoStatus={hex(scratchpad)}, InfoBuf={hex(info_buf_ptr)}, Len={len(info_data)}, Class={info_class})")
    
    return data, shellcode

def setThreadInfo(agent_id, file_handle, info_class, info_data):
    from services.orders import write_scratchpad, send_and_wait
    
    data, shellcode = NtSetInformationThread(agent_id, file_handle, info_class, info_data)
    
    # Write the structures (IO_STATUS and InfoBlock) to agent memory
    write_scratchpad(agent_id, data)
    
    # Execute the syscall
    response_bytes = send_and_wait(agent_id, shellcode)
    ntstatus = int.from_bytes(response_bytes, 'little')
    
    #printf"Response from NtSetInformationThread = {hex(ntstatus)}")
    return ntstatus

def function(agent_id, args):
    # Example usage for Deletion (FileDispositionInformation = 13)
    # args[0]: handle, args[1]: class, args[2]: data
    # Note: For deletion, info_data is usually b"\x01" (Delete = True)
    
    file_handle = args[0]
    info_class = args[1]
    info_data = args[2] # Ensure this is passed as bytes
    print(args)
    retval = setThreadInfo(agent_id, file_handle, info_class, info_data)
    
    return {"retval": hex(retval)}