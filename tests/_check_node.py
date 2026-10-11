import sys, pathlib
sys.path.insert(0, 'tests')
from device import connect, command
c = connect()
try:
    data = pathlib.Path('launcher/node.sh').read_bytes().replace(b'\r\n', b'\n')
    with c.open_sftp() as sftp:
        with sftp.file('/tmp/weread-node-new.sh', 'wb') as f:
            f.write(data)
    print(command(c, 'bash -n /tmp/weread-node-new.sh && echo SYNTAX_OK'))
finally:
    c.close()