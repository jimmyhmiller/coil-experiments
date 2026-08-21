#!/usr/bin/env python3
"""Translate clang's typed JSON AST to inspectable Coil (never compiles C)."""
import ast, json, os, re, subprocess, sys

class Error(Exception): pass
def q(s): return '"' + s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\t','\\t') + '"'
def children(n, kind=None):
    xs=n.get('inner',[])
    return [x for x in xs if kind is None or x.get('kind')==kind]
def name(n): return re.sub(r'[^A-Za-z0-9_?!+*/<>=-]', '_', n.get('name','anon'))

class Gen:
  def __init__(self, ast, source):
    self.ast=ast; self.source=source; self.records={}; self.typedef={}; self.funcs=set(); self.globals={}; self.strings=[]
  def typ(self,t):
    s=(t or {}).get('desugaredQualType') or (t or {}).get('qualType','int'); s=re.sub(r'\b(const|volatile|restrict|_Atomic)\b','',s).strip()
    if s in self.typedef: return self.typedef[s]
    base={'void':'void','_Bool':'bool','char':'i8','signed char':'i8','unsigned char':'u8','short':'i16','short int':'i16','unsigned short':'u16','unsigned short int':'u16','int':'i32','signed int':'i32','unsigned':'u32','unsigned int':'u32','long':'i64','long int':'i64','unsigned long':'u64','unsigned long int':'u64','long long':'i64','unsigned long long':'u64','float':'f32','double':'f64','long double':'f64'}
    if s in base:return base[s]
    m=re.match(r'(.+)\s*\[(\d+)\]$',s)
    if m:return f'(array {self.typ({"qualType":m.group(1)})} {m.group(2)})'
    m=re.match(r'(.+) \(\*\)\((.*)\)$',s)
    if m:
      aa=[] if m.group(2).strip() in ('','void') else [self.typ({'qualType':x.strip()}) for x in m.group(2).split(',')]
      return f'(fnptr c [{" ".join(aa)}] {self.typ({"qualType":m.group(1)})})'
    if s.endswith('*'): return f'(ptr {self.typ({"qualType":s[:-1].strip()})})'
    if s.startswith(('struct ','union ','enum ')): return name({'name':s.split(' ',1)[1]}) if not s.startswith('enum ') else 'i32'
    return name({'name':s})
  def cast(self,ty,x): return f'(primitive/cast {self.typ(ty)} {x})'
  def lit(self,n):
    v=n.get('value','0'); t=self.typ(n.get('type'))
    if t in ('f32','f64'): return v
    return self.cast(n.get('type'),v)
  def lv(self,n):
    k=n.get('kind'); ins=children(n)
    if k=='DeclRefExpr':
      z=name(n.get('referencedDecl',n)); return f'(__c_global_{z})' if z in self.globals else z
    if k=='UnaryOperator' and n.get('opcode')=='*': return self.expr(ins[0])
    if k=='ArraySubscriptExpr': return f'(primitive/index {self.expr(ins[0])} (primitive/cast i64 {self.expr(ins[1])}))'
    if k=='MemberExpr':
      b=self.expr(ins[0]) if n.get('isArrow') else self.lv(ins[0]); return f'(field {b} {name(n)})'
    raise Error('unsupported lvalue '+str(k))
  def expr(self,n):
    k=n.get('kind'); ins=children(n)
    if k in ('IntegerLiteral','FloatingLiteral'): return self.lit(n)
    if k=='CharacterLiteral': return self.cast(n.get('type'),str(n.get('value',0)))
    if k=='StringLiteral':
      v=n.get('value','')
      if len(v)>=2 and v[0]=='"' and v[-1]=='"': v=ast.literal_eval(v)
      return 'c'+q(v)
    if k in ('ParenExpr','ImplicitCastExpr','ExprWithCleanups','ConstantExpr','CStyleCastExpr'):
      if k=='ImplicitCastExpr' and n.get('castKind')=='ArrayToPointerDecay':
        if ins[0].get('kind')=='StringLiteral': return self.cast(n.get('type'),self.expr(ins[0]))
        return f'(primitive/index {self.lv(ins[0])} 0)'
      x=self.expr(ins[0]); return self.cast(n.get('type'),x) if k=='CStyleCastExpr' else x
    if k=='DeclRefExpr':
      r=n.get('referencedDecl',n); z=name(r)
      if r.get('kind')=='EnumConstantDecl': return str(r.get('value',self.enums.get(z,0)))
      return f'(primitive/fnptr-of {z})' if r.get('kind')=='FunctionDecl' else f'(load {self.lv(n)})'
    if k=='UnaryOperator':
      op=n.get('opcode'); x=ins[0]
      if op=='&': return self.cast(n.get('type'),self.lv(x))
      if op=='*': return f'(load {self.expr(x)})'
      if op=='!': return f'(not {self.truth(self.expr(x))})'
      if op=='~': return f'(~ {self.expr(x)})'
      if op in ('++','--','post++','post--'):
        l=self.lv(x); d='+' if '+' in op else '-'; return f'(do (store! {l} ({d} (load {l}) 1)) (load {l}))'
      if op=='-': return f'(- 0 {self.expr(x)})'
      return self.expr(x)
    if k in ('BinaryOperator','CompoundAssignOperator'):
      op=n.get('opcode'); a=self.expr(ins[0]); b=self.expr(ins[1])
      mp={'&&':'and','||':'or','%':'primitive/srem','<<':'<<','>>':'>>','&':'&','|':'|','^':'^','==':'=','!=':'!=','<':'<','>':'>','<=':'<=','>=':'>='}
      if op=='=': return f'(do (store! {self.lv(ins[0])} {b}) {b})'
      if k=='CompoundAssignOperator':
        base=op[:-1]; l=self.lv(ins[0]); return f'(do (store! {l} ({mp.get(base,base)} (load {l}) {b})) (load {l}))'
      if op in ('&&','||'): return f'({mp[op]} {self.truth(a)} {self.truth(b)})'
      return f'({mp.get(op,op)} {a} {b})'
    if k=='ConditionalOperator': return f'(if {self.truth(self.expr(ins[0]))} {self.expr(ins[1])} {self.expr(ins[2])})'
    if k=='ArraySubscriptExpr' or k=='MemberExpr': return f'(load {self.lv(n)})'
    if k=='CallExpr':
      cal=ins[0]; args=' '.join(self.expr(x) for x in ins[1:])
      direct=cal
      while direct.get('kind') in ('ImplicitCastExpr','ParenExpr') and children(direct): direct=children(direct)[0]
      if direct.get('kind')=='DeclRefExpr' and direct.get('referencedDecl',{}).get('kind')=='FunctionDecl': return f'({name(direct.get("referencedDecl",direct))} {args})'
      return f'(primitive/call-ptr {self.expr(cal)} {args})'
    if k=='InitListExpr':
      t=self.typ(n.get('type')); vals=[self.expr(x) for x in ins]
      if t.startswith('(array '): return '['+' '.join(vals)+']'
      rec=self.records.get(t)
      if rec:
        fs=children(rec,'FieldDecl'); return f'({t} '+' '.join(f':{name(f)} {v}' for f,v in zip(fs,vals))+')'
      return '(primitive/zeroed '+t+')'
    if k=='GNUNullExpr': return '(primitive/cast (ptr u8) 0)'
    raise Error('unsupported expression '+str(k))
  def truth(self,x):
    if any(x.startswith('('+op+' ') for op in ('=','!=','<','>','<=','>=','and','or','not')): return x
    return f'(!= {x} 0)'
  def stmt(self,n):
    k=n.get('kind'); ins=children(n)
    if k=='CompoundStmt': return self.block(ins)
    if k=='ReturnStmt': return f'(coil.control.return-from :return {self.expr(ins[0]) if ins else "0"})'
    if k=='DeclStmt': raise Error('internal declaration escaped block lowering')
    if k=='IfStmt': return f'(if {self.truth(self.expr(ins[0]))} {self.stmt(ins[1])} {self.stmt(ins[2]) if len(ins)>2 else "0"})'
    if k=='WhileStmt': return f'(loop (when (not {self.truth(self.expr(ins[0]))}) (break) 0) {self.stmt(ins[1])})'
    if k=='DoStmt': return f'(loop {self.stmt(ins[0])} (when (not {self.truth(self.expr(ins[1]))}) (break) 0))'
    if k=='ForStmt':
      raw=n.get('inner',[]); init=raw[0] if raw and raw[0].get('kind') else None
      cond=raw[-3] if len(raw)>=3 and raw[-3].get('kind') else None
      inc=raw[-2] if len(raw)>=2 and raw[-2].get('kind') else None; body=raw[-1]
      loop=f'(loop {f"(when (not {self.truth(self.expr(cond))}) (break) 0)" if cond else ""} {self.stmt(body)} {self.expr(inc) if inc else 0})'
      if init and init.get('kind')=='DeclStmt':
        return f'(let [{" ".join(self.local(x) for x in children(init,"VarDecl"))}] {loop} 0)'
      return f'(do {self.stmt(init) if init else 0} {loop} 0)'
    if k=='BreakStmt': return '(break)'
    if k=='ContinueStmt': return '(continue)'
    if k=='NullStmt': return '0'
    return self.expr(n)
  def block(self,items):
    if not items: return '0'
    head,*tail=items
    if head.get('kind')=='DeclStmt':
      decls=children(head,'VarDecl'); binds=' '.join(self.local(x) for x in decls); setup=[]
      for d in decls:
        t=self.typ(d.get('type')); init=children(d)
        if t.startswith('(array ') and init and init[-1].get('kind')=='InitListExpr':
          setup += [f'(store! (primitive/index {name(d)} {i}) {self.expr(v)})' for i,v in enumerate(children(init[-1]))]
        if t in self.records and init and init[-1].get('kind')=='InitListExpr':
          fields=children(self.records[t],'FieldDecl')
          setup += [f'(store! (field {name(d)} {name(field)}) {self.expr(v)})' for field,v in zip(fields,children(init[-1]))]
      return f'(let [{binds}] (do {" ".join(setup)} {self.block(tail)}))'
    return f'(do {self.stmt(head)} {self.block(tail)})'
  def local(self,n):
    z=name(n); t=self.typ(n.get('type')); init=children(n)
    if t.startswith('(array ') or t in self.records: return f'{z} (alloc/stack {t})'
    v=self.expr(init[-1]) if init else f'(primitive/zeroed {t})'
    return f'(mut {z}) {v}'
  def function(self,n):
    z=name(n); pars=children(n,'ParmVarDecl'); body=next((x for x in children(n) if x.get('kind')=='CompoundStmt'),None)
    qt=n.get('type',{}).get('qualType','int ()'); ret=self.typ({'qualType':qt.split(' (',1)[0]}); args=' '.join(f'({name(p)} {self.typ(p.get("type"))})' for p in pars)
    if body is None:
      variadic=' ...' if n.get('variadic') else ''; return f'(extern {z} :cc c [{" ".join(self.typ(p.get("type")) for p in pars)}{variadic}] (-> {ret}))'
    aliases=' '.join(f'(mut {name(p)}__c) {name(p)}' for p in pars)
    # Parameters are mutable in C; rewrite references in this function's AST names.
    for x in self.walk(body):
      r=x.get('referencedDecl',{}); pn=r.get('name')
      if r.get('kind')=='ParmVarDecl': r['name']=pn+'__c'
    return f'(defn {z} [{args}] (-> {ret}) (let [{aliases}] (coil.control.scope :return {self.stmt(body)} {"0" if ret!="void" else "0"})))'
  def walk(self,n):
    yield n
    for x in children(n): yield from self.walk(x)
  def generate(self):
    alltop=children(self.ast)
    # Clang omits repeated file names in JSON locations.  The main-file declarations
    # form the final run beginning with the first location explicitly naming it.
    start=next((i for i,n in enumerate(alltop) if os.path.abspath((n.get('loc') or {}).get('file','/'))==self.source),len(alltop))
    top=[n for n in alltop[start:] if not n.get('isImplicit') and 'includedFrom' not in (n.get('loc') or {})]
    referenced=set()
    for n in top:
      for x in self.walk(n):
        r=x.get('referencedDecl',{})
        if r.get('kind')=='FunctionDecl': referenced.add(r.get('name'))
    header_externs=[]; external_names=set()
    for n in alltop:
      if n.get('kind')=='FunctionDecl' and not n.get('isImplicit') and n.get('name') in referenced and not any(x.get('kind')=='CompoundStmt' for x in children(n)):
        z=n.get('name')
        defined={x.get('name') for x in top if x.get('kind')=='FunctionDecl' and children(x,'CompoundStmt')}
        if z not in external_names and z not in defined and children(n,'ParmVarDecl'):
          header_externs.append(n); external_names.add(z)
    out=['(do','(module c_program)','(import "coil.primitive" :as primitive)','(import "coil.alloc" :as alloc)','(import "coil.control" :as coil.control)']
    self.enums={}
    for n in top:
      if n.get('kind')=='TypedefDecl' and n.get('name') and not n.get('isImplicit'): self.typedef[n['name']]=self.typ(n.get('type'))
      if n.get('kind')=='RecordDecl' and n.get('completeDefinition') and n.get('name'):
        self.records[n['name']]=n; out.append(f'(defstruct {name(n)} ['+' '.join(f'({name(f)} {self.typ(f.get("type"))})' for f in children(n,'FieldDecl'))+'])')
      if n.get('kind')=='EnumDecl':
        value=-1
        for e in children(n,'EnumConstantDecl'):
          cs=children(e,'ConstantExpr'); value=int(cs[0].get('value')) if cs else value+1; self.enums[name(e)]=value
      if n.get('kind')=='VarDecl' and n.get('storageClass')!='extern': self.globals[name(n)]=n
      if n.get('kind')=='FunctionDecl' and n.get('name') and not n.get('isImplicit'): self.funcs.add(name(n))
    for z,n in self.globals.items(): out.append(f'(defn __c_global_{z} [] (-> (ptr {self.typ(n.get("type"))})) (alloc/static {self.typ(n.get("type"))}))')
    seen=set()
    for n in top+header_externs:
      if n.get('kind')=='FunctionDecl' and n.get('name') and not n.get('isImplicit'):
        z=name(n); has=any(x.get('kind')=='CompoundStmt' for x in children(n))
        if has or z not in seen: out.append(self.function(n)); seen.add(z)
    out.append(')'); return '\n'.join(out)

def main():
  path=os.path.abspath(sys.argv[1]); cmd=['clang','-std=c11','-fsyntax-only','-Wno-everything','-Xclang','-ast-dump=json',path]
  p=subprocess.run(cmd,capture_output=True,text=True)
  if p.returncode: sys.stderr.write(p.stderr); return p.returncode
  try: print(Gen(json.loads(p.stdout),path).generate())
  except Error as e: sys.stderr.write('C reader: '+str(e)+'\n'); return 2
  return 0
if __name__=='__main__': raise SystemExit(main())
