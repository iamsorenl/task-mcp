import json,sys,tiktoken
enc=tiktoken.get_encoding("o200k_base")
def walk(o,d=0):
    leaves=keys=0;md=d
    if isinstance(o,dict):
        for v in o.values():
            keys+=1;l,k,m=walk(v,d+1);leaves+=l;keys+=k;md=max(md,m)
    elif isinstance(o,list):
        for v in o:
            l,k,m=walk(v,d+1);leaves+=l;keys+=k;md=max(md,m)
    else: leaves=1
    return leaves,keys,md
for f in sys.argv[1:]:
    raw=open(f,'rb').read()
    try: j=json.loads(raw)
    except Exception as e: print(f,len(raw),"NOT JSON",raw[:80]);continue
    top=len(j) if isinstance(j,dict) else len(j)
    topk=len(j) if isinstance(j,dict) else (len(j[0]) if j and isinstance(j[0],dict) else 0)
    l,k,m=walk(j)
    mini=json.dumps(j,separators=(',',':'))
    print(f"{f}\tbytes={len(raw)}\ttop={'dict' if isinstance(j,dict) else 'list['+str(len(j))+']'}\ttopkeys={topk}\ttotalKeyNames={k}\tleaves={l}\tdepth={m}\ttok_o200k_raw={len(enc.encode(raw.decode()))}\ttok_mini={len(enc.encode(mini))}")
