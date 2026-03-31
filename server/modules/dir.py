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

import struct

def parse_file_both_dir_information(data: bytes):
    import struct
    """
    Parses a bytearray containing one or more FILE_BOTH_DIR_INFORMATION entries.
    Returns a list of dictionaries.
    """

    results = []
    offset = 0
    length = len(data)

    while offset < length:
        # Base structure (fixed part before FileName)
        # Layout reference (little-endian):
        # ULONG NextEntryOffset (4)
        # ULONG FileIndex (4)
        # LARGE_INTEGER CreationTime (8)
        # LARGE_INTEGER LastAccessTime (8)
        # LARGE_INTEGER LastWriteTime (8)
        # LARGE_INTEGER ChangeTime (8)
        # LARGE_INTEGER EndOfFile (8)
        # LARGE_INTEGER AllocationSize (8)
        # ULONG FileAttributes (4)
        # ULONG FileNameLength (4)
        # ULONG EaSize (4)
        # CHAR ShortNameLength (1)
        # WCHAR ShortName[12] (24 bytes)
        base_format = "<IIqqqqqqIIIb"
        base_size = struct.calcsize(base_format)

        if offset + base_size > length:
            break

        unpacked = struct.unpack_from(base_format, data, offset)

        (
            next_entry_offset,
            file_index,
            creation_time,
            last_access_time,
            last_write_time,
            change_time,
            end_of_file,
            allocation_size,
            file_attributes,
            file_name_length,
            ea_size,
            short_name_length
        ) = unpacked

        # ShortName is fixed 24 bytes (12 WCHARs)
        short_name_offset = offset + base_size
        short_name_raw = data[short_name_offset:short_name_offset + 24]

        short_name = short_name_raw[:short_name_length * 2].decode("utf-16le", errors="ignore")

        # FileName follows immediately after ShortName
        file_name_offset = short_name_offset + 24
        file_name_raw = data[file_name_offset:file_name_offset + file_name_length]

        file_name = file_name_raw.decode("utf-16le", errors="ignore")

        results.append({
            "file_index": file_index,
            "creation_time": creation_time,
            "last_access_time": last_access_time,
            "last_write_time": last_write_time,
            "change_time": change_time,
            "end_of_file": end_of_file,
            "allocation_size": allocation_size,
            "file_attributes": file_attributes,
            "ea_size": ea_size,
            "short_name": short_name,
            "file_name": file_name,
        })

        # Move to next entry
        if next_entry_offset == 0:
            break

        offset += next_entry_offset

    return results

def function(agent_id, args, dependencies):
    from services.orders import read_from_agent
    NtAlloc = dependencies[0]
    NtOpen = dependencies[1]
    NtQuery = dependencies[2]
    NtClose = dependencies[3]
    NtFree = dependencies[4]
    
    dir_path = args[0] if args[0].startswith("\\??\\") else "\\??\\" + args[0]
    buf_size = 8192

    # 1. ALLOCATE MEMORY (RW) for the results buffer
    # NtAlloc returns a pointer to the newly allocated 8KB region
    alloc_ret = NtAlloc(agent_id, [buf_size, 0x04]) # MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE
    
    if alloc_ret["NTSTATUS"] == 0:
        target_buf_ptr = alloc_ret["allocated_memory"]
        print(f"[*] Allocated {buf_size} bytes at {hex(target_buf_ptr)} for enumeration.")

        # 2. OPEN THE DIRECTORY (Access: 0x01 = FILE_LIST_DIRECTORY)
        # Using our OpenFile component to get the dir handle
        open_ret = NtOpen(agent_id, [dir_path, 0x00100001])
        
        if open_ret["NTSTATUS"] == 0:
            dir_handle = open_ret["FILE_HANDLE"]
            
            # 3. QUERY THE DIRECTORY CONTENTS
            # We call NtQueryDirectoryFile with the REMOTE buffer pointer we just allocated
            # args: [handle, buffer_ptr, buffer_size]

            query_ret = NtQuery(agent_id, [dir_handle, target_buf_ptr, buf_size])
            
            if query_ret["NTSTATUS"] == 0:
                # 4. Success! (The results are now in target_buf_ptr)
                # You might need a way to read this remote buffer back to the UI.
                # For now, we return the status and the location.
                data = read_from_agent(agent_id, target_buf_ptr, buf_size)
                data = parse_file_both_dir_information(data)
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
                free_ret = NtFree(agent_id, [target_buf_ptr, buf_size]) # MEM_RELEASE
                if free_ret["NTSTATUS"] != 0:
                    print(f"[!] Warning: NtFree failed with {hex(free_ret['NTSTATUS'])}")
                
                return results

            else:
                NtClose(agent_id, [dir_handle])
                NtFree(agent_id, [target_buf_ptr, 0])
                return {"Result": f"Error in NtQueryDirectoryFile: {hex(query_ret['NTSTATUS'])}"}
        else:
            NtFree(agent_id, [target_buf_ptr, 0])
            return {"Result": f"Error in NtOpenFile: {hex(open_ret['NTSTATUS'])}"}
    else:
        return {"Result": f"Error in NtAllocateVirtualMemory: {hex(alloc_ret['NTSTATUS'])}"}