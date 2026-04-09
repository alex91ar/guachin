NAME = "write"
DESCRIPTION = "Write a buffer to a file"
PARAMS = [
    {"name":"file_name", "description":"The file name", "type":"str"},
    {"name":"data_buffer", "description":"Bytes buffer to write", "type":"bytes"},
    {"name":"byte_offset", "description":"Offset to write the file into", "type":"hex", "optional":True, "default":"0"},
]
DEPENDENCIES = ["NtCreateFile", "NtWriteFile", "NtClose", "NtAllocateVirtualMemory", "NtFreeVirtualMemory","set_eof"]

def function(agent_id, args):
    from services.orders import write_to_agent
    from services.binary import align_up
    file_name = "\\??\\" + args[0]
    data_buffer = args[1]
    buffer_size = align_up(len(data_buffer), 0x1000)
    byte_offset = args[2]
    print(f"Value of data_buffer= {data_buffer}")
    ret = NtAllocateVirtualMemory(agent_id, [buffer_size, 0x04])
    buffer_ptr = ret["allocated_memory"]
    if ret["retval"] == 0:
        print(write_to_agent(agent_id, buffer_ptr, data_buffer))
        ret = NtCreateFile(agent_id, [file_name, 0xC0100000])
        if ret["retval"] == 0:
            file_handle = ret["FILE_HANDLE"]
            ret = NtWriteFile(agent_id, [file_handle, buffer_ptr, len(data_buffer), byte_offset])
            if ret["retval"] == 0:
                ret = set_eof(agent_id, [file_handle, len(data_buffer)])
                if ["retval"] == 0:
                    ret = NtClose(agent_id, [file_handle])
                    if ret["retval"] == 0:
                        retfree = NtFreeVirtualMemory(agent_id, [buffer_ptr, buffer_size])
                        print(f"NtFreeVirtualMemory = {hex(retfree["retval"])}")
                        return {"retval":0}
                    else:
                        retfree = NtFreeVirtualMemory(agent_id, [buffer_ptr, buffer_size])
                        print(f"NtFreeVirtualMemory = {hex(retfree["retval"])}")
                        return {"retval":0}
                else:
                    retfree = NtFreeVirtualMemory(agent_id, [buffer_ptr, buffer_size])
                    print(f"NtFreeVirtualMemory = {hex(retfree["retval"])}")
                    return {"retval":0}
            else:
                retfree = NtFreeVirtualMemory(agent_id, [buffer_ptr, buffer_size])
                print(f"NtFreeVirtualMemory = {hex(retfree["retval"])}")
                return {"retval":0}
        else:
            retfree = NtFreeVirtualMemory(agent_id, [buffer_ptr, buffer_size])
            print(f"NtFreeVirtualMemory = {hex(retfree["retval"])}")
            return {"retval":0}
    else:
        return {"retval":0}