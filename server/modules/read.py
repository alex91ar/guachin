NAME = "read"
DESCRIPTION = "Read bytes from a file"
PARAMS = [
    {"name":"file_name", "description":"The file name", "type":"str"},
    {"name":"read_size", "description":"Number of bytes to read", "type":"int", "optional":True, "default":"0"},
    {"name":"byte_offset", "description":"Offset to read the file from", "type":"hex", "optional":True, "default":"0"},
]
DEPENDENCIES = ["NtOpenFile", "NtReadFile", "NtClose", "NtAllocateVirtualMemory", "NtFreeVirtualMemory", "get_file_size"]

def function(agent_id, args):
    from services.orders import read_from_agent
    from services.binary import align_up


    file_name = args[0] if args[0].startswith("\\??\\") else "\\??\\" + args[0]
    read_size = args[1]
    if read_size == 0:
        read_size = get_file_size(agent_id, [file_name])
        if read_size["retval"] != 0:
            return{"retval":"Error geting file size."}
        else:
            read_size = read_size["file_size"]
    buffer_size = align_up(read_size, 0x1000)
    byte_offset = args[2]

    ret = NtAllocateVirtualMemory(agent_id, [buffer_size, 0x04])
    if ret["retval"] == 0:
        buffer_ptr = ret["allocated_memory"]
        print(f"buffer_ptr = {hex(buffer_ptr)}")

        ret = NtOpenFile(agent_id, [file_name,  0x00100001, 0x00000007, 0x00000020, 0])
        if ret["retval"] == 0:
            file_handle = ret["FILE_HANDLE"]
            print(f"About to call NtReadFile {[file_handle, buffer_ptr, read_size, byte_offset]}")
            ret = NtReadFile(agent_id, [file_handle, buffer_ptr, read_size, byte_offset])
            if ret["retval"] == 0:
                data = read_from_agent(agent_id, buffer_ptr, read_size)

                retclose = NtClose(agent_id, [file_handle])
                print(f"NtClose = {hex(retclose['retval'])}")

                retfree = NtFreeVirtualMemory(agent_id, [buffer_ptr, buffer_size])
                print(f"NtFreeVirtualMemory = {hex(retfree['retval'])}")
                decoded = data
                return {
                    "retval": 0,
                    "data": decoded
                }
            else:
                retclose = NtClose(agent_id, [file_handle])
                print(f"NtClose = {hex(retclose['retval'])}")

                retfree = NtFreeVirtualMemory(agent_id, [buffer_ptr, buffer_size])
                print(f"NtFreeVirtualMemory = {hex(retfree['retval'])}")

                return {"retval": f"Error in NtReadFile: {hex(ret['retval'])}"}
        else:
            retfree = NtFreeVirtualMemory(agent_id, [buffer_ptr, buffer_size])
            print(f"NtFreeVirtualMemory = {hex(retfree['retval'])}")

            return {"retval": f"Error in NtOpenFile: {hex(ret['retval'])}"}
    else:
        return {"retval": "Failed to allocate process memory"}