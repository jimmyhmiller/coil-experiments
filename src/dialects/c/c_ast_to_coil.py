#!/usr/bin/env python3
"""Translate clang's typed JSON AST to inspectable Coil (never compiles C)."""
import argparse, ast, copy, json, os, re, subprocess, sys

class Error(Exception): pass
def q(s): return '"' + s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\t','\\t') + '"'
def string_value(n):
    value=n.get('value','')
    return ast.literal_eval(value) if len(value)>=2 and value[0]=='"' and value[-1]=='"' else value
def c_string_units(n):
    source=n.get('value','')
    quote=source.find('"'); source=source[quote+1:-1] if quote>=0 and source.endswith('"') else source
    out=[]; i=0; simple={'n':10,'r':13,'t':9,'a':7,'b':8,'f':12,'v':11,'\\':92,'"':34,"'":39,'?':63}
    while i<len(source):
        if source[i]!='\\': out.append(ord(source[i])); i+=1; continue
        i+=1
        if i>=len(source): break
        if source[i] in simple: out.append(simple[source[i]]); i+=1; continue
        if source[i] in '01234567':
            end=i+1
            while end<min(i+3,len(source)) and source[end] in '01234567': end+=1
            out.append(int(source[i:end],8)); i=end; continue
        if source[i]=='x':
            end=i+1
            while end<len(source) and source[end] in '0123456789abcdefABCDEF': end+=1
            out.append(int(source[i+1:end],16)); i=end; continue
        out.append(ord(source[i])); i+=1
    return out
def cq(s):
    out=[]
    for ch in s:
        value=ord(ch)
        if ch=='\\': out.append('\\\\')
        elif ch=='"': out.append('\\"')
        elif 32<=value<127: out.append(ch)
        elif value<=255: out.append(f'\\x{value:02x};')
        else: out.extend(f'\\x{byte:02x};' for byte in ch.encode())
    return '"'+''.join(out)+'"'
def children(n, kind=None):
    xs=n.get('inner',[])
    if kind is not None: return [x for x in xs if x.get('kind')==kind]
    return [x for x in xs if not x.get('kind','').endswith('Attr')]
def name(n): return re.sub(r'[^A-Za-z0-9_?!+*/<>=-]', '_', n.get('name','anon'))

