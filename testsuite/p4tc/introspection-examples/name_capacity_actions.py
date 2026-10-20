# SPDX-License-Identifier: GPL-2.0-or-later
import json,subprocess,sys
tc=sys.argv[1]
def run(*args,status=0):
    p=subprocess.run([tc,*args],capture_output=True,text=True)
    assert p.returncode==status,(args,p.returncode,p.stdout,p.stderr)
    return p
names=['a'*31,'a'*32]
for ident,name in enumerate(names,1):
    run('p4template','create','action/ptables/'+name,'actid',str(ident))
before=[json.loads(run('-j','p4template','get','action/ptables/'+name).stdout) for name in names]
for length,ident in [(33,3),(34,4)]:
    p=run('p4template','create','action/ptables/'+'a'*length,'actid',str(ident),status=255)
    assert 'Path component exceeds 32 bytes' in p.stderr,p.stderr
    run('p4template','get','action/ptables','actid',str(ident),status=255)
assert before==[json.loads(run('-j','p4template','get','action/ptables/'+name).stdout) for name in names]
args=['p4template','create','table/ptables/cb/tname2','tblid','2','keysz','32','table_acts']
for name in names: args+=['act','name','ptables/'+name]
run(*args)
table=json.loads(run('-j','p4template','get','table/ptables/cb/tname2').stdout)
assert sorted(a['act_name'] for a in table[0]['acts_list'])==names,table
print('ACTION_NAME_ROUNDTRIP_OK')
