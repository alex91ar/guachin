NAME = "dir"
DESCRIPTION = "Enumerate files in a directory. If no path is provided, it uses the agent's current working directory."
PARAMS = [
    {"name":"directory_path", "description":"Optional: Complete path (e.g. C:\\Windows)", "type":"str", "optional": True, "default": ""},
]

DEPENDENCIES = [
    "NtAllocateVirtualMemory", 
    "NtOpenFile", 
    "NtQueryDirectoryFile", 
    "NtClose", 
    "NtFreeVirtualMemory",
    "NtReadVirtualMemory",
    "pwd"
]

# ... (parse_file_both_dir_information, filetime_to_dt, format_dir_entry, build_dir_output same as before) ...
def filetime_to_dt(filetime):
    import datetime
    """Convert Windows FILETIME (100-ns since 1601) to datetime."""
    if not filetime:
        return None
    return datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=filetime / 10)

def format_dir_entry(entry):
    dt = filetime_to_dt(entry["last_write_time"])
    if dt:
        date_str = dt.strftime("%m/%d/%Y")
        time_str = dt.strftime("%I:%M %p")
    else:
        date_str = "??/??/????"
        time_str = "??:??"

    is_dir = entry["file_attributes"] & 0x10  # FILE_ATTRIBUTE_DIRECTORY

    if is_dir:
        size_str = "<DIR>".rjust(14)
    else:
        size_str = str(entry["end_of_file"]).rjust(14)

    return f"{date_str}  {time_str}  {size_str}  {entry['file_name']}"

def parse_file_both_dir_information(buf: bytes):
    import struct 
    """
    Parse a buffer returned by NtQueryDirectoryFile with 
    FileBothDirectoryInformation (0x03).
    
    Structure: FILE_BOTH_DIR_INFORMATION (64-bit alignment)
    """
    entries = []
    offset = 0
    buflen = len(buf)

    while offset < buflen:
        # Minimum structure size checkout (94 bytes + 2 for alignment/char)
        if buflen - offset < 94:
            break

        # 0x00: NextEntryOffset (ULONG)
        # 0x04: FileIndex (ULONG)
        next_entry_offset, file_index = struct.unpack_from("<II", buf, offset + 0)

        # 0x08-0x37: LARGE_INTEGER timestamps and sizes (8 bytes each)
        creation_time    = struct.unpack_from("<q", buf, offset + 8)[0]
        last_access_time = struct.unpack_from("<q", buf, offset + 16)[0]
        last_write_time  = struct.unpack_from("<q", buf, offset + 24)[0]
        change_time      = struct.unpack_from("<q", buf, offset + 32)[0]
        end_of_file      = struct.unpack_from("<q", buf, offset + 40)[0] # File Size
        allocation_size  = struct.unpack_from("<q", buf, offset + 48)[0]

        # 0x38: FileAttributes (ULONG)
        file_attributes  = struct.unpack_from("<I", buf, offset + 56)[0]
        # 0x3C: FileNameLength (ULONG) - In bytes
        file_name_length = struct.unpack_from("<I", buf, offset + 60)[0]
        # 0x40: EaSize (ULONG)
        ea_size          = struct.unpack_from("<I", buf, offset + 64)[0]
        # 0x44: ShortNameLength (CCHAR/1 byte)
        short_name_length = struct.unpack_from("<B", buf, offset + 68)[0]

        # 0x46: ShortName (WCHAR[12]) - Fixed 24 byte buffer
        short_name_raw = buf[offset + 70 : offset + 70 + 24]
        try:
            short_name = short_name_raw[:short_name_length].decode("utf-16le", errors="ignore")
        except:
            short_name = ""
        # 0x5E: (Padding/Reserved - 2 bytes usually)
        # 0x60: FileName (WCHAR[1]) - Variable length starts here (Offset 94)
        file_name_offset = offset + 94
        file_name_end = file_name_offset + file_name_length
        
        if file_name_end > buflen:
            break

        try:
            file_name = buf[file_name_offset:file_name_end].decode("utf-16le", errors="ignore")
        except:
            file_name = "Unknown"
        if file_name[-1] == "\x00":
            file_name = file_name[:-1]
        entries.append({
            "next_entry_offset": next_entry_offset,
            "file_index": file_index,
            "creation_time": creation_time,
            "last_access_time": last_access_time,
            "last_write_time": last_write_time,
            "change_time": change_time,
            "end_of_file": end_of_file,
            "allocation_size": allocation_size,
            "file_attributes": file_attributes,
            "file_name_length": file_name_length,
            "ea_size": ea_size,
            "short_name_length": short_name_length,
            "short_name": short_name,
            "file_name": file_name,
        })

        # If offset is 0, this is the last entry in the buffer
        if next_entry_offset == 0:
            break

        # Move to the next structure block
        offset += next_entry_offset

    return entries

