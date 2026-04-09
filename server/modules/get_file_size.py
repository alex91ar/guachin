NAME = "get_file_size"
DESCRIPTION = "Retrieve the size of an open file using ntdll!NtQueryInformationFile."
PARAMS = [
    {"name":"file_name", "description":"The file name", "type":"str"}
]

# Dependencies: 
# 1. NtQueryInformationFile (to query EOF)
DEPENDENCIES = ["NtQueryInformationFile", "NtOpenFile","NtClose"]

def function(agent_id, args):
    from services.orders import write_scratchpad, send_and_wait, read_scratchpad
    import struct
    
    file_name = args[0] if args[0].startswith("\\??\\") else "\\??\\" + args[0]
    ret = NtOpenFile(agent_id, [file_name,  0x100080, 0x00000007, 0x00000020, 0])
    print(f"NtOpenFile {ret}")
    if ret["retval"] != 0:
        return{"retval"f"Error in NtOpenFile {ret["retval"]}"}
    ret_ntquery = NtQueryInformationFile(agent_id, [ret["FILE_HANDLE"], 5,  24])
    if ret_ntquery["retval"] != 0:
        NtClose(agent_id, [ret["FILE_HANDLE"]])
        return {"retval":f"Error in NtQueryInformationFile {ret_ntquery["retval"]}"}
    buffer_hex = ret_ntquery["BufferHex"]
    print(f"NtQuerInformationFile returned 0: {buffer_hex}")
    NtClose(agent_id, [ret["FILE_HANDLE"]])
    file_size = int.from_bytes(buffer_hex[:8], byteorder="little")
    print(f"File size = {file_size}")
    return {
        "retval": 0,
        "file_size": file_size,
    }