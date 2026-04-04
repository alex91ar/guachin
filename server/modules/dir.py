NAME = "dir"
DESCRIPTION = "Enumerate files in a directory using separate memory allocation"
PARAMS = [
    {"name":"directory_path", "description":"Complete path (e.g. C:\\Windows)", "type":"str"}
]
# We now require 5 dependencies for the full memory-safe chain
DEPENDENCIES = [
    "NtAllocateVirtualMemory", 
    "NtOpenFile", 
    "NtQueryDirectoryFile", 
    "NtClose", 
    "NtFreeVirtualMemory"
]

def parse_file_both_dir_information(buf: bytes):
    import struct 
    """
    Parse a buffer returned by NtQueryDirectoryFile with
    FileBothDirectoryInformation / FILE_BOTH_DIR_INFORMATION.

    Returns a list of dicts.
    """
    entries = []
    offset = 0
    buflen = len(buf)

    while offset < buflen:
        if buflen - offset < 94:
            break

        next_entry_offset, file_index = struct.unpack_from("<II", buf, offset + 0)

        creation_time      = struct.unpack_from("<q", buf, offset + 8)[0]
        last_access_time   = struct.unpack_from("<q", buf, offset + 16)[0]
        last_write_time    = struct.unpack_from("<q", buf, offset + 24)[0]
        change_time        = struct.unpack_from("<q", buf, offset + 32)[0]
        end_of_file        = struct.unpack_from("<q", buf, offset + 40)[0]
        allocation_size    = struct.unpack_from("<q", buf, offset + 48)[0]

        file_attributes    = struct.unpack_from("<I", buf, offset + 56)[0]
        file_name_length   = struct.unpack_from("<I", buf, offset + 60)[0]
        ea_size            = struct.unpack_from("<I", buf, offset + 64)[0]
        short_name_length  = struct.unpack_from("<B", buf, offset + 68)[0]

        # offset 69 is padding
        short_name_raw = buf[offset + 70 : offset + 70 + 24]
        short_name = short_name_raw[:short_name_length].decode("utf-16le", errors="ignore")

        file_name_offset = offset + 94
        file_name_end = file_name_offset + file_name_length
        if file_name_end > buflen:
            break

        file_name = buf[file_name_offset:file_name_end].decode("utf-16le", errors="ignore")

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

        if next_entry_offset == 0:
            break

        offset += next_entry_offset

    return entries

def filetime_to_dt(filetime):
    import datetime
    """Convert Windows FILETIME (100-ns since 1601) to datetime."""
    if not filetime:
        return None
    return datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=filetime / 10)


def filetime_to_dt(filetime):
    import datetime
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
    
    dir_path = args[0] if args[0].startswith("\\??\\") else "\\??\\" + args[0]
    buf_size = 8192

    # 1. ALLOCATE MEMORY (RW) for the results buffer
    # NtAllocateVirtualMemoryreturns a pointer to the newly allocated 8KB region
    alloc_ret = NtAllocateVirtualMemory(agent_id, [buf_size, 0x04]) # MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
    
    if alloc_ret["retval"] == 0:
        target_buf_ptr = alloc_ret["allocated_memory"]
        print(f"[*] Allocated {buf_size} bytes at {hex(target_buf_ptr)} for enumeration.")

        # 2. OPEN THE DIRECTORY (Access: 0x01 = FILE_LIST_DIRECTORY)
        # Using our OpenFile component to get the dir handle
        open_ret = NtOpenFile(agent_id, [dir_path, 0x00100001, 0x00000007, 0x00000021, 0])
        
        if open_ret["retval"] == 0:
            dir_handle = open_ret["FILE_HANDLE"]
            
            # 3. QUERY THE DIRECTORY CONTENTS
            # We call NtQueryDirectoryFile with the REMOTE buffer pointer we just allocated
            # args: [handle, buffer_ptr, buffer_size]

            query_ret = NtQueryDirectoryFile(agent_id, [dir_handle, target_buf_ptr, buf_size])
            
            if query_ret["retval"] == 0:
                # 4. Success! (The results are now in target_buf_ptr)
                # You might need a way to read this remote buffer back to the UI.
                # For now, we return the status and the location.
                data = read_from_agent(agent_id, target_buf_ptr, buf_size)
                data = parse_file_both_dir_information(data)
                data = "\n" + build_dir_output(data)
                print(data)

                results = {
                    "Result": "Success",
                    "BytesReturned": query_ret.get("bytes_written", 0),
                    "BufferLocation": hex(target_buf_ptr),
                    "file_data": data
                }

                
                # 5. CLEANUP: CLOSE HANDLE
                NtClose(agent_id, [dir_handle])
                
                # 6. CLEANUP: DEALLOCATE MEMORY
                # NtFreeVirtualMemory (Syscall 0x1E)
                # args: [base_addr, size, free_type]
                free_ret = NtFreeVirtualMemory(agent_id, [target_buf_ptr, buf_size]) # MEM_RELEASE
                if free_ret["retval"] != 0:
                    print(f"[!] Warning: NtFreeVirtualMemory failed with {hex(free_ret['retval'])}")
                
                return results

            else:
                NtClose(agent_id, [dir_handle])
                NtFreeVirtualMemory(agent_id, [target_buf_ptr, 0])
                return {"Result": f"Error in NtQueryDirectoryFile: {hex(query_ret['retval'])}"}
        else:
            NtFreeVirtualMemory(agent_id, [target_buf_ptr, 0])
            return {"Result": f"Error in NtOpenFile: {hex(open_ret['retval'])}"}
    else:
        return {"Result": f"Error in NtAllocateVirtualMemory: {hex(alloc_ret['retval'])}"}