def build_dir_output(entries):
    lines = []

    total_files = 0
    total_dirs = 0
    total_size = 0

    for e in entries:
        lines.append(format_dir_entry(e))

        if e["file_attributes"] & 0x10:
            total_dirs += 1
        else:
            total_files += 1
            total_size += e["end_of_file"]

    lines.append("")  # blank line like dir

    lines.append(f"               {total_files} File(s) {total_size} bytes")
    lines.append(f"               {total_dirs} Dir(s)")

    return "\n".join(lines)

def function(agent_id, args):
    from services.orders import read_from_agent
    
    # Check if directory_path was provided and is not empty
    if not args or args[0] == "":
        #print"[*] No path provided. Resolving current directory from PEB...")
        dir_path = pwd(agent_id, [])
        dir_path = dir_path["pwd"]
    else:
        dir_path = args[0]
    
    # Ensure Native Prefix
    if not dir_path.startswith("\\??\\"):
        dir_path = "\\??\\" + dir_path

    #printf"[*] Enumerating: {dir_path}")
    buf_size = 8192

    # 1. ALLOCATE MEMORY
    alloc_ret = NtAllocateVirtualMemory(agent_id, [buf_size, 0x04]) 
    
    if alloc_ret["retval"] == 0:
        target_buf_ptr = alloc_ret["allocated_memory"]

        # 2. OPEN THE DIRECTORY
        # Access: FILE_LIST_DIRECTORY | SYNCHRONIZE (0x100001)
        open_ret = NtOpenFile(agent_id, [dir_path, 0x00100001, 0x00000007, 0x00000021, 0])
        
        if open_ret["retval"] == 0:
            dir_handle = open_ret["FILE_HANDLE"]
            
            # 3. QUERY
            query_ret = NtQueryDirectoryFile(agent_id, [dir_handle, target_buf_ptr, buf_size])
            
            if query_ret["retval"] == 0:
                import inspect
                data = read_from_agent(agent_id, target_buf_ptr, buf_size)
                entries = parse_file_both_dir_information(data)
                formatted_output = "\n Directory of " + dir_path + "\n\n" + build_dir_output(entries)
                print(f"caller = {inspect.stack()[1].function} from {inspect.stack()[2].function} from {inspect.stack()[3].function} ")
                if inspect.stack()[3].function == "_shell_ws_agent":
                    results = formatted_output
                else:
                    results = entries
                    results = {"retval":0, "results":entries}

                NtClose(agent_id, [dir_handle])
                NtFreeVirtualMemory(agent_id, [target_buf_ptr, buf_size])
                return results
            else:
                NtClose(agent_id, [dir_handle])
                NtFreeVirtualMemory(agent_id, [target_buf_ptr, 0])
                return {"retval": -1, "message":f"Error in NtQueryDirectoryFile: {hex(query_ret['retval'])}"}
        else:
            NtFreeVirtualMemory(agent_id, [target_buf_ptr, 0])
            return {"retval": -1, "message":f"Error in NtOpenFile: {hex(open_ret['retval'])}"}
    else:
        return {"retval": -1, "message":f"Error in NtAllocateVirtualMemory: {hex(alloc_ret['retval'])}"}