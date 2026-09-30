import re, pcbnew
def parse(s):
    toks=re.findall(r'"[^"]*"|\(|\)|[^\s()]+',s); st=[[]]
    for t in toks:
        if t=='(': st.append([])
        elif t==')': x=st.pop(); st[-1].append(x)
        else: st[-1].append(t.strip('"'))
    return st[0][0]
def find(n,key): return [c for c in n if isinstance(c,list) and c and c[0]==key]
def import_ses(b,fn,skip_nets=()):
    tree=parse(open(fn).read())
    ro=find(tree,'routes')[0]
    res=find(ro,'resolution')[0]; scale=1e6/ (float(res[2])*1000) if res[1]=='um' else None  # nm por unidad
    nmper=1000/float(res[2])  # nm por unidad (um/10 -> 100 nm)
    layers={'F.Cu':pcbnew.F_Cu,'B.Cu':pcbnew.B_Cu}
    nw=find(ro,'network_out')[0]; nt=nv=0
    for net in find(nw,'net'):
        name=net[1]
        if name in skip_nets: continue
        ni=b.FindNet(name)
        for w in find(net,'wire'):
            if find(w,'type') and find(w,'type')[0][1]=='protect': continue
            p=find(w,'path')[0]; ly=layers[p[1]]; wd=int(float(p[2])*nmper)
            xs=list(map(float,p[3:])); pts=[(int(xs[i]*nmper),int(-xs[i+1]*nmper)) for i in range(0,len(xs),2)]
            for a,c in zip(pts,pts[1:]):
                t=pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(*a)); t.SetEnd(pcbnew.VECTOR2I(*c)); t.SetWidth(wd); t.SetLayer(ly); t.SetNet(ni); b.Add(t); nt+=1
        for v in find(net,'via'):
            m=re.search(r'_(\d+):(\d+)_um',v[1]); x,y=float(v[2]),float(v[3])
            via=pcbnew.PCB_VIA(b); via.SetPosition(pcbnew.VECTOR2I(int(x*nmper),int(-y*nmper)))
            via.SetWidth(int(m.group(1))*1000); via.SetDrill(int(m.group(2))*1000); via.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu); via.SetNet(ni); b.Add(via); nv+=1
    return nt,nv