class Gen:
  def __init__(self, ast, source, *, module_name='c_program', standalone=False,
               imports=None, function_targets=None, global_targets=None, owned_external_global_ids=None,
               wrap_main=True, fragment=False, anonymous_prefix='', record_names=None, project_roots=None):
    self.ast=ast; self.source=source; self.module_name=module_name; self.standalone=standalone
    self.imports=imports or {}
    self.function_targets=function_targets or {}; self.global_targets=global_targets or {}
    self.owned_external_global_ids=owned_external_global_ids; self.wrap_main=wrap_main; self.fragment=fragment; self.anonymous_prefix=anonymous_prefix
    self.record_names=record_names or {}
    self.project_roots=tuple(str(path).rstrip(os.sep)+os.sep for path in (project_roots or (os.path.dirname(source),)))
    self.source_lines=open(source).read().splitlines() if os.path.isfile(source) else []; self.records={}; self.known_record_names=set(); self.zero_record_names=set(); self.anonymous_locations={}; self.typedef={}; self.scope_types={}; self.scope_places={}; self.alignments={}; self.bitfields={}; self.vla_ids=set(); self.active_vlas=[]; self.break_cleanup_depths=[]; self.continue_cleanup_depths=[]; self.funcs=set(); self.defined_func_names=set(); self.globals={}; self.strings=[]; self.break_targets=[]; self.continue_targets=[]; self.current_labels={}; self.current_label_names={}; self.compound_places={}; self.temporary_places={}; self.external_global_ids=set(); self.variadic_defs={}; self.variadic_specs={}; self.current_varargs=[]; self.current_vararg_types=[]; self.current_va_counters={}; self.active_cleanups=[]; self.constructors=[]; self.destructors=[]; self.temp_id=0
  def fresh(self,stem):
    self.temp_id+=1; return f'__c_{stem}_{self.temp_id}'
  def typ(self,t):
    s=(t or {}).get('desugaredQualType') or (t or {}).get('qualType','int'); s=re.sub(r'\b(const|volatile|restrict|_Atomic)\b','',s).strip()
    if s.startswith('(') and s.endswith(')') and s.count('(')==1: s=s[1:-1].strip()
    s=re.sub(r'\b(__stdcall|__cdecl|__fastcall)\b','',s).strip()
    s=re.sub(r'__attribute__\s*\(\([^)]*\)\)','',s).strip()
    s=s.replace('((*))','(*)')
    if s in self.typedef: return self.typedef[s]
    if s.startswith(('typeof','__typeof')):
      identifiers=re.findall(r'\b[A-Za-z_]\w*\b',s)
      variable=next((z for z in reversed(identifiers) if z in self.scope_types),None)
      alias=next((z for z in reversed(identifiers) if z in self.typedef),None)
      builtin=next((z for z in ('long double','double','float','unsigned long long','long long','unsigned long','long','unsigned int','int','unsigned char','signed char','char') if re.search(r'\b'+re.escape(z)+r'\b',s)),None)
      if variable or alias or builtin:
        result=self.scope_types[variable] if variable else self.typedef[alias] if alias else self.typ({'qualType':builtin})
        return f'(ptr {result})' if s.endswith('*') else result
    unnamed=re.search(r'\(unnamed(?: struct)? at .*:(\d+):(\d+)\)',s)
    if unnamed:
      record=self.anonymous_locations.get((int(unnamed.group(1)),int(unnamed.group(2))))
      if record:
        suffix=s[unnamed.end():].strip()
        return self.typ({'qualType':record+suffix})
    base={'void':'void','_Bool':'bool','char':'i8','signed char':'i8','unsigned char':'u8','short':'i16','short int':'i16','unsigned short':'u16','unsigned short int':'u16','int':'i32','signed int':'i32','unsigned':'u32','unsigned int':'u32','long':'i64','long int':'i64','unsigned long':'u64','unsigned long int':'u64','long long':'i64','unsigned long long':'u64','float':'f32','double':'f64','long double':'f64','int8_t':'i8','uint8_t':'u8','int16_t':'i16','uint16_t':'u16','int32_t':'i32','uint32_t':'u32','int64_t':'i64','uint64_t':'u64','intptr_t':'i64','uintptr_t':'u64','size_t':'u64','ptrdiff_t':'i64','clock_t':'i64','time_t':'i64','atomic_flag':'atomic_flag','struct atomic_flag':'atomic_flag','FILE':'i8','_IO_FILE':'i8'}
    base.update({'pthread_t':'u64','pthread_attr_t':'(array i8 56)','union pthread_attr_t':'(array i8 56)',
                 'pthread_cond_t':'(array i8 48)','union pthread_cond_t':'(array i8 48)',
                 'pthread_condattr_t':'(array i8 4)','union pthread_condattr_t':'(array i8 4)'})
    if s in base:return base[s]
    m=re.match(r'(.+?)\s*\(\s*\*\s*\)\s*\[(\d+)\]$',s)
    if m:return f'(ptr (array {self.typ({"qualType":m.group(1)})} {m.group(2)}))'
    m=re.match(r'(.+?)\s*\(\s*\*\s*\)\s*\[\s*\]$',s)
    if m:return f'(ptr {self.typ({"qualType":m.group(1)})})'
    m=re.match(r'(.+)\s*\[(\d+)\]$',s)
    if m:
      return '__c_zero_array' if m.group(2)=='0' else f'(array {self.typ({"qualType":m.group(1)})} {m.group(2)})'
    m=re.match(r'(.+)\s*\[\s*\]$',s)
    if m:return f'(array {self.typ({"qualType":m.group(1)})} 0)'
    m=re.match(r'(.+)\s*\[([^]]+)\]$',s)
    if m:return f'(ptr {self.typ({"qualType":m.group(1)})})'
    m=re.match(r'(.+?)\s*\(\s*\*\s*\*\s*\)\s*\((.*)\)$',s)
    if m:
      params=[] if m.group(2).strip() in ('','void') else [self.typ({'qualType':x.strip()}) for x in m.group(2).split(',')]
      return f'(ptr (fnptr c [{" ".join(params)}] {self.typ({"qualType":m.group(1)})}))'
    m=re.match(r'(.+?)\s*\(\s*\*\s*\)\s*\((.*)\)$',s)
    if m:
      params=[x.strip() for x in m.group(2).split(',') if x.strip()!='...']
      aa=[] if params in ([],['void']) else [self.typ({'qualType':x}) for x in params]
      ret=self.typ({'qualType':m.group(1)})
      return f'(fnptr c [{" ".join(aa)}] {"i64" if ret=="void" else ret})'
    if s.endswith('*'):
      pointee=self.typ({'qualType':s[:-1].strip()})
      return f'(ptr {"i8" if pointee=="void" else pointee})'
    if s.startswith(('struct ','union ','enum ')):
      tag=s.split(' ',1)[1]
      if tag=='__va_list_tag': return 'i8'
      record=self.record_names.get(name({'name':tag}),name({'name':tag}))
      return ('i8' if record in self.zero_record_names else record if record in self.known_record_names else 'i8') if not s.startswith('enum ') else 'i32'
    return name({'name':s})
  def cast(self,ty,x): return f'(primitive/cast {self.typ(ty)} {x})'
  def vla_parts(self,n):
    spelling=(n.get('type') or {}).get('qualType',''); match=re.match(r'(.+)\s*\[([^]]+)\]$',spelling)
    return (self.typ({'qualType':match.group(1)}),match.group(2)) if match and not match.group(2).strip().isdigit() else None
  def vla_count(self,text):
    def lower(node):
      if isinstance(node,ast.Constant): return f'(primitive/cast i64 {node.value})'
      if isinstance(node,ast.Name):
        if node.id in self.scope_places:
          place,t=self.scope_places[node.id]; return f'(primitive/cast i64 (primitive/alias-load {t} {place}))'
        if node.id in self.globals: return f'(primitive/cast i64 {self.load(self.globals[node.id],f"(__c_global_{node.id})")})'
      if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
        def argument(x):
          if isinstance(x,ast.Name) and x.id in self.globals:
            t=self.typ(self.globals[x.id].get('type')); array=re.match(r'^\(array (.+) \d+\)$',t)
            if array:return f'(primitive/cast (ptr {array.group(1)}) (__c_global_{x.id}))'
          return lower(x)
        args=' '.join(argument(x) for x in node.args)
        return f'(primitive/cast i64 ({self.fun_name({"name":node.func.id})} {args}))'
      if isinstance(node,ast.BinOp):
        ops={ast.Add:'+',ast.Sub:'-',ast.Mult:'*',ast.Div:'/',ast.Mod:'primitive/irem'}; op=ops.get(type(node.op))
        if op:return f'({op} {lower(node.left)} {lower(node.right)})'
      raise Error('unsupported VLA bound '+text)
    return lower(ast.parse(text,mode='eval').body)
  def vla_cleanups(self,depth=0):
    return ' '.join(f'(primitive/free (primitive/cast (ptr i8) (load {place})))' for place,_ in reversed(self.active_vlas[depth:]))
  def aliasable(self,t):
    return t in ('bool','i8','u8','i16','u16','i32','u32','i64','u64','f32','f64') or t.startswith(('(ptr ','(fnptr '))
  def aliasable_node(self,n):
    if n.get('kind')=='MemberExpr':
      base=self.typ(children(n)[0].get('type'))
      record=base[5:-1] if base.startswith('(ptr ') else base
      if self.records.get(record,{}).get('tagUsed')=='union': return False
    return self.aliasable(self.typ(n.get('type')))
  def record_fields(self,n):
    return [f for f in children(n,'FieldDecl')
            if not re.search(r'\[\s*\]$',(f.get('type') or {}).get('qualType',''))
            and not (f.get('isBitfield') and not f.get('name'))]
  def load(self,n,p):
    t=self.typ(n.get('type'))
    result=f'(primitive/alias-load {t} {p})' if self.aliasable_node(n) else f'(load {p})'
    info=self.bitfields.get(n.get('referencedMemberDecl') or n.get('id'))
    if info and info[0] < {'i8':8,'u8':8,'i16':16,'u16':16,'i32':32,'u32':32,'i64':64,'u64':64}.get(t,0):
      width,signed=info; mask=(1<<width)-1; raw=f'(& {result} (primitive/cast {t} {mask}))'
      if signed:
        sign=1<<(width-1); limit=1<<width; limit=limit-(1<<64) if limit>=(1<<63) else limit
        result=f'(if (!= [i64] (primitive/cast i64 (& {raw} (primitive/cast {t} {sign}))) (primitive/cast i64 0)) (- (primitive/cast {t} {raw}) (primitive/cast {t} {limit})) (primitive/cast {t} {raw}))'
      else: result=raw
    return result
  def store(self,n,p,v):
    t=self.typ(n.get('type')); info=self.bitfields.get(n.get('referencedMemberDecl') or n.get('id'))
    if info and info[0] < {'i8':8,'u8':8,'i16':16,'u16':16,'i32':32,'u32':32,'i64':64,'u64':64}.get(t,0):
      width,signed=info; mask=(1<<width)-1; raw=f'(& (primitive/cast {t} {v}) (primitive/cast {t} {mask}))'; limit=1<<width; limit=limit-(1<<64) if limit>=(1<<63) else limit
      v=f'(if (!= [i64] (primitive/cast i64 (& {raw} (primitive/cast {t} {1<<(width-1)}))) (primitive/cast i64 0)) (- {raw} (primitive/cast {t} {limit})) {raw})' if signed else raw
    return f'(primitive/alias-store! {p} {v})' if self.aliasable_node(n) else f'(store! {p} {v})'
  def fnptr_bits(self,t,value):
    return f'(let [p (alloc/stack {t})] (store! p {value}) (load (primitive/cast (ptr i64) p)))'
  def atomic_call(self,op,t,args):
    if t.startswith('(ptr '):
      element=t[5:-1]
      names={'load':'atomic/atomic-load-ptr','store':'atomic/atomic-store-ptr','cas':'atomic/atomic-cas-ptr'}
      if op not in names: raise Error(f'unsupported pointer atomic operation {op}')
      return f'({names[op]} [{element}] {" ".join(args)})'
    is_bool=t=='bool'
    stem={'bool':'i8','i8':'i8','u8':'i8','i16':'i16','u16':'i16','i32':'i32','u32':'i32','i64':'i64','u64':'i64'}.get(t)
    if stem is None: raise Error(f'unsupported atomic type {t}')
    storage=stem
    casted=[(f'(primitive/cast {storage} (if {x} 1 0))' if is_bool else f'(primitive/cast {storage} {x})') if i else f'(primitive/cast (ptr {storage}) {x})' for i,x in enumerate(args)]
    result=f'(__c_atomic_{op}_{stem} {" ".join(casted)})'
    if is_bool and op!='store': return f'(!= [i8] {result} (primitive/cast i8 0))'
    return f'(primitive/cast {t} {result})' if t!=stem and op!='store' else result
  def fun_name(self,n):
    z=name(n)
    if z=='main' or z in self.defined_func_names: return z if z=='main' else 'c_'+z
    return self.function_targets.get(z,z)
  def direct_decl(self,n):
    cur=n
    while cur.get('kind') in ('ImplicitCastExpr','ParenExpr') and children(cur): cur=children(cur)[0]
    if cur.get('kind')=='DeclRefExpr' and cur.get('referencedDecl',{}).get('kind')=='FunctionDecl': return cur.get('referencedDecl')
    return None
  def nested_string(self,n):
    current=n
    while current.get('kind') in ('ParenExpr','ImplicitCastExpr','CStyleCastExpr') and children(current): current=children(current)[0]
    return current if current.get('kind')=='StringLiteral' else None
  def generic_selected(self,n):
    selected=next((x for x in n.get('inner',[])[1:] if x.get('selected')),None)
    selected_children=(selected or {}).get('inner',[])
    if not selected_children: raise Error('generic selection has no selected expression')
    return selected_children[-1]
  def integer_constant(self,n):
    current=n
    while current.get('kind') in ('ParenExpr','ImplicitCastExpr','ConstantExpr') and children(current): current=children(current)[0]
    if current.get('kind')=='IntegerLiteral': return int(current.get('value','0'),0)
    return None
  def is_sizeof_expr(self,n):
    current=n
    while current.get('kind') in ('ParenExpr','ImplicitCastExpr','ConstantExpr') and children(current): current=children(current)[0]
    return current.get('kind')=='UnaryExprOrTypeTraitExpr'
  def initializer_values(self,n):
    values=children(n)
    if values: return values
    filler=n.get('array_filler',[])
    return filler[1:] if filler else []
  def variadic_spec_name(self,z,key):
    keys=self.variadic_specs.setdefault(z,[])
    if key not in keys: keys.append(key)
    return f'{self.fun_name({"name":z})}__va{keys.index(key)}'
  def lit(self,n):
    v=n.get('value','0'); t=self.typ(n.get('type'))
    if t in ('f32','f64'): return f'(primitive/cast {t} {v})'
    if t=='u64' and int(v,0)>0x7fffffffffffffff: v=str(int(v,0)-(1<<64))
    return self.cast(n.get('type'),v)
  def lv(self,n):
    k=n.get('kind'); ins=children(n)
    if k in ('ParenExpr','ExprWithCleanups') or (k=='ImplicitCastExpr' and n.get('valueCategory')=='lvalue'): return self.lv(ins[0])
    if k=='MaterializeTemporaryExpr':
      place=self.temporary_places.get(n.get('id'))
      if place is None: raise Error('materialized temporary has no storage')
      return f'(do (store! {place} {self.expr(ins[0])}) {place})'
    if k=='GenericSelectionExpr': return self.lv(self.generic_selected(n))
    if k=='UnaryOperator' and n.get('opcode')=='__extension__': return self.lv(ins[0])
    if k=='PredefinedExpr' and ins: return self.lv(ins[0])
    if k=='StringLiteral': return self.expr(n)
    if k=='ConditionalOperator': return f'(if {self.truth(self.expr(ins[0]),ins[0])} {self.lv(ins[1])} {self.lv(ins[2])})'
    if k=='CompoundLiteralExpr':
      place=self.compound_places.get(n.get('id'))
      if place is None: raise Error('compound literal has no storage')
      value=next((x for x in ins if x.get('kind')=='InitListExpr'),None)
      return f'(do {" ".join(self.aggregate_setup(place,n,value))} {place})'
    if k=='DeclRefExpr':
      r=n.get('referencedDecl',n); z=name(r)
      if r.get('kind')=='FunctionDecl': return self.expr(n)
      if z in self.global_targets: return f'({self.global_targets[z]})'
      if z in self.globals: return f'(__c_global_{z})'
      if r.get('id') in self.external_global_ids:
        return f'(primitive/cast (ptr {self.typ(r.get("type"))}) (primitive/linker-address {z}))'
      return f'(load {z})' if r.get('id') in self.vla_ids else z
    if k=='UnaryOperator' and n.get('opcode')=='*': return self.expr(ins[0])
    if k=='ArraySubscriptExpr':
      base=self.expr(ins[0]); index=f'(primitive/cast i64 {self.expr(ins[1])})'; base_type=self.typ(ins[0].get('type'))
      nested=re.match(r'^\(ptr \(array (.+) (\d+)\)\)$',base_type)
      if nested:
        return f'(primitive/index (primitive/cast (ptr {nested.group(1)}) {base}) (* {index} {nested.group(2)}))'
      return f'(primitive/index {base} {index})'
    if k=='MemberExpr':
      base_type=self.typ(ins[0].get('type')); record_type=base_type[5:-1] if base_type.startswith('(ptr ') else base_type
      b=self.expr(ins[0]) if n.get('isArrow') else self.lv(ins[0])
      if record_type in self.records and self.records[record_type].get('tagUsed')=='union':
        return f'(primitive/cast (ptr {self.typ(n.get("type"))}) {b})'
      fields=self.record_fields(self.records[record_type]) if record_type in self.records else []
      if not any(name(f)==name(n) for f in fields):
        candidate=next((z for z,r in self.records.items() if any(name(f)==name(n) for f in self.record_fields(r))),None)
        if candidate: b=f'(primitive/cast (ptr {candidate}) {b})'
      return f'(field {b} {name(n)})'
    raise Error('unsupported lvalue '+str(k))
  def expr(self,n):
    k=n.get('kind'); ins=children(n)
    if k in ('IntegerLiteral','FloatingLiteral'): return self.lit(n)
    if k=='CharacterLiteral': return self.cast(n.get('type'),str(n.get('value',0)))
    if k=='StringLiteral':
      return 'c'+cq(string_value(n))
    if k in ('ParenExpr','ImplicitCastExpr','ExprWithCleanups','ConstantExpr','CStyleCastExpr','MaterializeTemporaryExpr'):
      if k=='ConstantExpr' and n.get('value') is not None:
        return self.cast(n.get('type'),str(n['value']))
      if k=='ImplicitCastExpr' and n.get('castKind')=='ArrayToPointerDecay':
        if ins[0].get('kind')=='StringLiteral': return self.cast(n.get('type'),self.expr(ins[0]))
        return self.cast(n.get('type'),self.lv(ins[0]))
      src=self.typ(ins[0].get('type')); dst=self.typ(n.get('type'))
      if dst=='void' and self.is_sizeof_expr(ins[0]): return '0'
      x=self.expr(ins[0])
      if dst=='void': return f'(do {x} 0)'
      if dst.startswith('(fnptr ') and src!=dst:
        storage=src if src.startswith(('(ptr ','(fnptr ')) else '(ptr i8)'
        value=x if storage==src else f'(primitive/cast {storage} {x})'
        return f'(let [p (alloc/stack {storage})] (store! p {value}) (load (primitive/cast (ptr {dst}) p)))'
      casts=('IntegralCast','FloatingCast','IntegralToFloating','FloatingToIntegral','PointerToIntegral','IntegralToPointer','BitCast','NullToPointer','IntegralToBoolean','PointerToBoolean','FloatingToBoolean')
      if dst=='bool':
        if src=='bool': return x
        if any(x.startswith('('+op+' ') for op in ('=','!=','<','>','<=','>=','and','or','not','primitive/fcmp-eq','primitive/fcmp-ne')): return x
        if src.startswith('(fnptr '): return f'(!= {self.fnptr_bits(src,x)} (primitive/cast i64 0))'
        return f'(!= [{src}] {x} (primitive/cast {src} 0))'
      if src=='bool' and dst!='bool': return self.cast(n.get('type'),f'(if {x} 1 0)')
      return self.cast(n.get('type'),x) if k=='CStyleCastExpr' or (k=='ImplicitCastExpr' and n.get('castKind') in casts) else x
    if k=='DeclRefExpr':
      r=n.get('referencedDecl',n); z=name(r)
      if r.get('kind')=='EnumConstantDecl': return str(r.get('value',self.enums.get(z,0)))
      if r.get('kind')=='FunctionDecl':
        raw=f'(primitive/fnptr-of {self.fun_name(r)})'; qt=r.get('type',{}).get('qualType','')
        if qt.strip().startswith('void (') and z not in self.defined_func_names and z not in self.function_targets:
          return f'(primitive/linker-address {z})'
        return raw
      return self.load(n,self.lv(n))
    if k=='UnaryOperator':
      op=n.get('opcode'); x=ins[0]
      if op=='&': return self.lv(x)
      if op=='*':
        value=self.expr(x)
        return value if self.typ(x.get('type')).startswith('(fnptr ') else self.load(n,value)
      if op=='!':
        result=f'(not {self.truth(self.expr(x),x)})'
        return result if self.typ(n.get('type'))=='bool' else self.cast(n.get('type'),f'(if {result} 1 0)')
      if op=='~': return f'(primitive/inot {self.expr(x)})'
      if op in ('++','--','post++','post--'):
        l=self.lv(x); d=1 if '+' in op else -1; p=self.fresh('inc_ptr'); old=self.fresh('inc_old'); new=self.fresh('inc_new')
        xt=self.typ(x.get('type'))
        step=f'(primitive/index {old} {d})' if xt.startswith('(ptr ') else f'({"+" if d>0 else "-"} {old} (primitive/cast {xt} 1))'
        result=old if n.get('isPostfix') or op.startswith('post') else new
        return f'(let [{p} {l} {old} {self.load(x,p)} {new} {step}] {self.store(x,p,new)} {result})'
      if op=='-':
        xt=self.typ(n.get('type')); value=self.expr(x)
        if self.typ(x.get('type'))=='bool': value=f'(if {value} 1 0)'
        return f'(* {value} (primitive/cast {xt} -1))' if xt in ('f32','f64') else f'(- (primitive/cast {xt} 0) (primitive/cast {xt} {value}))'
      return self.expr(x)
    if k in ('BinaryOperator','CompoundAssignOperator'):
      op=n.get('opcode'); a=self.expr(ins[0]); b=self.expr(ins[1])
      mp={'&&':'and','||':'or','%':'primitive/irem','<<':'<<','>>':'>>','&':'&','|':'|','^':'^','==':'=','!=':'!=','<':'<','>':'>','<=':'<=','>=':'>='}
      if op=='=':
        p=self.fresh('assign_ptr'); value=self.fresh('assign_value')
        return f'(let [{p} {self.lv(ins[0])} {value} {b}] {self.store(ins[0],p,value)} {value})'
      if k=='CompoundAssignOperator':
        base=op[:-1]; l=self.lv(ins[0]); at=self.typ(ins[0].get('type')); p=self.fresh('assign_ptr'); old=self.fresh('assign_old'); rhs=self.fresh('assign_rhs'); value=self.fresh('assign_value')
        ct=self.typ(n.get('computeLHSType') or ins[0].get('type'))
        calc=f'(primitive/index {old} {"(- 0 (primitive/cast i64 "+rhs+"))" if base=="-" else "(primitive/cast i64 "+rhs+")"})' if at.startswith('(ptr ') and base in ('+','-') else f'(primitive/cast {at} ({mp.get(base,base)} (primitive/cast {ct} {old}) (primitive/cast {ct} {rhs})))'
        return f'(let [{p} {l} {old} {self.load(ins[0],p)} {rhs} {b} {value} {calc}] {self.store(ins[0],p,value)} {value})'
      if op in ('&&','||'):
        test=f'({mp[op]} {self.truth(a,ins[0])} {self.truth(b,ins[1])})'
        return self.cast(n.get('type'),f'(if {test} 1 0)')
      if op==',': return f'(do {a} {b})'
      at=self.typ(ins[0].get('type')); bt=self.typ(ins[1].get('type'))
      if op=='+' and at.startswith('(ptr '): return f'(primitive/index {a} (primitive/cast i64 {b}))'
      if op=='+' and bt.startswith('(ptr '): return f'(primitive/index {b} (primitive/cast i64 {a}))'
      if op=='-' and at.startswith('(ptr ') and not bt.startswith('(ptr '): return f'(primitive/index {a} (- 0 (primitive/cast i64 {b})))'
      if op=='-' and at.startswith('(ptr ') and bt.startswith('(ptr '):
        pointee=at[5:-1]; return f'(/ (- (primitive/cast i64 {a}) (primitive/cast i64 {b})) (primitive/sizeof {pointee}))'
      if op=='%' and at.startswith('u'): return f'(primitive/urem {a} {b})'
      if op in ('<<','>>'): return f'({mp[op]} {a} (primitive/cast {at} {b}))'
      if op in ('==','!=') and (at.startswith('(fnptr ') or bt.startswith('(fnptr ')):
        left=self.fnptr_bits(at,a) if at.startswith('(fnptr ') else f'(primitive/cast i64 {a})'
        right=self.fnptr_bits(bt,b) if bt.startswith('(fnptr ') else f'(primitive/cast i64 {b})'
        return self.cast(n.get('type'),f'(if ({mp[op]} {left} {right}) 1 0)')
      if op in ('==','!=') and at in ('f32','f64'):
        return self.cast(n.get('type'),f'(if ({"primitive/fcmp-eq" if op=="==" else "primitive/fcmp-ne"} {a} {b}) 1 0)')
      if op in ('==','!=','<','>','<=','>=') and (at.startswith('(ptr ') or bt.startswith('(ptr ')):
        left=f'(primitive/cast i64 {a})'
        right=f'(primitive/cast i64 {b})'
        return self.cast(n.get('type'),f'(if ({mp[op]} {left} {right}) 1 0)')
      if op in ('==','!=','<','>','<=','>='):
        return self.cast(n.get('type'),f'(if ({mp[op]} (primitive/cast {at} {a}) (primitive/cast {at} {b})) 1 0)')
      return f'({mp.get(op,op)} {a} {b})'
    if k=='ConditionalOperator':
      constant=self.integer_constant(ins[0])
      if constant is not None: return self.expr(ins[1] if constant else ins[2])
      return f'(if {self.truth(self.expr(ins[0]),ins[0])} {self.expr(ins[1])} {self.expr(ins[2])})'
    if k=='GenericSelectionExpr':
      return self.expr(self.generic_selected(n))
    if k=='StmtExpr':
      body=next((x for x in ins if x.get('kind')=='CompoundStmt'),None)
      if body is None: raise Error('statement expression has no body')
      return self.block_value(children(body),self.typ(n.get('type')))
    if k=='ArraySubscriptExpr' or k=='MemberExpr': return self.load(n,self.lv(n))
    if k=='CallExpr':
      cal=ins[0]; arg_values=[self.expr(x) for x in ins[1:]]; args=' '.join(arg_values)
      decl=self.direct_decl(cal)
      if decl:
        z=name(decl)
        format_index={'printf':0,'fprintf':1,'sprintf':1,'snprintf':2}.get(z)
        if format_index is not None and format_index<len(arg_values):
          literal=self.nested_string(ins[1+format_index])
          if literal and '%L' in string_value(literal):
            arg_values[format_index]=self.cast(ins[1+format_index].get('type'),cq(string_value(literal).replace('%L','%')))
            args=' '.join(arg_values)
        if z=='write' and z not in self.defined_func_names:
          return f'(alloc/write (primitive/cast i32 {self.expr(ins[1])}) (primitive/cast (ptr i8) {self.expr(ins[2])}) (primitive/cast i64 {self.expr(ins[3])}))'
        if z in ('__builtin_nanf','__builtin_nan'):
          t=self.typ(n.get('type')); return f'(primitive/fdiv (primitive/cast {t} 0) (primitive/cast {t} 0))'
        if z=='__builtin_isnan':
          x=self.expr(ins[1]); return f'(if (primitive/fcmp-ne {x} {x}) (primitive/cast i32 1) (primitive/cast i32 0))'
        if z=='__builtin_isinf_sign':
          x=self.expr(ins[1]); return f'(if (> (fabs {x}) (primitive/cast f64 1.7976931348623157e308)) (primitive/cast i32 1) (primitive/cast i32 0))'
        if z in ('__builtin_memcpy','__builtin_memmove'): return f'({z[10:]} {args})'
        if z in ('__builtin_ctz','__builtin_ctzl','__builtin_ctzll'): return f'(- (ffsll (primitive/cast i64 {self.expr(ins[1])})) (primitive/cast i32 1))'
        if z in ('__builtin_clz','__builtin_clzl','__builtin_clzll'): return f'(__c_builtin_clzll (primitive/cast u64 {self.expr(ins[1])}))'
        if z=='__builtin_expect': return self.expr(ins[1])
        if z in ('__builtin_va_start','__builtin_va_end'): return '0'
        if z in ('vfprintf','vprintf','vsprintf','vsnprintf') and self.current_varargs:
          fixed=ins[1:-1]; base=z[1:]
          return f'({base} {" ".join(self.expr(x) for x in fixed)} {" ".join(f"(load {v})" for v in self.current_varargs)})'
        if z in self.variadic_defs:
          fixed=len(children(self.variadic_defs[z],'ParmVarDecl')); key=tuple(self.typ(x.get('type')) for x in ins[1+fixed:])
          return f'({self.variadic_spec_name(z,key)} {args})'
        return f'({self.fun_name(decl)} {args})'
      callee=self.expr(cal)
      cal_spelling=(cal.get('type') or {}).get('qualType','')
      if '...' in cal_spelling or (re.search(r'\(\s*\*\s*\)\s*\(\s*\)$',cal_spelling) and len(ins)>1):
        arg_types=' '.join(self.typ(x.get('type')) for x in ins[1:]); ret=self.typ(n.get('type'))
        target=f'(fnptr c [{arg_types}] {"i64" if ret=="void" else ret})'; source=self.typ(cal.get('type'))
        callee=f'(let [p (alloc/stack {source})] (store! p {callee}) (load (primitive/cast (ptr {target}) p)))'
      return f'(primitive/call-ptr {callee} {args})'
    if k=='AtomicExpr':
      op=n.get('name'); values=[self.expr(x) for x in ins]
      load_ops=('__c11_atomic_load','__atomic_load_n')
      store_ops=('__c11_atomic_init','__c11_atomic_store','__atomic_store_n')
      if op in load_ops:
        t=self.typ(n.get('type')); return self.atomic_call('load',t,values[:1])
      if op in store_ops:
        t=self.typ(ins[-1].get('type')); return f'(do {self.atomic_call("store",t,[values[0],values[-1]])} 0)'
      if op in ('__c11_atomic_fetch_add','__atomic_fetch_add'):
        t=self.typ(n.get('type')); return self.atomic_call('add',t,[values[0],values[-1]])
      if op in ('__c11_atomic_exchange','__atomic_exchange_n'):
        t=self.typ(n.get('type')); return self.atomic_call('xchg',t,[values[0],values[-1]])
      if op in ('__c11_atomic_compare_exchange_strong','__c11_atomic_compare_exchange_weak','__atomic_compare_exchange_n'):
        desired_index=len(ins)-2 if op=='__atomic_compare_exchange_n' else len(ins)-1
        t=self.typ(ins[desired_index].get('type')); expected_ptr=values[2]
        expected_node=children(ins[2])[0] if ins[2].get('kind')=='UnaryOperator' and children(ins[2]) else ins[2]
        expected=self.load(expected_node,expected_ptr)
        observed=self.atomic_call('cas',t,[values[0],expected,values[desired_index]])
        return f'(let [__c_expected {expected} __c_observed {observed} __c_success (= __c_observed __c_expected)] (if __c_success 0 {self.store(expected_node,expected_ptr,"__c_observed")}) __c_success)'
      raise Error('unsupported atomic expression '+str(op))
    if k=='InitListExpr':
      t=self.typ(n.get('type')); vals=[self.expr(x) for x in self.initializer_values(n)]
      array=re.match(r'^\(array (.+) (\d+)\)$',t)
      if array:
        vals += [f'(primitive/zeroed {array.group(1)})']*(int(array.group(2))-len(vals))
        return '['+' '.join(vals)+']'
      rec=self.records.get(t)
      if rec:
        fs=self.record_fields(rec); return f'({t} '+' '.join(f':{name(f)} {v}' for f,v in zip(fs,vals))+')'
      return '(primitive/zeroed '+t+')'
    if k=='CompoundLiteralExpr':
      if n.get('id') in self.compound_places: return self.load(n,self.lv(n))
      value=next((x for x in ins if x.get('kind')=='InitListExpr'),None)
      if value is None: return f'(primitive/zeroed {self.typ(n.get("type"))})'
      return self.expr(value)
    if k=='ImplicitValueInitExpr': return f'(primitive/zeroed {self.typ(n.get("type"))})'
    if k=='VAArgExpr':
      wanted=self.typ(n.get('type'))
      matches=[v for v,t in zip(self.current_varargs,self.current_vararg_types) if t==wanted]
      if not matches: return f'(primitive/zeroed {wanted})'
      counter=self.current_va_counters[wanted]
      selected=f'(load {matches[-1]})'
      for i,place in reversed(list(enumerate(matches[:-1]))): selected=f'(if (= __c_va_index (primitive/cast i64 {i})) (load {place}) {selected})'
      return f'(let [__c_va_index (load {counter})] (store! {counter} (+ __c_va_index (primitive/cast i64 1))) {selected})'
    if k=='UnaryExprOrTypeTraitExpr':
      op='alignof' if n.get('name') in ('alignof','__alignof') else 'sizeof'
      arg=n.get('argType')
      if arg is None and ins: arg=ins[0].get('type')
      if arg is None: raise Error(f'{op}: missing argument type')
      if op=='alignof' and ins:
        target=ins[0]
        while target.get('kind') in ('ParenExpr','ImplicitCastExpr') and children(target): target=children(target)[0]
        referenced=target.get('referencedDecl',{})
        if referenced.get('name') in self.alignments: return self.cast(n.get('type'),str(self.alignments[referenced['name']]))
      return self.cast(n.get('type'),f'(primitive/{op} {self.typ(arg)})')
    if k=='GNUNullExpr': return '(primitive/cast (ptr u8) 0)'
    if k=='AddrLabelExpr':
      target=self.current_label_names.get(n.get('name'))
      if target is None: raise Error('address of unknown label '+str(n.get('name')))
      return f'(primitive/cast (ptr i8) {target[0]})'
    raise Error('unsupported expression '+str(k))
  def truth(self,x,n=None):
    if any(x.startswith('('+op+' ') for op in ('=','!=','<','>','<=','>=','and','or','not')): return x
    t=self.typ(n.get('type')) if n is not None else 'i64'
    if t=='bool': return x
    if t.startswith('(fnptr '): return f'(!= [i64] {self.fnptr_bits(t,x)} (primitive/cast i64 0))'
    return f'(!= [{t}] (primitive/cast {t} {x}) (primitive/cast {t} 0))'
  def stmt(self,n):
    k=n.get('kind'); ins=children(n)
    if k=='CompoundStmt': return self.block(ins)
    if k=='ReturnStmt':
      cleanups=' '.join(f'({fun} {place})' for fun,place in reversed(self.active_cleanups))
      return f'(do {cleanups} {self.vla_cleanups()} (coil.control.return-from :return {self.expr(ins[0]) if ins else "0"}) 0)'
    if k=='DeclStmt': raise Error('internal declaration escaped block lowering')
    if k=='IfStmt': return f'(if {self.truth(self.expr(ins[0]),ins[0])} {self.stmt(ins[1])} {self.stmt(ins[2]) if len(ins)>2 else "0"})'
    if k=='WhileStmt':
      ident=self.fresh('while'); label=f':continue-{ident}'; break_label=f':break-{ident}'; depth=len(self.active_vlas); self.break_targets.append(break_label); self.continue_targets.append(label); self.break_cleanup_depths.append(depth); self.continue_cleanup_depths.append(depth); body=self.stmt(ins[1]); self.continue_cleanup_depths.pop(); self.break_cleanup_depths.pop(); self.continue_targets.pop(); self.break_targets.pop()
      return f'(coil.control.scope {break_label} (loop (when (not {self.truth(self.expr(ins[0]),ins[0])}) (break) 0) (coil.control.scope {label} {body})))'
    if k=='DoStmt':
      ident=self.fresh('do'); label=f':continue-{ident}'; break_label=f':break-{ident}'; depth=len(self.active_vlas); self.break_targets.append(break_label); self.continue_targets.append(label); self.break_cleanup_depths.append(depth); self.continue_cleanup_depths.append(depth); body=self.stmt(ins[0]); self.continue_cleanup_depths.pop(); self.break_cleanup_depths.pop(); self.continue_targets.pop(); self.break_targets.pop()
      return f'(coil.control.scope {break_label} (loop (coil.control.scope {label} {body}) (when (not {self.truth(self.expr(ins[1]),ins[1])}) (break) 0)))'
    if k=='ForStmt':
      raw=n.get('inner',[]); init=raw[0] if raw and raw[0].get('kind') else None
      cond=raw[-3] if len(raw)>=3 and raw[-3].get('kind') else None
      inc=raw[-2] if len(raw)>=2 and raw[-2].get('kind') else None; body=raw[-1]
      ident=self.fresh('for'); label=f':continue-{ident}'; break_label=f':break-{ident}'; depth=len(self.active_vlas); self.break_targets.append(break_label); self.continue_targets.append(label); self.break_cleanup_depths.append(depth); self.continue_cleanup_depths.append(depth); body_code=self.stmt(body); self.continue_cleanup_depths.pop(); self.break_cleanup_depths.pop(); self.continue_targets.pop(); self.break_targets.pop()
      loop=f'(coil.control.scope {break_label} (loop {f"(when (not {self.truth(self.expr(cond),cond)}) (break) 0)" if cond else ""} (coil.control.scope {label} {body_code}) {self.expr(inc) if inc else 0}))'
      if init and init.get('kind')=='DeclStmt':
        decls=children(init,'VarDecl')
        return f'(do {" ".join(y for x in decls for y in self.local_setup(x))} {loop} 0)'
      return f'(do {self.stmt(init) if init else 0} {loop} 0)'
    if k=='SwitchStmt': return self.switch_stmt(n)
    if k=='GotoStmt':
      target=n.get('targetLabelDeclId')
      if target not in self.current_labels: raise Error('goto target is not in the current function')
      return f'(do {self.vla_cleanups()} (coil.control.return-from {self.current_labels[target]} 0))'
    if k=='IndirectGotoStmt':
      target=ins[0] if ins else {}
      while target.get('kind') in ('ParenExpr','ImplicitCastExpr') and children(target): target=children(target)[0]
      if target.get('kind')=='AddrLabelExpr' and target.get('name') in self.current_label_names:
        return f'(coil.control.return-from {self.current_label_names[target.get("name")][1]} 0)'
      raise Error('computed goto target is not statically known')
    if k=='LabelStmt': return self.stmt(ins[0]) if ins else '0'
    if k=='BreakStmt':
      cleanup=self.vla_cleanups(self.break_cleanup_depths[-1] if self.break_cleanup_depths else 0)
      jump=f'(coil.control.return-from {self.break_targets[-1]} 0)' if self.break_targets and self.break_targets[-1].startswith(':') else '(break)'
      return f'(do {cleanup} {jump})'
    if k=='ContinueStmt':
      target=self.continue_targets[-1] if self.continue_targets else None
      cleanup=self.vla_cleanups(self.continue_cleanup_depths[-1] if self.continue_cleanup_depths else 0); jump=f'(coil.control.return-from {target} 0)' if target else '(continue)'
      return f'(do {cleanup} {jump})'
    if k=='NullStmt': return '0'
    return f'(do {self.expr(n)} 0)'
  def switch_labels(self,n):
    labels=[]
    cur=n
    while cur.get('kind') in ('CaseStmt','DefaultStmt'):
      xs=children(cur)
      if cur.get('kind')=='CaseStmt':
        if cur.get('isGNURange'):
          labels.append(('case',(self.expr(xs[0]),self.expr(xs[1])))); cur=xs[2] if len(xs)>2 else None
        else:
          labels.append(('case',self.expr(xs[0]))); cur=xs[1] if len(xs)>1 else None
      else:
        labels.append(('default',None)); cur=xs[0] if xs else None
      if cur is None: break
    return labels,cur
  def switch_match(self,value):
    if isinstance(value,tuple):
      return f'(and (<= {value[0]} __c_switch_value) (<= __c_switch_value {value[1]}))'
    return f'(= __c_switch_value {value})'
  def switch_stmt(self,n):
    ins=children(n); value=self.expr(ins[0]); items=children(ins[1])
    segments=[]; current=None
    for item in items:
      if item.get('kind') in ('CaseStmt','DefaultStmt'):
        labels,first=self.switch_labels(item)
        for label in labels:
          current=[label,[]]; segments.append(current)
        if first is not None: current[1].append(first)
      elif current is not None:
        current[1].append(item)
    cases=[v for ((kind,v),_) in segments if kind=='case']
    matched='false' if not cases else '(or '+' '.join(self.switch_match(v) for v in cases)+')'
    forms=[]; label=f':switch-{getattr(self,"switch_id",0)}'; self.switch_id=getattr(self,'switch_id',0)+1
    self.break_targets.append(label)
    for (kind,case_value),body in segments:
      condition='(or (load __c_switch_active) (not __c_switch_matched))' if kind=='default' else f'(or (load __c_switch_active) {self.switch_match(case_value)})'
      code=self.block(body)
      forms.append(f'(when {condition} (store! __c_switch_active true) {code})')
    self.break_targets.pop()
    sequence=' '.join(forms)
    for i,(_,body) in enumerate(segments):
      for labelled in (x for item in body for x in self.walk(item) if x.get('kind')=='LabelStmt'):
        decl=labelled.get('declId'); target=self.current_labels.get(decl)
        if target and any(x.get('kind')=='GotoStmt' and x.get('targetLabelDeclId')==decl for _,prior in segments[:i] for item in prior for x in self.walk(item)):
          sequence=f'(coil.control.scope {target} (do {" ".join(forms[:i])} 0)) '+ ' '.join(forms[i:])
    return f'(let [__c_switch_value {value} __c_switch_matched {matched} (mut __c_switch_active) false] (coil.control.scope {label} (do {sequence} 0)))'
  def block_value(self,items,result_type):
    if not items: return '(primitive/zeroed '+result_type+')'
    head,*tail=items
    if head.get('kind')=='DeclStmt':
      setup=[y for x in children(head,'VarDecl') for y in self.local_setup(x)]
      return f'(do {" ".join(setup)} {self.block_value(tail,result_type)})'
    if not tail:
      return self.stmt(head) if result_type=='void' else self.expr(head)
    return f'(do {self.stmt(head)} {self.block_value(tail,result_type)})'
  def block(self,items):
    if not items: return '0'
    if not any(item.get('kind')=='LabelStmt' for item in items):
      for outer_index,item in enumerate(items):
        labels=[x for x in self.walk(item) if x.get('kind')=='LabelStmt']
        if len(labels)!=1 or not children(labels[0]) or children(labels[0])[0].get('kind')!='NullStmt': continue
        label=labels[0]; target=self.current_labels.get(label.get('declId'))
        if target and any(x.get('kind')=='GotoStmt' and x.get('targetLabelDeclId')==label.get('declId') for suffix in items[outer_index+1:] for x in self.walk(suffix)):
          break_target=f':goto-break-{self.fresh("label")}'
          body=self.block(items[outer_index+1:])
          return f'(do {self.block(items[:outer_index+1])} (coil.control.scope {break_target} (loop (coil.control.scope {target} (do {body} (coil.control.return-from {break_target} 0))))))'
      for outer_index,item in enumerate(items):
        labels=[x for x in self.walk(item) if x.get('kind')=='LabelStmt']
        if len(labels)!=1 or not children(labels[0]): continue
        label=labels[0]; target=self.current_labels.get(label.get('declId'))
        if target and any(x.get('kind')=='GotoStmt' and x.get('targetLabelDeclId')==label.get('declId') for suffix in items[outer_index+1:] for x in self.walk(suffix)):
          break_target=f':goto-break-{self.fresh("label")}'; suffix=self.block(items[outer_index+1:]); labelled=self.stmt(children(label)[0])
          return f'(do {self.block(items[:outer_index])} (coil.control.scope {break_target} (do (coil.control.scope {target} (do {suffix} (coil.control.return-from {break_target} 0))) (loop (coil.control.scope {target} (do {labelled} {suffix} (coil.control.return-from {break_target} 0)))))))'
      for outer_index,item in enumerate(items):
        if item.get('kind')!='CompoundStmt': continue
        nested=children(item)
        label_index=next((i for i,x in enumerate(nested) if x.get('kind')=='LabelStmt'),None)
        if label_index is None: continue
        label=nested[label_index]; target=self.current_labels.get(label.get('declId'))
        if target and any(x.get('kind')=='GotoStmt' and x.get('targetLabelDeclId')==label.get('declId') for prefix in items[:outer_index] for x in self.walk(prefix)):
          labelled=children(label); target_body=(labelled[:1] if labelled else [])+nested[label_index+1:]
          return f'(do (coil.control.scope {target} {self.block(items[:outer_index])}) {self.block(target_body)} {self.block(items[outer_index+1:])})'
      forms=[]; cleanup_base=len(self.active_cleanups); vla_base=len(self.active_vlas)
      for item in items:
        if item.get('kind')=='DeclStmt':
          for x in children(item,'VarDecl'):
            forms.extend(self.local_setup(x))
            if self.vla_parts(x): self.active_vlas.append((name(x),self.vla_save_names[x.get('id')]))
            attr=next((a for a in x.get('inner',[]) if a.get('kind')=='CleanupAttr'),None)
            if attr:
              cleanup=attr.get('cleanup_function',{})
              self.active_cleanups.append((self.fun_name(cleanup),name(x)))
        else: forms.append(self.stmt(item))
      forms.extend(f'({fun} {place})' for fun,place in reversed(self.active_cleanups[cleanup_base:]))
      forms.append(self.vla_cleanups(vla_base))
      del self.active_cleanups[cleanup_base:]
      del self.active_vlas[vla_base:]
      return f'(do {" ".join(forms)} 0)'
    head,*tail=items
    if head.get('kind')=='DeclStmt':
      decls=children(head,'VarDecl'); setup=[]
      for d in decls:
        setup += self.local_setup(d)
      return f'(do {" ".join(setup)} {self.block(tail)})'
    for i,label in enumerate(items):
      if label.get('kind')!='LabelStmt': continue
      decl=label.get('declId')
      if any(x.get('kind')=='GotoStmt' and x.get('targetLabelDeclId')==decl for item in items[i+1:] for x in self.walk(item)):
        target=self.current_labels[decl]; break_target=f':goto-break-{self.fresh("label")}'
        labelled=children(label); body=(labelled[:1] if labelled else [])+items[i+1:]
        return f'(do (coil.control.scope {target} {self.block(items[:i])}) (coil.control.scope {break_target} (loop (coil.control.scope {target} (do {self.block(body)} (coil.control.return-from {break_target} 0))))))'
    label_index=next((i for i in range(len(items)-1,-1,-1) if items[i].get('kind')=='LabelStmt'),None)
    if label_index is not None:
      label=items[label_index]; target=self.current_labels.get(label.get('declId'))
      if target is None: raise Error('label is not registered in the current function')
      labelled=children(label)
      suffix=(labelled[:1] if labelled else [])+items[label_index+1:]
      return f'(do (coil.control.scope {target} {self.block(items[:label_index])}) {self.block(suffix)})'
    return f'(do {self.stmt(head)} {self.block(tail)})'
  def local(self,n):
    return f'{name(n)} (alloc/stack {self.typ(n.get("type"))})'
  def string_array_setup(self,place,t,value):
    match=re.match(r'^\(array (i8|u8|i32|u32) (\d+)\)$',t)
    if match is None: return None
    element=match.group(1); capacity=int(match.group(2)); units=c_string_units(value)+[0]
    units=(units+[0]*capacity)[:capacity]
    return [f'(store! (primitive/index {place} {i}) (primitive/cast {element} {unit if not element.startswith("i") or unit<128 else unit-256 if element=="i8" else unit}))' for i,unit in enumerate(units)]
  def aggregate_setup(self,place,n,value):
    if value is None: return []
    t=self.typ(n.get('type'))
    if value.get('kind')=='StringLiteral':
      return self.string_array_setup(place,t,value) or []
    if value.get('kind')!='InitListExpr': return [self.store(n,place,self.expr(value))]
    vals=self.initializer_values(value)
    if t.startswith('(array '):
      return [f'(store! (primitive/index {place} {i}) {self.expr(v)})' for i,v in enumerate(vals)]
    if t in self.records:
      fields=self.record_fields(self.records[t])
      if self.records[t].get('tagUsed')=='union':
        return [f'(store! (primitive/cast (ptr {self.typ(fields[0].get("type"))}) {place}) {self.expr(vals[0])})'] if fields and vals else []
      return [form for field,v in zip(fields,vals) for form in self.aggregate_setup(f'(field {place} {name(field)})',field,v)]
    return []
  def local_setup(self,n):
    if n.get('storageClass')=='static': return []
    z=name(n); t=self.typ(n.get('type')); init=children(n)
    vla=self.vla_parts(n)
    if vla:
      element,bound=vla; size=f'(* {self.vla_count(bound)} (primitive/cast i64 (primitive/sizeof {element})))'
      save=self.vla_save_names[n.get('id')]
      return [f'(store! {z} (primitive/cast (ptr {element}) (alloc/malloc {size})))']
    if not init: return []
    value=init[-1]
    string_setup=self.string_array_setup(z,t,value) if value.get('kind')=='StringLiteral' else None
    if string_setup is not None: return string_setup
    if t.startswith('(array ') and value.get('kind')=='InitListExpr':
      return [f'(store! (primitive/index {z} {i}) {self.expr(v)})' for i,v in enumerate(self.initializer_values(value))]
    if t in self.records and value.get('kind')=='InitListExpr':
      return self.aggregate_setup(z,n,value)
    return [f'(store! {z} {self.expr(value)})']
  def global_accessor(self,z,n):
    t=self.typ(n.get('type')); init=children(n)
    if not init: return f'(defn __c_global_{z} [] (-> (ptr {t})) (alloc/static {t}))'
    value=init[-1]; setup=[]
    string_setup=self.string_array_setup('cell',t,value) if value.get('kind')=='StringLiteral' else None
    if string_setup is not None:
      setup=string_setup
    elif t.startswith('(array ') and value.get('kind')=='InitListExpr':
      setup=[f'(store! (primitive/index cell {i}) {self.expr(v)})' for i,v in enumerate(self.initializer_values(value))]
    elif t in self.records and value.get('kind')=='InitListExpr':
      setup=self.aggregate_setup('cell',n,value)
    else: setup=[f'(store! cell {self.expr(value)})']
    return f'(defn __c_global_{z} [] (-> (ptr {t})) (let [cell (alloc/static {t}) initialized (alloc/static bool)] (if (not (load initialized)) (do (store! initialized true) {" ".join(setup)} 0) 0) cell))'
  def function(self,n,vararg_types=(),special_name=None):
    z=self.fun_name(n); pars=children(n,'ParmVarDecl'); body=next((x for x in children(n) if x.get('kind')=='CompoundStmt'),None)
    if special_name: z=special_name
    previous_scope_types=self.scope_types; self.scope_types={name(p):self.typ(p.get('type')) for p in pars}
    if body is not None:
      for x in self.walk(body):
        spelling=(x.get('type') or {}).get('qualType','')
        if x.get('kind')=='VarDecl' and not spelling.startswith(('typeof','__typeof')): self.scope_types[name(x)]=self.typ(x.get('type'))
    attrs={x.get('kind') for x in n.get('inner',[]) if x.get('kind','').endswith('Attr')}
    self_recursive=body is not None and any(x.get('kind')=='DeclRefExpr' and name(x.get('referencedDecl',{}))==name(n) for x in self.walk(body))
    small_static=body is not None and n.get('storageClass')=='static' and sum(1 for _ in self.walk(n))<=128 and not self_recursive
    inline=' :inline (Always)' if 'AlwaysInlineAttr' in attrs or small_static else (' :inline (Hint)' if 'InlineAttr' in attrs else '')
    function_type=n.get('type',{}); qt=function_type.get('desugaredQualType') or function_type.get('qualType','int ()'); ret=self.typ({'qualType':qt.split('(',1)[0].strip()})
    canonical_text=qt[qt.find('(')+1:qt.rfind(')')].strip()
    canonical=[] if canonical_text in ('','void') else [self.typ({'qualType':x.strip()}) for x in canonical_text.split(',')]
    abi_types=canonical if len(canonical)==len(pars) else [self.typ(p.get('type')) for p in pars]
    args=' '.join(f'({name(p)} {abi_types[i]})' for i,p in enumerate(pars))
    if vararg_types: args+=' '+' '.join(f'(__va{i} {t})' for i,t in enumerate(vararg_types))
    if body is None:
      variadic=' ...' if n.get('variadic') else ''; result=f'(extern {z} :cc c [{" ".join(self.typ(p.get("type")) for p in pars)}{variadic}] (-> {"i64" if ret=="void" else ret}))'; self.scope_types=previous_scope_types; return result
    if ret=='void': ret='i64'
    locals=[x for x in self.walk(body) if x.get('kind')=='VarDecl' and x.get('storageClass')!='static']
    compounds=[x for x in self.walk(body) if x.get('kind')=='CompoundLiteralExpr']
    temporaries=[x for x in self.walk(body) if x.get('kind')=='MaterializeTemporaryExpr']
    original_local_names={x.get('id'):name(x) for x in locals if x.get('id')}
    local_names={x.get('id'):f'{name(x)}__local_{i}' for i,x in enumerate(locals) if x.get('id')}
    for x in locals:
      if x.get('id') in local_names: x['name']=local_names[x.get('id')]
    for x in self.walk(body):
      r=x.get('referencedDecl',{}); rid=r.get('id')
      if rid in local_names: r['name']=local_names[rid]
    previous_scope_places=self.scope_places; previous_vla_ids=self.vla_ids; previous_vla_save_names=getattr(self,'vla_save_names',{})
    self.scope_places={name(p):(f'{name(p)}__c',self.typ(p.get('type'))) for p in pars}
    self.scope_places.update({original_local_names[x.get('id')]:(name(x),self.typ(x.get('type'))) for x in locals if x.get('id')})
    self.vla_ids={x.get('id') for x in locals if self.vla_parts(x)}
    self.vla_save_names={x.get('id'):f'{name(x)}__stack' for x in locals if x.get('id') in self.vla_ids}
    aliases=' '.join(f'{name(p)}__c (alloc/stack {self.typ(p.get("type"))})' for p in pars)
    aliases+=' '+' '.join(f'{name(x)} (alloc/stack {self.typ(x.get("type"))})' for x in locals)
    aliases+=' '+' '.join(f'{save} (alloc/stack (ptr i8))' for save in self.vla_save_names.values())
    previous_compounds=self.compound_places; self.compound_places={x.get('id'):f'__c_compound_{i}' for i,x in enumerate(compounds)}
    aliases+=' '+' '.join(f'{self.compound_places[x.get("id")]} (alloc/stack {self.typ(x.get("type"))})' for x in compounds)
    previous_temporaries=self.temporary_places; self.temporary_places={x.get('id'):f'__c_temporary_{i}' for i,x in enumerate(temporaries)}
    aliases+=' '+' '.join(f'{self.temporary_places[x.get("id")]} (alloc/stack {self.typ(x.get("type"))})' for x in temporaries)
    va_names=[f'__va{i}__c' for i in range(len(vararg_types))]
    aliases+=' '+' '.join(f'{va_names[i]} (alloc/stack {t})' for i,t in enumerate(vararg_types))
    va_counter_names={t:f'__c_va_counter_{i}' for i,t in enumerate(dict.fromkeys(vararg_types))}
    aliases+=' '+' '.join(f'{counter} (alloc/stack i64)' for counter in va_counter_names.values())
    copy_values=[name(p) if abi_types[i]==self.typ(p.get('type')) else self.cast(p.get('type'),name(p)) for i,p in enumerate(pars)]
    copies=' '.join(f'(store! {name(p)}__c {copy_values[i]})' for i,p in enumerate(pars))
    copies+=' '+' '.join(f'(store! {va_names[i]} __va{i})' for i in range(len(vararg_types)))
    copies+=' '+' '.join(f'(store! {counter} (primitive/cast i64 0))' for counter in va_counter_names.values())
    # Parameters are mutable in C; rewrite references in this function's AST names.
    for x in self.walk(body):
      r=x.get('referencedDecl',{}); pn=r.get('name')
      if r.get('kind')=='ParmVarDecl': r['name']=pn+'__c'
    previous=self.current_varargs; previous_vararg_types=self.current_vararg_types; previous_va_counters=self.current_va_counters; previous_labels=self.current_labels; previous_label_names=self.current_label_names
    self.current_varargs=va_names; self.current_vararg_types=list(vararg_types); self.current_va_counters=va_counter_names
    self.current_labels={x.get('declId'):f':goto-{name(x)}-{self.fresh("label")}' for x in self.walk(body) if x.get('kind')=='LabelStmt'}
    self.current_label_names={name(x):(i+1,self.current_labels[x.get('declId')]) for i,x in enumerate(self.walk(body)) if x.get('kind')=='LabelStmt'}
    body_code=f'(coil.control.scope :return {self.stmt(body)} (primitive/zeroed {ret}))'
    if z=='main' and self.wrap_main:
      before=' '.join(f'({f})' for f in self.constructors)
      after=' '.join(f'({f})' for f in reversed(self.destructors))
      body_code=f'(do {before} (let [__c_main_result {body_code}] {after} __c_main_result))'
    result=f'(defn {z}{inline} [{args}] (-> {ret}) (let [{aliases}] {copies} {body_code}))'
    self.current_varargs=previous; self.current_vararg_types=previous_vararg_types; self.current_va_counters=previous_va_counters; self.current_labels=previous_labels; self.current_label_names=previous_label_names
    self.compound_places=previous_compounds
    self.temporary_places=previous_temporaries
    self.scope_types=previous_scope_types
    self.scope_places=previous_scope_places; self.vla_ids=previous_vla_ids; self.vla_save_names=previous_vla_save_names
    return result
  def walk(self,n):
    stack=[n]
    while stack:
      current=stack.pop(); yield current
      stack.extend(reversed(children(current)))
  def generate(self):
    alltop=children(self.ast)
    for n in alltop:
      if n.get('kind')!='TypedefDecl' or not n.get('name'): continue
      builtin=next((x for x in children(n) if x.get('kind')=='BuiltinType'),None)
      if builtin is not None: self.typedef[n['name']]=self.typ(builtin.get('type'))
    typeofs=[n for n in self.walk(self.ast) if n.get('kind')=='TypeOfExprType' and children(n)]
    for n in reversed(typeofs):
      spelling=(n.get('type') or {}).get('qualType')
      if spelling: self.typedef[spelling]=self.typ(children(n)[-1].get('type'))
    project_start=next((i for i,n in enumerate(alltop)
                        if ((n.get('loc') or {}).get('file') or '').startswith(self.project_roots)),len(alltop))
    project_decls=[]; in_project=False
    for n in alltop[project_start:]:
      explicit_file=(n.get('loc') or {}).get('file')
      if explicit_file: in_project=explicit_file.startswith(self.project_roots)
      if in_project: project_decls.append(n)
    anonymous_names={}
    for n in project_decls:
      if n.get('kind')=='TypedefDecl' and n.get('name'):
        for x in children(n):
          owned=x.get('ownedTagDecl') or {}
          if owned.get('kind')=='RecordDecl' and not owned.get('name'): anonymous_names[owned.get('id')]=name(n)
    # Every declaration physically originating in the project participates. This
    # also makes a deliberately amalgamated entry a whole C program while retaining
    # header-defined inline functions and excluding libc implementation records.
    top=[n for n in project_decls if not n.get('isImplicit')]
    project_nodes=[x for n in top for x in self.walk(n)]
    record_nodes=[]; record_ids=set()
    for x in project_nodes:
      if x.get('kind')=='RecordDecl' and x.get('completeDefinition') and x.get('id') not in record_ids:
        record_nodes.append(x); record_ids.add(x.get('id'))
        if not x.get('name') and x.get('id') not in anonymous_names: anonymous_names[x.get('id')]=f'__c_anon_record_{self.anonymous_prefix}{len(anonymous_names)}'
    for x in project_nodes:
      if x.get('kind')=='DeclStmt':
        xs=children(x)
        for i,r in enumerate(xs):
          if r.get('kind')=='RecordDecl' and not r.get('name') and r.get('id') in anonymous_names:
            v=next((y for y in xs[i+1:] if y.get('kind')=='VarDecl'),None)
            if v:
              for spelling in ((v.get('type') or {}).get('qualType'),(v.get('type') or {}).get('desugaredQualType')):
                if spelling:
                  cleaned=re.sub(r'\s*\[\d*\]\s*$','',re.sub(r'\b(const|volatile|restrict|_Atomic)\b','',spelling).strip())
                  self.typedef[cleaned]=anonymous_names[r.get('id')]
    self.known_record_names={self.record_names.get(name(x),name(x)) if x.get('name') else anonymous_names.get(x.get('id')) for x in record_nodes}
    self.known_record_names.discard(None)
    self.zero_record_names={self.record_names.get(name(x),name(x)) for x in record_nodes if x.get('name') and not children(x,'FieldDecl')}
    for x in project_nodes:
      if x.get('kind')=='FieldDecl' and x.get('isBitfield'):
        width=next((int(y.get('value')) for y in children(x) if y.get('value') is not None),None)
        spelling=(x.get('type') or {}).get('qualType','')
        signed='unsigned' not in spelling and not spelling.startswith('enum ') and self.typ(x.get('type'))!='bool'
        if width is not None: self.bitfields[x.get('id')]=(width,signed)
    self.enums={}
    for n in project_nodes:
      if n.get('kind')=='TypedefDecl' and n.get('name') and not n.get('isImplicit'):
        for x in children(n):
          owned=x.get('ownedTagDecl') or {}
          if owned.get('kind')=='RecordDecl' and owned.get('id') in anonymous_names: self.typedef[n['name']]=anonymous_names[owned.get('id')]
        owns_enum=any((x.get('ownedTagDecl') or {}).get('kind')=='EnumDecl' for x in children(n))
        if n['name'] not in self.typedef:
          underlying={'qualType':(n.get('type') or {}).get('qualType','int')}
          self.typedef[n['name']]='i32' if owns_enum else self.typ(underlying)
      if n.get('kind')=='EnumDecl':
        value=-1
        for e in children(n,'EnumConstantDecl'):
          cs=children(e,'ConstantExpr'); value=int(cs[0].get('value')) if cs else value+1; self.enums[name(e)]=value
    for n in top:
      if n.get('kind')=='VarDecl' and (n.get('storageClass')!='extern' or children(n)):
        z=name(n)
        if n.get('storageClass')=='static' or self.owned_external_global_ids is None or n.get('id') in self.owned_external_global_ids:
          self.globals[z]=n
      if n.get('kind')=='FunctionDecl' and n.get('name') and not n.get('isImplicit'): self.funcs.add(name(n))
      if n.get('kind')=='VarDecl':
        attr=next((x for x in n.get('inner',[]) if x.get('kind')=='AlignedAttr'),None)
        if attr:
          value=next((x.get('value') for x in children(attr) if x.get('value') is not None),None)
          line=(n.get('loc') or {}).get('line',0); text=self.source_lines[line-1] if 0<line<=len(self.source_lines) else ''
          if value is not None: self.alignments[n.get('name')]=int(value)
          elif re.search(r'aligned\s*\(\s*16\s*\)',text): self.alignments[n.get('name')]=16
          elif re.search(r'_Alignas\s*\(\s*double\s*\)',text): self.alignments[n.get('name')]=8
          else: self.alignments[n.get('name')]=4
    static_index=0
    for function in (n for n in top if n.get('kind')=='FunctionDecl'):
      body=next((x for x in children(function) if x.get('kind')=='CompoundStmt'),None)
      if body is None: continue
      statics=[x for x in self.walk(body) if x.get('kind')=='VarDecl' and x.get('storageClass')=='static']
      for static in statics:
        original_id=static.get('id'); static_index+=1
        static_name=f'__c_static_{name(function)}_{name(static)}_{static_index}'
        static['name']=static_name; self.globals[static_name]=static
        for x in self.walk(body):
          referenced=x.get('referencedDecl',{})
          if original_id and referenced.get('id')==original_id: referenced['name']=static_name
    self.variadic_defs={name(n):n for n in top if n.get('kind')=='FunctionDecl' and n.get('variadic') and children(n,'CompoundStmt')}
    self.defined_func_names={name(n) for n in top if n.get('kind')=='FunctionDecl' and children(n,'CompoundStmt')}
    self.constructors=[self.fun_name(n) for n in top if n.get('kind')=='FunctionDecl' and any(x.get('kind')=='ConstructorAttr' for x in n.get('inner',[]))]
    self.destructors=[self.fun_name(n) for n in top if n.get('kind')=='FunctionDecl' and any(x.get('kind')=='DestructorAttr' for x in n.get('inner',[]))]
    referenced=set()
    for n in top:
      for x in self.walk(n):
        r=x.get('referencedDecl',{})
        if r.get('kind')=='FunctionDecl': referenced.add(r.get('name'))
        if x.get('kind')=='CallExpr' and children(x):
          decl=self.direct_decl(children(x)[0]); z=name(decl) if decl else ''
          if z in self.variadic_defs:
            fixed=len(children(self.variadic_defs[z],'ParmVarDecl'))
            self.variadic_spec_name(z,tuple(self.typ(a.get('type')) for a in children(x)[1+fixed:]))
          if z in ('vfprintf','vprintf','vsprintf','vsnprintf'): referenced.add(z[1:])
          if z in ('__builtin_memcpy','__builtin_memmove'): referenced.add(z[10:])
    header_externs=[]; external_names=set()
    for n in alltop:
      if n.get('kind')=='FunctionDecl' and not n.get('isImplicit') and n.get('name') in referenced and not any(x.get('kind')=='CompoundStmt' for x in children(n)):
        z=n.get('name')
        defined={x.get('name') for x in top if x.get('kind')=='FunctionDecl' and children(x,'CompoundStmt')}
        if z not in self.function_targets and z not in external_names and z not in defined:
          header_externs.append(n); external_names.add(z)
    for n in project_nodes:
      if n.get('kind')=='FunctionDecl' and not n.get('isImplicit') and n.get('name') in referenced and not children(n,'CompoundStmt'):
        z=n.get('name')
        if z not in self.function_targets and z not in external_names and z not in self.defined_func_names:
          header_externs.append(n); external_names.add(z)
    out=[] if self.standalone else ['(do']
    out += [f'(module {self.module_name})','(import "coil.primitive" :as primitive)','(import "coil.alloc" :as alloc)','(import "coil.control" :as coil.control)','(import "coil.atomic" :as atomic)']
    out += [f'(import {q(module)} :as {alias})' for alias,module in sorted(self.imports.items())]
    out += ['(defstruct __c_zero_array [])','(defstruct atomic_flag [(_Value bool)])']
    for bits,align in ((8,1),(16,2),(32,4),(64,8)):
      t=f'i{bits}'
      out.append(f'(defn __c_atomic_load_{t} [(p (ptr {t}))] (-> {t}) (primitive/llvm-ir {t} [p] "%v = load atomic {t}, ptr $0 seq_cst, align {align}\\nret {t} %v"))')
      out.append(f'(defn __c_atomic_store_{t} [(p (ptr {t})) (v {t})] (-> i64) (primitive/llvm-ir i64 [p v] "store atomic {t} $1, ptr $0 seq_cst, align {align}\\nret i64 0"))')
      for op,llvm_op in (('add','add'),('xchg','xchg')):
        out.append(f'(defn __c_atomic_{op}_{t} [(p (ptr {t})) (v {t})] (-> {t}) (primitive/llvm-ir {t} [p v] "%old = atomicrmw {llvm_op} ptr $0, {t} $1 seq_cst\\nret {t} %old"))')
      out.append(f'(defn __c_atomic_cas_{t} [(p (ptr {t})) (expected {t}) (desired {t})] (-> {t}) (primitive/llvm-ir {t} [p expected desired] "%r = cmpxchg ptr $0, {t} $1, {t} $2 seq_cst seq_cst\\n%v = extractvalue {{ {t}, i1 }} %r, 0\\nret {t} %v"))')
    out.append('(extern ffsll :cc c [i64] (-> i32))')
    out.append('(defn __c_builtin_ctzll [(x u64)] (-> i32) (let [(mut n) (primitive/cast i32 0) (mut v) x] (loop (when (!= (& (load v) (primitive/cast u64 1)) (primitive/cast u64 0)) (break) 0) (set! n (+ (load n) (primitive/cast i32 1))) (set! v (>> (load v) (primitive/cast u64 1)))) (load n)))')
    out.append('(defn __c_builtin_clzll [(x u64)] (-> i32) (let [(mut n) (primitive/cast i32 0) (mut mask) (primitive/cast u64 -9223372036854775808)] (loop (when (!= (& x (load mask)) (primitive/cast u64 0)) (break) 0) (set! n (+ (load n) (primitive/cast i32 1))) (set! mask (>> (load mask) (primitive/cast u64 1)))) (load n)))')
    declarations_start=len(out)
    emitted_records=set()
    for n in record_nodes:
      if n.get('kind')=='RecordDecl' and n.get('completeDefinition'):
        record_name=self.record_names.get(name(n),name(n)) if n.get('name') else anonymous_names.get(n.get('id'))
        if record_name:
          if record_name in self.zero_record_names: continue
          if record_name in emitted_records: record_name=f'{record_name}__{len(emitted_records)}'
          location=n.get('loc') or {}
          if not n.get('name') and location.get('line') and location.get('col'):
            self.anonymous_locations[(location['line'],location['col'])]=record_name
          self.records[record_name]=n
          out.append(f'(defstruct {record_name} ['+' '.join(f'({name(f)} {self.typ(f.get("type"))})' for f in self.record_fields(n))+'])')
          emitted_records.add(record_name)
    referenced_global_ids={x.get('referencedDecl',{}).get('id') for n in top for x in self.walk(n) if x.get('referencedDecl',{}).get('kind')=='VarDecl'}
    project_global_ids={n.get('id') for n in top if n.get('kind')=='VarDecl'}
    external_top_ids={n.get('id') for n in alltop if n.get('kind')=='VarDecl'}-project_global_ids
    self.external_global_ids={x for x in referenced_global_ids & external_top_ids if x}
    for z,n in self.globals.items(): out.append(self.global_accessor(z,n))
    seen=set(); defined={name(n) for n in top if n.get('kind')=='FunctionDecl' and children(n,'CompoundStmt')}
    for n in top+header_externs:
      if n.get('kind')=='FunctionDecl' and n.get('name') and not n.get('isImplicit'):
        z=name(n); has=any(x.get('kind')=='CompoundStmt' for x in children(n))
        if has and z in self.variadic_defs: continue
        if not has and z in self.function_targets: continue
        if z=='write' and not has: continue
        if has or (z not in seen and z not in defined): out.append(self.function(n)); seen.add(z)
    for z,keys in self.variadic_specs.items():
      for key in keys: out.append(self.function(copy.deepcopy(self.variadic_defs[z]),key,self.variadic_spec_name(z,key)))
    if self.fragment: out=out[declarations_start:]
    elif not self.standalone: out.append(')')
    return '\n'.join(out)

def load_ast(path, clang_args=()):
  command=['clang','-std=gnu11','-fsyntax-only','-Wno-everything',*clang_args,'-Xclang','-ast-dump=json',path]
  process=subprocess.run(command,capture_output=True,text=True)
  if process.returncode: raise Error(process.stderr.strip() or f'clang exited {process.returncode}')
  return json.loads(process.stdout)

def main():
  parser=argparse.ArgumentParser(description=__doc__)
  parser.add_argument('source'); parser.add_argument('--module',default='c_program')
  parser.add_argument('--standalone',action='store_true')
  args=parser.parse_args(); path=os.path.abspath(args.source)
  try: print(Gen(load_ast(path),path,module_name=args.module,standalone=args.standalone).generate())
  except Error as e: sys.stderr.write('C reader: '+str(e)+'\n'); return 2
  return 0
if __name__=='__main__': raise SystemExit(main())
