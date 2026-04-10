NAME = "encrypttest"
DESCRIPTION = "Test encryption."
PARAMS = [
    {"name":"file", "description":"Random file to test encryption in (will be overwritten)", "type":"str"}
]

# Dependencies: 
# 1. NtQueryInformationProcess (to find PEB)
DEPENDENCIES = ["encrypt", "decrypt", "read", "write"]


def function(agent_id, args):
    file_name = args[0]
    testdata = "asd"
    write(agent_id, [file_name, testdata])
    encrypt(agent_id, [file_name])
    post_encrypt_data = read(agent_id, [file_name])
    post_encrypt_data = post_encrypt_data["data"]
    decrypt(agent_id, [file_name])
    return {"retval":0} 