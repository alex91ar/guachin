NAME = "createpipesforexeckernel"
DESCRIPTION = "Create an anonymous pipe pair using ntdll!NtCreateNamedPipeFile"
PARAMS = [
]
DEPENDENCIES = ["CreateNamedPipe", "NtOpenFile", "NtClose"]
DEFAULT = True

def function(agent_id, args):
    pipename = "\\??\\pipe\\MyNativePipe"
    ret = CreateNamedPipe(agent_id, [pipename])
    if ret["retval"] == 0xFFFFFFFFFFFFFFFF:
        #printf"Error creating named pipe {pipename}")
        return {"retval": False}
    read_pipe_h = ret["retval"]
    ret = NtOpenFile(agent_id, [pipename, 0xC0100000])
    if ret["retval"] != 0:
        #printf"Error opening write handle to pipe {pipename}")
        NtClose(read_pipe_h)
        return {"retval": False}
    write_pipe_h = ret["FILE_HANDLE"]
    #printf"createpipesforexeckernel read_pipe_h = {hex(read_pipe_h)}, write_pipe_h = {hex(write_pipe_h)}")
    return {
        "retval": True,
        "READ_HANDLE": read_pipe_h,
        "WRITE_HANDLE": write_pipe_h
    }