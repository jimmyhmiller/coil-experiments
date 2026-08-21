#!/usr/bin/env python3
"""Translate clang's typed JSON AST to inspectable Coil (never compiles C)."""
import ast, copy, json, os, re, subprocess, sys

class Error(Exception): pass
def q(s): return '"' + s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\t','\\t') + '"'
def children(n, kind=None):
    xs=n.get('inner',[])
    return [x for x in xs if kind is None or x.get('kind')==kind]
def name(n): return re.sub(r'[^A-Za-z0-9_?!+*/<>=-]', '_', n.get('name','anon'))

class Gen:
  def __init__(self, ast, source):
    self.ast=ast; self.source=source; self.records={}; self.typedef={}; self.funcs=set(); self.defined_func_names=set(); self.globals={}; self.strings=[]; self.break_targets=[]; self.continue_targets=[]; self.current_labels={}; self.external_global_ids=set(); self.variadic_defs={}; self.variadic_specs={}; self.current_varargs=[]; self.temp_id=0
  def fresh(self,stem):
    self.temp_id+=1; return f'__c_{stem}_{self.temp_id}'
  def typ(self,t):
    s=(t or {}).get('desugaredQualType') or (t or {}).get('qualType','int'); s=re.sub(r'\b(const|volatile|restrict|_Atomic)\b','',s).strip()
    if s in self.typedef: return self.typedef[s]
    base={'void':'void','_Bool':'bool','char':'i8','signed char':'i8','unsigned char':'u8','short':'i16','short int':'i16','unsigned short':'u16','unsigned short int':'u16','int':'i32','signed int':'i32','unsigned':'u32','unsigned int':'u32','long':'i64','long int':'i64','unsigned long':'u64','unsigned long int':'u64','long long':'i64','unsigned long long':'u64','float':'f32','double':'f64','long double':'f64','int8_t':'i8','uint8_t':'u8','int16_t':'i16','uint16_t':'u16','int32_t':'i32','uint32_t':'u32','int64_t':'i64','uint64_t':'u64','intptr_t':'i64','uintptr_t':'u64','size_t':'u64','ptrdiff_t':'i64','clock_t':'i64','time_t':'i64','FILE':'i8','_IO_FILE':'i8'}
    if s in base:return base[s]
    m=re.match(r'(.+)\s*\[(\d+)\]$',s)
    if m:return f'(array {self.typ({"qualType":m.group(1)})} {m.group(2)})'
    m=re.match(r'(.+?)\s*\(\s*\*\s*\)\s*\((.*)\)$',s)
    if m:
      aa=[] if m.group(2).strip() in ('','void') else [self.typ({'qualType':x.strip()}) for x in m.group(2).split(',')]
      ret=self.typ({'qualType':m.group(1)})
      return f'(fnptr c [{" ".join(aa)}] {"i64" if ret=="void" else ret})'
    if s.endswith('*'):
      pointee=self.typ({'qualType':s[:-1].strip()})
      return f'(ptr {"i8" if pointee=="void" else pointee})'
    if s.startswith(('struct ','union ','enum ')):
      tag=s.split(' ',1)[1]
      if tag=='__va_list_tag': return 'i8'
      return name({'name':tag}) if not s.startswith('enum ') else 'i32'
    return name({'name':s})
  def cast(self,ty,x): return f'(primitive/cast {self.typ(ty)} {x})'
  def fun_name(self,n):
    z=name(n)
    return z if z=='main' or z not in self.funcs else 'c_'+z
  def direct_decl(self,n):
    cur=n
    while cur.get('kind') in ('ImplicitCastExpr','ParenExpr') and children(cur): cur=children(cur)[0]
    if cur.get('kind')=='DeclRefExpr' and cur.get('referencedDecl',{}).get('kind')=='FunctionDecl': return cur.get('referencedDecl')
    return None
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
    if k in ('ParenExpr','ExprWithCleanups'): return self.lv(ins[0])
    if k=='DeclRefExpr':
      r=n.get('referencedDecl',n); z=name(r)
      if z in self.globals: return f'(__c_global_{z})'
      if r.get('id') in self.external_global_ids:
        return f'(primitive/cast (ptr {self.typ(r.get("type"))}) (primitive/linker-address {z}))'
      return z
    if k=='UnaryOperator' and n.get('opcode')=='*': return self.expr(ins[0])
    if k=='ArraySubscriptExpr': return f'(primitive/index {self.expr(ins[0])} (primitive/cast i64 {self.expr(ins[1])}))'
    if k=='MemberExpr':
      base_type=self.typ(ins[0].get('type')); record_type=base_type[5:-1] if base_type.startswith('(ptr ') else base_type
      b=self.expr(ins[0]) if n.get('isArrow') else self.lv(ins[0])
      if record_type in self.records and self.records[record_type].get('tagUsed')=='union':
        return f'(primitive/cast (ptr {self.typ(n.get("type"))}) {b})'
      return f'(field {b} {name(n)})'
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
      x=self.expr(ins[0]); src=self.typ(ins[0].get('type')); dst=self.typ(n.get('type'))
      if dst=='void': return f'(do {x} 0)'
      if dst.startswith('(fnptr ') and src!=dst:
        storage=src if src.startswith(('(ptr ','(fnptr ')) else '(ptr i8)'
        value=x if storage==src else f'(primitive/cast {storage} {x})'
        return f'(let [p (alloc/stack {storage})] (store! p {value}) (load (primitive/cast (ptr {dst}) p)))'
      casts=('IntegralCast','FloatingCast','IntegralToFloating','FloatingToIntegral','PointerToIntegral','IntegralToPointer','BitCast','NullToPointer','IntegralToBoolean','PointerToBoolean','FloatingToBoolean')
      if dst=='bool':
        if src=='bool': return x
        if any(x.startswith('('+op+' ') for op in ('=','!=','<','>','<=','>=','and','or','not','primitive/fcmp-eq','primitive/fcmp-ne')): return x
        return f'(!= {x} (primitive/cast {src} 0))'
      if src=='bool' and dst!='bool': return self.cast(n.get('type'),f'(if {x} 1 0)')
      return self.cast(n.get('type'),x) if k=='CStyleCastExpr' or (k=='ImplicitCastExpr' and n.get('castKind') in casts) else x
    if k=='DeclRefExpr':
      r=n.get('referencedDecl',n); z=name(r)
      if r.get('kind')=='EnumConstantDecl': return str(r.get('value',self.enums.get(z,0)))
      if r.get('kind')=='FunctionDecl':
        raw=f'(primitive/fnptr-of {self.fun_name(r)})'; qt=r.get('type',{}).get('qualType','')
        if qt.strip().startswith('void (') and z not in self.defined_func_names:
          return f'(primitive/linker-address {z})'
        return raw
      return f'(load {self.lv(n)})'
    if k=='UnaryOperator':
      op=n.get('opcode'); x=ins[0]
      if op=='&': return self.lv(x)
      if op=='*': return f'(load {self.expr(x)})'
      if op=='!': return f'(not {self.truth(self.expr(x),x)})'
      if op=='~': return f'(primitive/inot {self.expr(x)})'
      if op in ('++','--','post++','post--'):
        l=self.lv(x); d=1 if '+' in op else -1; p=self.fresh('inc_ptr'); old=self.fresh('inc_old'); new=self.fresh('inc_new')
        xt=self.typ(x.get('type'))
        step=f'(primitive/index {old} {d})' if xt.startswith('(ptr ') else f'({"+" if d>0 else "-"} {old} (primitive/cast {xt} 1))'
        result=old if n.get('isPostfix') or op.startswith('post') else new
        return f'(let [{p} {l} {old} (load {p}) {new} {step}] (store! {p} {new}) {result})'
      if op=='-':
        xt=self.typ(x.get('type'))
        return f'(* {self.expr(x)} (primitive/cast {xt} -1))' if xt in ('f32','f64') else f'(- (primitive/cast {xt} 0) {self.expr(x)})'
      return self.expr(x)
    if k in ('BinaryOperator','CompoundAssignOperator'):
      op=n.get('opcode'); a=self.expr(ins[0]); b=self.expr(ins[1])
      mp={'&&':'and','||':'or','%':'primitive/irem','<<':'<<','>>':'>>','&':'&','|':'|','^':'^','==':'=','!=':'!=','<':'<','>':'>','<=':'<=','>=':'>='}
      if op=='=':
        p=self.fresh('assign_ptr'); value=self.fresh('assign_value')
        return f'(let [{p} {self.lv(ins[0])} {value} {b}] (store! {p} {value}) {value})'
      if k=='CompoundAssignOperator':
        base=op[:-1]; l=self.lv(ins[0]); at=self.typ(ins[0].get('type')); p=self.fresh('assign_ptr'); old=self.fresh('assign_old'); rhs=self.fresh('assign_rhs'); value=self.fresh('assign_value')
        ct=self.typ(n.get('computeLHSType') or ins[0].get('type'))
        calc=f'(primitive/index {old} {"(- 0 (primitive/cast i64 "+rhs+"))" if base=="-" else "(primitive/cast i64 "+rhs+")"})' if at.startswith('(ptr ') and base in ('+','-') else f'(primitive/cast {at} ({mp.get(base,base)} (primitive/cast {ct} {old}) (primitive/cast {ct} {rhs})))'
        return f'(let [{p} {l} {old} (load {p}) {rhs} {b} {value} {calc}] (store! {p} {value}) {value})'
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
        left=f'(let [p (alloc/stack {at})] (store! p {a}) (load (primitive/cast (ptr i64) p)))' if at.startswith('(fnptr ') else f'(primitive/cast i64 {a})'
        right=f'(let [p (alloc/stack {bt})] (store! p {b}) (load (primitive/cast (ptr i64) p)))' if bt.startswith('(fnptr ') else f'(primitive/cast i64 {b})'
        return self.cast(n.get('type'),f'(if ({mp[op]} {left} {right}) 1 0)')
      if op in ('==','!=') and at in ('f32','f64'):
        return self.cast(n.get('type'),f'(if ({"primitive/fcmp-eq" if op=="==" else "primitive/fcmp-ne"} {a} {b}) 1 0)')
      if op in ('==','!=','<','>','<=','>=') and (at.startswith('(ptr ') or bt.startswith('(ptr ')):
        return self.cast(n.get('type'),f'(if ({mp[op]} (primitive/cast i64 {a}) (primitive/cast i64 {b})) 1 0)')
      if op in ('==','!=','<','>','<=','>='):
        return self.cast(n.get('type'),f'(if ({mp[op]} {a} {b}) 1 0)')
      return f'({mp.get(op,op)} {a} {b})'
    if k=='ConditionalOperator': return f'(if {self.truth(self.expr(ins[0]),ins[0])} {self.expr(ins[1])} {self.expr(ins[2])})'
    if k=='ArraySubscriptExpr' or k=='MemberExpr': return f'(load {self.lv(n)})'
    if k=='CallExpr':
      cal=ins[0]; args=' '.join(self.expr(x) for x in ins[1:])
      decl=self.direct_decl(cal)
      if decl:
        z=name(decl)
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
      return f'(primitive/call-ptr {self.expr(cal)} {args})'
    if k=='InitListExpr':
      t=self.typ(n.get('type')); vals=[self.expr(x) for x in ins]
      if t.startswith('(array '): return '['+' '.join(vals)+']'
      rec=self.records.get(t)
      if rec:
        fs=children(rec,'FieldDecl'); return f'({t} '+' '.join(f':{name(f)} {v}' for f,v in zip(fs,vals))+')'
      return '(primitive/zeroed '+t+')'
    if k=='UnaryExprOrTypeTraitExpr':
      op='alignof' if n.get('name') in ('alignof','__alignof') else 'sizeof'
      arg=n.get('argType')
      if arg is None and ins: arg=ins[0].get('type')
      if arg is None: raise Error(f'{op}: missing argument type')
      return self.cast(n.get('type'),f'(primitive/{op} {self.typ(arg)})')
    if k=='GNUNullExpr': return '(primitive/cast (ptr u8) 0)'
    raise Error('unsupported expression '+str(k))
  def truth(self,x,n=None):
    if any(x.startswith('('+op+' ') for op in ('=','!=','<','>','<=','>=','and','or','not')): return x
    t=self.typ(n.get('type')) if n is not None else 'i64'
    if t=='bool': return x
    return f'(!= {x} (primitive/cast {t} 0))'
  def stmt(self,n):
    k=n.get('kind'); ins=children(n)
    if k=='CompoundStmt': return self.block(ins)
    if k=='ReturnStmt': return f'(do (coil.control.return-from :return {self.expr(ins[0]) if ins else "0"}) 0)'
    if k=='DeclStmt': raise Error('internal declaration escaped block lowering')
    if k=='IfStmt': return f'(if {self.truth(self.expr(ins[0]),ins[0])} {self.stmt(ins[1])} {self.stmt(ins[2]) if len(ins)>2 else "0"})'
    if k=='WhileStmt':
      ident=self.fresh('while'); label=f':continue-{ident}'; break_label=f':break-{ident}'; self.break_targets.append(break_label); self.continue_targets.append(label); body=self.stmt(ins[1]); self.continue_targets.pop(); self.break_targets.pop()
      return f'(coil.control.scope {break_label} (loop (when (not {self.truth(self.expr(ins[0]),ins[0])}) (break) 0) (coil.control.scope {label} {body})))'
    if k=='DoStmt':
      ident=self.fresh('do'); label=f':continue-{ident}'; break_label=f':break-{ident}'; self.break_targets.append(break_label); self.continue_targets.append(label); body=self.stmt(ins[0]); self.continue_targets.pop(); self.break_targets.pop()
      return f'(coil.control.scope {break_label} (loop (coil.control.scope {label} {body}) (when (not {self.truth(self.expr(ins[1]),ins[1])}) (break) 0)))'
    if k=='ForStmt':
      raw=n.get('inner',[]); init=raw[0] if raw and raw[0].get('kind') else None
      cond=raw[-3] if len(raw)>=3 and raw[-3].get('kind') else None
      inc=raw[-2] if len(raw)>=2 and raw[-2].get('kind') else None; body=raw[-1]
      ident=self.fresh('for'); label=f':continue-{ident}'; break_label=f':break-{ident}'; self.break_targets.append(break_label); self.continue_targets.append(label); body_code=self.stmt(body); self.continue_targets.pop(); self.break_targets.pop()
      loop=f'(coil.control.scope {break_label} (loop {f"(when (not {self.truth(self.expr(cond),cond)}) (break) 0)" if cond else ""} (coil.control.scope {label} {body_code}) {self.expr(inc) if inc else 0}))'
      if init and init.get('kind')=='DeclStmt':
        decls=children(init,'VarDecl')
        return f'(do {" ".join(y for x in decls for y in self.local_setup(x))} {loop} 0)'
      return f'(do {self.stmt(init) if init else 0} {loop} 0)'
    if k=='SwitchStmt': return self.switch_stmt(n)
    if k=='GotoStmt':
      target=n.get('targetLabelDeclId')
      if target not in self.current_labels: raise Error('goto target is not in the current function')
      return f'(coil.control.return-from {self.current_labels[target]} 0)'
    if k=='LabelStmt': return self.stmt(ins[0]) if ins else '0'
    if k=='BreakStmt':
      return f'(coil.control.return-from {self.break_targets[-1]} 0)' if self.break_targets and self.break_targets[-1].startswith(':') else '(break)'
    if k=='ContinueStmt':
      target=self.continue_targets[-1] if self.continue_targets else None
      return f'(coil.control.return-from {target} 0)' if target else '(continue)'
    if k=='NullStmt': return '0'
    return f'(do {self.expr(n)} 0)'
  def switch_labels(self,n):
    labels=[]
    cur=n
    while cur.get('kind') in ('CaseStmt','DefaultStmt'):
      xs=children(cur)
      if cur.get('kind')=='CaseStmt':
        labels.append(('case',self.expr(xs[0]))); cur=xs[1] if len(xs)>1 else None
      else:
        labels.append(('default',None)); cur=xs[0] if xs else None
      if cur is None: break
    return labels,cur
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
    matched='false' if not cases else '(or '+' '.join(f'(= __c_switch_value {v})' for v in cases)+')'
    forms=[]; label=f':switch-{getattr(self,"switch_id",0)}'; self.switch_id=getattr(self,'switch_id',0)+1
    self.break_targets.append(label)
    for (kind,case_value),body in segments:
      condition='(or (load __c_switch_active) (not __c_switch_matched))' if kind=='default' else f'(or (load __c_switch_active) (= __c_switch_value {case_value}))'
      code=self.block(body)
      forms.append(f'(when {condition} (store! __c_switch_active true) {code})')
    self.break_targets.pop()
    return f'(let [__c_switch_value {value} __c_switch_matched {matched} (mut __c_switch_active) false] (coil.control.scope {label} (do {" ".join(forms)} 0)))'
  def block(self,items):
    if not items: return '0'
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
  def local_setup(self,n):
    z=name(n); t=self.typ(n.get('type')); init=children(n)
    if not init: return []
    value=init[-1]
    if t.startswith('(array ') and value.get('kind')=='InitListExpr':
      return [f'(store! (primitive/index {z} {i}) {self.expr(v)})' for i,v in enumerate(children(value))]
    if t in self.records and value.get('kind')=='InitListExpr':
      if self.records[t].get('tagUsed')=='union':
        fields=children(self.records[t],'FieldDecl'); vals=children(value)
        return [f'(store! (primitive/cast (ptr {self.typ(fields[0].get("type"))}) {z}) {self.expr(vals[0])})'] if fields and vals else []
      return [f'(store! (field {z} {name(field)}) {self.expr(v)})' for field,v in zip(children(self.records[t],'FieldDecl'),children(value))]
    return [f'(store! {z} {self.expr(value)})']
  def global_accessor(self,z,n):
    t=self.typ(n.get('type')); init=children(n)
    if not init: return f'(defn __c_global_{z} [] (-> (ptr {t})) (alloc/static {t}))'
    value=init[-1]; setup=[]
    if t.startswith('(array ') and value.get('kind')=='InitListExpr':
      setup=[f'(store! (primitive/index cell {i}) {self.expr(v)})' for i,v in enumerate(children(value))]
    elif t in self.records and value.get('kind')=='InitListExpr':
      fields=children(self.records[t],'FieldDecl'); vals=children(value)
      setup=([f'(store! (primitive/cast (ptr {self.typ(fields[0].get("type"))}) cell) {self.expr(vals[0])})'] if fields and vals else []) if self.records[t].get('tagUsed')=='union' else [f'(store! (field cell {name(field)}) {self.expr(v)})' for field,v in zip(fields,vals)]
    else: setup=[f'(store! cell {self.expr(value)})']
    return f'(defn __c_global_{z} [] (-> (ptr {t})) (let [cell (alloc/static {t}) initialized (alloc/static bool)] (if (not (load initialized)) (do {" ".join(setup)} (store! initialized true)) 0) cell))'
  def function(self,n,vararg_types=(),special_name=None):
    z=self.fun_name(n); pars=children(n,'ParmVarDecl'); body=next((x for x in children(n) if x.get('kind')=='CompoundStmt'),None)
    if special_name: z=special_name
    qt=n.get('type',{}).get('qualType','int ()'); ret=self.typ({'qualType':qt.split('(',1)[0].strip()}); args=' '.join(f'({name(p)} {self.typ(p.get("type"))})' for p in pars)
    if vararg_types: args+=' '+' '.join(f'(__va{i} {t})' for i,t in enumerate(vararg_types))
    if body is None:
      variadic=' ...' if n.get('variadic') else ''; return f'(extern {z} :cc c [{" ".join(self.typ(p.get("type")) for p in pars)}{variadic}] (-> {ret}))'
    if ret=='void': ret='i64'
    locals=[x for x in self.walk(body) if x.get('kind')=='VarDecl']
    local_names={x.get('id'):f'{name(x)}__local_{i}' for i,x in enumerate(locals) if x.get('id')}
    for x in locals:
      if x.get('id') in local_names: x['name']=local_names[x.get('id')]
    for x in self.walk(body):
      r=x.get('referencedDecl',{}); rid=r.get('id')
      if rid in local_names: r['name']=local_names[rid]
    aliases=' '.join(f'{name(p)}__c (alloc/stack {self.typ(p.get("type"))})' for p in pars)
    aliases+=' '+' '.join(f'{name(x)} (alloc/stack {self.typ(x.get("type"))})' for x in locals)
    va_names=[f'__va{i}__c' for i in range(len(vararg_types))]
    aliases+=' '+' '.join(f'{va_names[i]} (alloc/stack {t})' for i,t in enumerate(vararg_types))
    copies=' '.join(f'(store! {name(p)}__c {name(p)})' for p in pars)
    copies+=' '+' '.join(f'(store! {va_names[i]} __va{i})' for i in range(len(vararg_types)))
    # Parameters are mutable in C; rewrite references in this function's AST names.
    for x in self.walk(body):
      r=x.get('referencedDecl',{}); pn=r.get('name')
      if r.get('kind')=='ParmVarDecl': r['name']=pn+'__c'
    previous=self.current_varargs; previous_labels=self.current_labels; self.current_varargs=va_names
    self.current_labels={x.get('declId'):f':goto-{name(x)}-{self.fresh("label")}' for x in self.walk(body) if x.get('kind')=='LabelStmt'}
    result=f'(defn {z} [{args}] (-> {ret}) (let [{aliases}] {copies} (coil.control.scope :return {self.stmt(body)} (primitive/zeroed {ret}))))'
    self.current_varargs=previous; self.current_labels=previous_labels
    return result
  def walk(self,n):
    yield n
    for x in children(n): yield from self.walk(x)
  def generate(self):
    alltop=children(self.ast)
    project_dir=os.path.dirname(self.source)+os.sep
    project_start=next((i for i,n in enumerate(alltop)
                        if ((n.get('loc') or {}).get('file') or '').startswith(project_dir)),len(alltop))
    project_decls=[]; in_project=False
    for n in alltop[project_start:]:
      explicit_file=(n.get('loc') or {}).get('file')
      if explicit_file: in_project=explicit_file.startswith(project_dir)
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
        if not x.get('name') and x.get('id') not in anonymous_names: anonymous_names[x.get('id')]=f'__c_anon_record_{len(anonymous_names)}'
    for x in project_nodes:
      if x.get('kind')=='DeclStmt':
        xs=children(x)
        for i,r in enumerate(xs):
          if r.get('kind')=='RecordDecl' and not r.get('name') and r.get('id') in anonymous_names:
            v=next((y for y in xs[i+1:] if y.get('kind')=='VarDecl'),None)
            if v:
              for spelling in ((v.get('type') or {}).get('qualType'),(v.get('type') or {}).get('desugaredQualType')):
                if spelling: self.typedef[re.sub(r'\b(const|volatile|restrict|_Atomic)\b','',spelling).strip()]=anonymous_names[r.get('id')]
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
      if n.get('kind')=='VarDecl' and n.get('storageClass')!='extern': self.globals[name(n)]=n
      if n.get('kind')=='FunctionDecl' and n.get('name') and not n.get('isImplicit'): self.funcs.add(name(n))
    self.variadic_defs={name(n):n for n in top if n.get('kind')=='FunctionDecl' and n.get('variadic') and children(n,'CompoundStmt')}
    self.defined_func_names={name(n) for n in top if n.get('kind')=='FunctionDecl' and children(n,'CompoundStmt')}
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
        if z not in external_names and z not in defined:
          header_externs.append(n); external_names.add(z)
    out=['(do','(module c_program)','(import "coil.primitive" :as primitive)','(import "coil.alloc" :as alloc)','(import "coil.control" :as coil.control)']
    out.append('(extern ffsll :cc c [i64] (-> i32))')
    out.append('(defn __c_builtin_ctzll [(x u64)] (-> i32) (let [(mut n) (primitive/cast i32 0) (mut v) x] (loop (when (!= (& (load v) (primitive/cast u64 1)) (primitive/cast u64 0)) (break) 0) (set! n (+ (load n) (primitive/cast i32 1))) (set! v (>> (load v) (primitive/cast u64 1)))) (load n)))')
    out.append('(defn __c_builtin_clzll [(x u64)] (-> i32) (let [(mut n) (primitive/cast i32 0) (mut mask) (primitive/cast u64 -9223372036854775808)] (loop (when (!= (& x (load mask)) (primitive/cast u64 0)) (break) 0) (set! n (+ (load n) (primitive/cast i32 1))) (set! mask (>> (load mask) (primitive/cast u64 1)))) (load n)))')
    emitted_records=set()
    for n in record_nodes:
      if n.get('kind')=='RecordDecl' and n.get('completeDefinition'):
        record_name=name(n) if n.get('name') else anonymous_names.get(n.get('id'))
        if record_name and record_name not in emitted_records:
          self.records[record_name]=n
          out.append(f'(defstruct {record_name} ['+' '.join(f'({name(f)} {self.typ(f.get("type"))})' for f in children(n,'FieldDecl'))+'])')
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
        if has or (z not in seen and z not in defined): out.append(self.function(n)); seen.add(z)
    for z,keys in self.variadic_specs.items():
      for key in keys: out.append(self.function(copy.deepcopy(self.variadic_defs[z]),key,self.variadic_spec_name(z,key)))
    out.append(')'); return '\n'.join(out)

def main():
  path=os.path.abspath(sys.argv[1]); cmd=['clang','-std=c11','-fsyntax-only','-Wno-everything','-Xclang','-ast-dump=json',path]
  p=subprocess.run(cmd,capture_output=True,text=True)
  if p.returncode: sys.stderr.write(p.stderr); return p.returncode
  try: print(Gen(json.loads(p.stdout),path).generate())
  except Error as e: sys.stderr.write('C reader: '+str(e)+'\n'); return 2
  return 0
if __name__=='__main__': raise SystemExit(main())
