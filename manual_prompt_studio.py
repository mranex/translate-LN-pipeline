#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import copy, json, re, shutil, sys, datetime as dt
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from tkinter.scrolledtext import ScrolledText

APP='Manual Prompt Studio v2'
D={'bg':'#14161b','p':'#282c37','e':'#101217','fg':'#e8eaf0','m':'#a7adba','a':'#7db1ff','s':'#33415c','b':'#3a4050','d':'#57313a','ok':'#2f5132'}

def pretty(o): return json.dumps(o,ensure_ascii=False,indent=2)
def compact(v,n=120):
    s='' if v is None else (json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else str(v))
    s=s.replace('\n',' ').strip(); return s if len(s)<=n else s[:n-1]+'…'
def read_json(p:Path,default=None):
    if not p.exists(): return copy.deepcopy(default)
    return json.loads(p.read_text(encoding='utf-8'))
def write_json(p:Path,o): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(pretty(o)+'\n',encoding='utf-8')
def read_jsonl(p:Path):
    if not p.exists(): return []
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
def write_jsonl(p:Path,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+'\n')
def backup(p:Path):
    if p.exists(): shutil.copy2(p,p.with_suffix(p.suffix+'.'+dt.datetime.now().strftime('%Y%m%d_%H%M%S')+'.bak'))
def result(row): return row.get('result') if isinstance(row.get('result'),dict) else row
def iid(row):
    r=result(row); return str(row.get('item_id') or r.get('item_id') or r.get('segment') or '')
def contains(o,q):
    if not q: return True
    try: s=json.dumps(o,ensure_ascii=False).lower()
    except Exception: s=str(o).lower()
    return q.lower() in s
def strip_fences(t):
    t=t.strip()
    if t.startswith('```'):
        t=re.sub(r'^```(?:json)?\s*','',t)
        t=re.sub(r'\s*```$','',t)
    return t.strip()
def parse_json_response(t):
    t=strip_fences(t)
    try:
        o=json.loads(t)
        if not isinstance(o,dict): raise ValueError('Top-level JSON must be an object.')
        return o
    except Exception:
        a=t.find('{'); b=t.rfind('}')
        if a>=0 and b>a:
            o=json.loads(t[a:b+1])
            if not isinstance(o,dict): raise ValueError('Top-level JSON must be an object.')
            return o
        raise
def item_id_from_record(rec):
    return str(rec.get('segment') or f"c{int(rec.get('chapter',0)):03d}")

def setup(root):
    root.configure(bg=D['bg']); st=ttk.Style(root)
    try: st.theme_use('clam')
    except tk.TclError: pass
    st.configure('.',background=D['bg'],foreground=D['fg'],fieldbackground=D['e'])
    st.configure('TFrame',background=D['bg']); st.configure('TLabel',background=D['bg'],foreground=D['fg'])
    st.configure('Muted.TLabel',background=D['bg'],foreground=D['m'])
    st.configure('TButton',background=D['p'],foreground=D['fg'],padding=(8,5)); st.map('TButton',background=[('active',D['s'])])
    st.configure('Accent.TButton',background=D['a'],foreground='#101217'); st.configure('Danger.TButton',background=D['d'],foreground=D['fg']); st.configure('Ok.TButton',background=D['ok'],foreground=D['fg'])
    st.configure('TEntry',fieldbackground=D['e'],foreground=D['fg'],insertcolor=D['fg'])
    st.configure('TNotebook',background=D['bg'],borderwidth=0); st.configure('TNotebook.Tab',background=D['p'],foreground=D['fg'],padding=(12,7)); st.map('TNotebook.Tab',background=[('selected',D['s'])])
    st.configure('Treeview',background=D['e'],fieldbackground=D['e'],foreground=D['fg'],rowheight=24); st.map('Treeview',background=[('selected',D['s'])],foreground=[('selected',D['fg'])])
    st.configure('Treeview.Heading',background=D['p'],foreground=D['fg'],relief='flat')

class WS:
    def __init__(self,root,project_name): 
        self.root=Path(root)
        self.project_name=project_name
    def p(self,*x): return self.root.joinpath('data',self.project_name,*x)
    def config_path(self): return self.p('project_config.json')
    def load_config(self): return read_json(self.config_path(), {'name':self.project_name, 'genre':'', 'level':'Heavy', 'enabled_steps':[]})
    def save_config(self, cfg): write_json(self.config_path(), cfg)
    def load_prompt(self,name): return self.root.joinpath('prompts',name).read_text(encoding='utf-8')
    def render(self,name,input_obj):
        base=self.load_prompt(name)
        jp=self.load_prompt('00_json_output_policy.txt') if self.root.joinpath('prompts','00_json_output_policy.txt').exists() else ''
        genre=self.load_config().get('genre','')
        return base.replace('{{JSON_OUTPUT_POLICY}}',jp).replace('{{INPUT_JSON}}',pretty(input_obj)).replace('{{genre}}',genre)
    def source(self,v): return self.p('source',f'volume_{v:02d}.json')
    def segs(self,v): return self.p('segments',f'volume_{v:02d}.segments.json')
    def chapters(self,v):
        d=read_json(self.source(v),[])
        return d.get('chapters',[]) if isinstance(d,dict) else d
    def segments(self,v):
        d=read_json(self.segs(v),[])
        return d.get('segments',[]) if isinstance(d,dict) else d
    def g_draft(self,v): return self.p('canon','glossary','drafts',f'volume_{v:02d}.glossary.draft.json')
    def g_final(self,v): return self.p('canon','glossary','finalized',f'volume_{v:02d}.glossary.json')
    def r_draft(self,v): return self.p('canon','relationships','drafts',f'volume_{v:02d}.relationships.draft.json')
    def r_final(self,v): return self.p('canon','relationships','finalized',f'volume_{v:02d}.relationships.json')
    def ge(self,v): return self.p('working','glossary_extractions',f'volume_{v:02d}.glossary_extractions.jsonl')
    def re(self,v): return self.p('working','relationship_extractions',f'volume_{v:02d}.relationships_extractions.jsonl')
    def sg(self,v): return self.p('working','segment_glossaries',f'volume_{v:02d}.segment_glossaries.jsonl')
    def sp(self,v): return self.p('canon','segment_pronouns',f'volume_{v:02d}.segment_pronouns.jsonl')
    def sc(self,v): return self.p('working','segment_contexts',f'volume_{v:02d}.segment_contexts.jsonl')
    def dl(self,v): return self.p('working','dialogue_labels',f'volume_{v:02d}.dialogue_labels.jsonl')
    def tr(self,v): return self.p('working','translations','draft',f'volume_{v:02d}.translated.jsonl')
    def qa(self,v): return self.p('working','translations','qa',f'volume_{v:02d}.qa.jsonl')
    def fx(self,v): return self.p('working','translations','fixed',f'volume_{v:02d}.fixed.jsonl')
    def rel_json(self,v): return self.p('release',f'volume_{v:02d}.vi.json')
    def rel_md(self,v): return self.p('release',f'volume_{v:02d}.vi.md')
    def map_jsonl(self,p): return {iid(r):r for r in read_jsonl(p)}

class Step:
    def __init__(self,id,label,scope,prompt=None,build=None,importer=None,local=None,desc=''):
        self.id=id; self.label=label; self.scope=scope; self.prompt=prompt; self.build=build; self.importer=importer; self.local=local; self.desc=desc

class Tab(ttk.Frame):
    def __init__(self,master,title,get_items,dirty,cols,can_add=False,template=None):
        super().__init__(master); self.get_items=get_items; self.dirty=dirty; self.cols=cols; self.can_add=can_add; self.template=template; self.cur=None
        self.columnconfigure(0,weight=1); self.rowconfigure(1,weight=1)
        bar=ttk.Frame(self); bar.grid(row=0,column=0,sticky='ew',padx=8,pady=(8,4)); bar.columnconfigure(1,weight=1)
        ttk.Label(bar,text=title,style='Muted.TLabel').grid(row=0,column=0,padx=(0,8)); self.q=tk.StringVar(); self.q.trace_add('write',lambda *_:self.refresh())
        ttk.Entry(bar,textvariable=self.q).grid(row=0,column=1,sticky='ew',padx=(0,8))
        ttk.Button(bar,text='Add',command=self.add).grid(row=0,column=2,padx=2); ttk.Button(bar,text='Duplicate',command=self.dup).grid(row=0,column=3,padx=2)
        ttk.Button(bar,text='Delete',style='Danger.TButton',command=self.delete).grid(row=0,column=4,padx=2); ttk.Button(bar,text='Refresh',command=self.refresh).grid(row=0,column=5,padx=2)
        pane=ttk.PanedWindow(self,orient=tk.HORIZONTAL); pane.grid(row=1,column=0,sticky='nsew',padx=8,pady=(4,8))
        left=ttk.Frame(pane); left.rowconfigure(0,weight=1); left.columnconfigure(0,weight=1)
        self.tree=ttk.Treeview(left,columns=[c[0] for c in cols],show='headings',selectmode='browse')
        for k,l,w,_ in cols: self.tree.heading(k,text=l); self.tree.column(k,width=w,minwidth=60,stretch=True)
        self.tree.grid(row=0,column=0,sticky='nsew'); y=ttk.Scrollbar(left,orient='vertical',command=self.tree.yview); y.grid(row=0,column=1,sticky='ns'); self.tree.configure(yscrollcommand=y.set); self.tree.bind('<<TreeviewSelect>>',self.sel)
        right=ttk.Frame(pane); right.rowconfigure(1,weight=1); right.columnconfigure(0,weight=1)
        rb=ttk.Frame(right); rb.grid(row=0,column=0,sticky='ew',pady=(0,4)); rb.columnconfigure(0,weight=1); self.label=ttk.Label(rb,text='No item selected',style='Muted.TLabel'); self.label.grid(row=0,column=0,sticky='w')
        ttk.Button(rb,text='Format JSON',command=self.fmt).grid(row=0,column=1,padx=2); ttk.Button(rb,text='Apply',style='Accent.TButton',command=self.apply).grid(row=0,column=2,padx=2)
        self.ed=ScrolledText(right,wrap=tk.NONE,undo=True,bg=D['e'],fg=D['fg'],insertbackground=D['fg'],selectbackground=D['s'],borderwidth=0,highlightthickness=1,highlightbackground=D['b'],font=('Consolas',11)); self.ed.grid(row=1,column=0,sticky='nsew')
        pane.add(left,weight=4); pane.add(right,weight=4)
    def refresh(self):
        self.tree.delete(*self.tree.get_children()); q=self.q.get().strip(); first=None
        items=self.get_items()
        old_cur_str = str(self.cur) if self.cur is not None else None
        for i,it in enumerate(items):
            if not contains(it,q): continue
            vals=[]
            for _,_,_,fn in self.cols:
                try: vals.append(compact(fn(it),140))
                except Exception: vals.append('')
            self.tree.insert('', 'end', iid=str(i), values=vals); first=first or str(i)
        if old_cur_str is not None and self.tree.exists(old_cur_str):
            self.tree.selection_set(old_cur_str); self.load(int(old_cur_str))
        elif first is not None: self.tree.selection_set(first); self.load(int(first))
        else: self.cur=None; self.ed.delete('1.0',tk.END); self.label.config(text='No item selected')
    def sel(self,_=None):
        s=self.tree.selection()
        if s: self.load(int(s[0]))
    def load(self,i):
        items=self.get_items()
        if not 0<=i<len(items): return
        self.cur=i; self.ed.delete('1.0',tk.END); self.ed.insert('1.0',pretty(items[i])); self.label.config(text=f'Editing index {i}')
    def fmt(self):
        try: o=json.loads(self.ed.get('1.0',tk.END).strip())
        except Exception as e: messagebox.showerror(APP,f'Invalid JSON:\n{e}'); return
        self.ed.delete('1.0',tk.END); self.ed.insert('1.0',pretty(o))
    def apply(self):
        if self.cur is None: return
        try: o=json.loads(self.ed.get('1.0',tk.END).strip())
        except Exception as e: messagebox.showerror(APP,f'Invalid JSON:\n{e}'); return
        self.get_items()[self.cur]=o; self.dirty(); self.refresh()
    def add(self):
        if not self.can_add or not self.template: messagebox.showinfo(APP,'Add is disabled for this tab.'); return
        self.get_items().append(self.template()); self.dirty(); self.refresh()
    def dup(self):
        if self.cur is None: return
        self.get_items().append(copy.deepcopy(self.get_items()[self.cur])); self.dirty(); self.refresh()
    def delete(self):
        if self.cur is None: return
        if not messagebox.askyesno(APP,f'Delete index {self.cur}?'): return
        del self.get_items()[self.cur]; self.dirty(); self.refresh()

class TranslationsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.rowconfigure(1, weight=1); self.columnconfigure(0, weight=1); self.columnconfigure(1, weight=2)
        left = ttk.Frame(self); left.grid(row=0, column=0, rowspan=2, sticky='nsew', padx=4, pady=4)
        left.rowconfigure(1, weight=1); left.columnconfigure(0, weight=1)
        ttk.Label(left, text='Segments').grid(row=0, column=0, sticky='w')
        self.listbox = tk.Listbox(left, bg=D['e'], fg=D['fg'], selectbackground=D['s'], font=('Consolas', 10))
        self.listbox.grid(row=1, column=0, sticky='nsew')
        self.listbox.bind('<<ListboxSelect>>', self.on_select)
        right = ttk.Frame(self); right.grid(row=0, column=1, rowspan=2, sticky='nsew', padx=4, pady=4)
        right.rowconfigure(1, weight=1); right.columnconfigure(0, weight=1)
        bar = ttk.Frame(right); bar.grid(row=0, column=0, sticky='ew')
        ttk.Button(bar, text='Save Translation', command=self.save_translation).pack(side='left', padx=2)
        ttk.Button(bar, text='Quick Fix (AI)', style='Accent.TButton', command=self.quick_fix).pack(side='left', padx=2)
        self.ed = ScrolledText(right, wrap=tk.WORD, undo=True, bg=D['e'], fg=D['fg'], insertbackground=D['fg'], selectbackground=D['s'], font=('Segoe UI', 11))
        self.ed.grid(row=1, column=0, sticky='nsew')
        self.items = []; self.cur_id = None
    def refresh(self):
        self.listbox.delete(0, tk.END); self.items = []
        if not self.app.current: return
        vol = self.app.vol()
        draft = self.app.jsonl_map(self.app.ws.tr(vol))
        fixed = self.app.jsonl_map(self.app.ws.fx(vol))
        segs = self.app.ws.segments(vol)
        for seg in segs:
            sid = str(seg.get('segment'))
            txt = (result(fixed.get(sid, {})).get('fixed_translation') or result(fixed.get(sid, {})).get('translation') or result(draft.get(sid, {})).get('translation') or '')
            self.items.append((sid, txt))
            self.listbox.insert(tk.END, sid + (' (*)' if txt else ''))
    def on_select(self, e):
        sel = self.listbox.curselection()
        if not sel: return
        self.cur_id, txt = self.items[sel[0]]
        self.ed.delete('1.0', tk.END)
        self.ed.insert('1.0', txt)
    def save_translation(self):
        if not self.cur_id: return
        txt = self.ed.get('1.0', tk.END).strip()
        self.app.imp_fix({'item_id': self.cur_id, 'fixed_translation': txt})
        self.refresh()
        messagebox.showinfo(APP, 'Saved to fixed translations.')
    def quick_fix(self):
        if not self.cur_id: return
        try:
            sel_first = self.ed.index(tk.SEL_FIRST)
            sel_last = self.ed.index(tk.SEL_LAST)
            highlighted = self.ed.get(sel_first, sel_last).strip()
        except tk.TclError: messagebox.showerror(APP, 'Please highlight text to Quick Fix.'); return
        if not highlighted: return
        instruction = simpledialog.askstring('Quick Fix', 'Enter instruction (e.g. "make it more aggressive"):')
        if not instruction: return
        vol = self.app.vol()
        seg_data = next((s for s in self.app.ws.segments(vol) if str(s.get('segment')) == self.cur_id), {})
        dl = result(self.app.jsonl_map(self.app.ws.dl(vol)).get(self.cur_id, {}))
        input_json = {'source_context': dl.get('labeled_source') or seg_data.get('content'), 'highlighted_translation_to_fix': highlighted, 'instruction': instruction}
        base = self.app.ws.load_prompt('12_quick_fix.txt')
        jp = self.app.ws.load_prompt('00_json_output_policy.txt') if self.app.ws.root.joinpath('prompts','00_json_output_policy.txt').exists() else ''
        genre = self.app.load_config().get('genre','')
        pr = base.replace('{{JSON_OUTPUT_POLICY}}', jp).replace('{{INPUT_JSON}}', pretty(input_json)).replace('{{genre}}', genre)
        self.app.current_quick_fix_data = {'item_id': self.cur_id, 'sel_first': sel_first, 'sel_last': sel_last, 'highlighted': highlighted}
        self.app.prompt.config(state=tk.NORMAL)
        self.app.prompt.delete('1.0', tk.END)
        self.app.prompt.insert('1.0', pr)
        self.app.prompt.config(state=tk.DISABLED)
        self.app.response.delete('1.0', tk.END)
        self.app.clipboard_clear(); self.app.clipboard_append(pr)
        messagebox.showinfo('Quick Fix', 'Prompt copied to clipboard. Paste response in the Response box and click Process Response.')

class App(tk.Tk):
    def __init__(self,root_dir, project_name):
        super().__init__(); setup(self); self.title(APP + f' - {project_name}'); self.geometry('1600x920'); self.minsize(1200,720)
        self.ws=WS(root_dir, project_name); self.current=None; self.data={}; self.dirty=set()
        self.config=self.ws.load_config()
        self.build_ui(); self.build_steps(); self.bind('<Control-s>',lambda _e:self.save_all()); self.bind('<Control-r>',lambda _e:self.reload())
        self.protocol('WM_DELETE_WINDOW',self.exit)
        self.tree.after(100, self.reload)
    def vol(self): return self.current.get('volume') if self.current else None
    def build_ui(self):
        self.rowconfigure(1,weight=1); self.columnconfigure(0,weight=1)
        top=ttk.Frame(self); top.grid(row=0,column=0,sticky='ew',padx=10,pady=(8,4)); top.columnconfigure(1,weight=1)
        ttk.Label(top,text=APP,font=('Segoe UI',14,'bold')).grid(row=0,column=0,sticky='w'); self.root_label=ttk.Label(top,text=str(self.ws.root),style='Muted.TLabel'); self.root_label.grid(row=0,column=1,sticky='w',padx=12)
        ttk.Button(top,text='Open Root',command=self.open_root).grid(row=0,column=2,padx=3); ttk.Button(top,text='Reload',command=self.reload).grid(row=0,column=3,padx=3)
        ttk.Button(top,text='Save Editors',style='Accent.TButton',command=self.save_all).grid(row=0,column=4,padx=3); ttk.Button(top,text='Approve Glossary',command=self.approve_g).grid(row=0,column=5,padx=3); ttk.Button(top,text='Approve Relationships',command=self.approve_r).grid(row=0,column=6,padx=3)
        main=ttk.PanedWindow(self,orient=tk.HORIZONTAL); main.grid(row=1,column=0,sticky='nsew',padx=10,pady=4)
        left=ttk.Frame(main); left.rowconfigure(1,weight=1); left.columnconfigure(0,weight=1); ttk.Label(left,text='Project Tree',style='Muted.TLabel').grid(row=0,column=0,sticky='w',padx=8,pady=(8,4))
        self.tree=ttk.Treeview(left,show='tree'); self.tree.grid(row=1,column=0,sticky='nsew',padx=8,pady=(4,8)); y=ttk.Scrollbar(left,orient='vertical',command=self.tree.yview); y.grid(row=1,column=1,sticky='ns'); self.tree.configure(yscrollcommand=y.set); self.tree.bind('<<TreeviewSelect>>',self.on_tree)
        center=ttk.PanedWindow(main,orient=tk.VERTICAL)
        ct=ttk.Frame(center); ct.columnconfigure(1,weight=1); ct.rowconfigure(1,weight=1); ct.rowconfigure(3,weight=1)
        ttk.Label(ct,text='Available Steps',style='Muted.TLabel').grid(row=0,column=0,sticky='w',padx=8,pady=(8,4))
        self.step_list=tk.Listbox(ct,height=7,bg=D['e'],fg=D['fg'],selectbackground=D['s'],selectforeground=D['fg']); self.step_list.grid(row=1,column=0,sticky='nsew',padx=(8,4),pady=(4,8)); self.step_list.bind('<<ListboxSelect>>',self.on_step)
        rt=ttk.Frame(ct); rt.grid(row=1,column=1,sticky='nsew',padx=(4,8),pady=(4,8)); rt.columnconfigure(0,weight=1); rt.rowconfigure(2,weight=1)
        self.step_meta=ttk.Label(rt,text='No step selected',style='Muted.TLabel',justify='left'); self.step_meta.grid(row=0,column=0,sticky='w')
        self.step_enabled_var = tk.BooleanVar()
        self.step_enabled_cb = ttk.Checkbutton(rt, text='Enable this step for the current project', variable=self.step_enabled_var, command=self.toggle_step)
        self.step_enabled_cb.grid(row=1, column=0, sticky='w', pady=(2, 4))
        bar=ttk.Frame(rt); bar.grid(row=2,column=0,sticky='ew',pady=(4,4))
        ttk.Button(bar,text='Generate Prompt',command=self.gen).pack(side='left',padx=2); ttk.Button(bar,text='Copy Prompt',command=self.copy_prompt).pack(side='left',padx=2); ttk.Button(bar,text='Validate Response',command=self.validate_response).pack(side='left',padx=2)
        ttk.Button(bar,text='Import Response',style='Accent.TButton',command=self.import_resp).pack(side='left',padx=2); ttk.Button(bar,text='Run Local',style='Ok.TButton',command=self.run_local).pack(side='left',padx=2)
        self.prompt=ScrolledText(rt,wrap=tk.WORD,undo=True,bg=D['e'],fg=D['fg'],insertbackground=D['fg'],selectbackground=D['s'],borderwidth=0,highlightthickness=1,highlightbackground=D['b'],font=('Consolas',10)); self.prompt.grid(row=3,column=0,sticky='nsew')
        cb=ttk.Frame(center); cb.columnconfigure(0,weight=1); cb.rowconfigure(1,weight=1); ttk.Label(cb,text='Paste Response JSON',style='Muted.TLabel').grid(row=0,column=0,sticky='w',padx=8,pady=(8,4))
        self.response=ScrolledText(cb,wrap=tk.WORD,undo=True,bg=D['e'],fg=D['fg'],insertbackground=D['fg'],selectbackground=D['s'],borderwidth=0,highlightthickness=1,highlightbackground=D['b'],font=('Consolas',10)); self.response.grid(row=1,column=0,sticky='nsew',padx=8,pady=(4,8))
        center.add(ct,weight=3); center.add(cb,weight=2)
        right=ttk.Frame(main); right.rowconfigure(1,weight=1); right.columnconfigure(0,weight=1); ttk.Label(right,text='Editors',style='Muted.TLabel').grid(row=0,column=0,sticky='w',padx=8,pady=(8,4))
        self.nb=ttk.Notebook(right); self.nb.grid(row=1,column=0,sticky='nsew',padx=8,pady=(4,8)); self.build_tabs()
        main.add(left,weight=2); main.add(center,weight=4); main.add(right,weight=4)
        self.status=tk.StringVar(value='Ready'); ttk.Label(self,textvariable=self.status,style='Muted.TLabel',anchor='w').grid(row=2,column=0,sticky='ew',padx=10,pady=(2,8))
    def build_tabs(self):
        self.tabs={}
        self.tabs['glossary']=Tab(self.nb,'Volume Glossary',lambda:self.data.setdefault('glossary',{}).setdefault('volume_merge_glossary',[]),lambda:self.mark('glossary'),
            [('source','Source',150,lambda x:x.get('source')),('vi','Vietnamese',160,lambda x:x.get('vi')),('type','Type',110,lambda x:x.get('type')),('status','Status',90,lambda x:x.get('status')),('notes','Notes',300,lambda x:x.get('notes'))],
            True,lambda:{'id':'','source':'','vi':'','type':'other','status':'tentative','notes':''})
        self.nb.add(self.tabs['glossary'],text='Volume Glossary')
        self.tabs['relationships']=Tab(self.nb,'Volume Relationships',lambda:self.data.setdefault('relationships',{}).setdefault('relationship_pronoun_canon',[]),lambda:self.mark('relationships'),
            [('speaker','Speaker',120,lambda x:x.get('speaker')),('listener','Listener',120,lambda x:x.get('listener')),('rel','Relationship',210,lambda x:x.get('relationship')),('self','Self',70,lambda x:x.get('self')),('other','Other',70,lambda x:x.get('other')),('variants','Variants',80,lambda x:len(x.get('variants',[]) or [])),('status','Status',90,lambda x:x.get('status')),('notes','Notes',220,lambda x:x.get('notes'))],
            True,lambda:{'id':'','speaker':'','listener':'','relationship':'','self':'','other':'','scope':'volume_default','status':'tentative','variants':[],'notes':'','needs_human_review':True})
        self.nb.add(self.tabs['relationships'],text='Volume Relationships')
        self.tabs['segment_glossaries']=Tab(self.nb,'Segment Glossaries',lambda:self.data.setdefault('segment_glossaries',[]),lambda:self.mark('segment_glossaries'),
            [('item','Item',110,iid),('status','Status',80,lambda x:x.get('status')),('chapter','Chapter',70,lambda x:result(x).get('chapter')),('segment','Segment',110,lambda x:result(x).get('segment')),('terms','Terms',60,lambda x:len(result(x).get('segment_glossary',[]) or [])),('missing','Missing',70,lambda x:len(result(x).get('missing_glossary_candidates',[]) or []))])
        self.nb.add(self.tabs['segment_glossaries'],text='Segment Glossaries')
        self.tabs['segment_pronouns']=Tab(self.nb,'Segment Pronouns',lambda:self.data.setdefault('segment_pronouns',[]),lambda:self.mark('segment_pronouns'),
            [('item','Item',110,iid),('status','Status',80,lambda x:x.get('status')),('segment','Segment',110,lambda x:result(x).get('segment')),('rules','Rules',60,lambda x:len(result(x).get('segment_pronoun_table',[]) or [])),('overrides','Overrides',70,lambda x:len(result(x).get('segment_override_candidates',[]) or [])),('missing','Missing',70,lambda x:len(result(x).get('missing_rules',[]) or []))])
        self.nb.add(self.tabs['segment_pronouns'],text='Segment Pronouns')
        self.tabs['translations'] = TranslationsTab(self.nb, self)
        self.nb.add(self.tabs['translations'], text='Translations')
        ref=ttk.Frame(self.nb); ref.rowconfigure(1,weight=1); ref.columnconfigure(0,weight=1); bar=ttk.Frame(ref); bar.grid(row=0,column=0,sticky='ew',padx=8,pady=(8,4)); bar.columnconfigure(0,weight=1)
        self.ref_path=tk.StringVar(); ttk.Entry(bar,textvariable=self.ref_path).grid(row=0,column=0,sticky='ew',padx=(0,6)); ttk.Button(bar,text='Open File...',command=self.open_ref).grid(row=0,column=1,padx=2); ttk.Button(bar,text='Reload',command=self.reload_ref).grid(row=0,column=2,padx=2)
        self.ref=ScrolledText(ref,wrap=tk.NONE,bg=D['e'],fg=D['fg'],insertbackground=D['fg'],selectbackground=D['s'],borderwidth=0,highlightthickness=1,highlightbackground=D['b'],font=('Consolas',10)); self.ref.grid(row=1,column=0,sticky='nsew',padx=8,pady=(4,8)); self.nb.add(ref,text='Reference')
    def build_steps(self):
        self.steps=[
            Step('extract_chapter_glossary','Extract Chapter Glossary','chapter','01_extract_volume_glossary.txt',self.in_extract_ch_gloss,self.imp_ch_gloss),
            Step('merge_volume_glossary','Merge Volume Glossary','volume','02_merge_volume_glossary.txt',self.in_merge_vol_gloss,self.imp_vol_gloss),
            Step('review_volume_glossary','Review/Finalize Volume Glossary','volume',None,None,None,self.focus_g,'Use editor tab, then Approve Glossary'),
            Step('extract_chapter_relationships','Extract Chapter Relationships','chapter','04_extract_volume_relationships.txt',self.in_extract_ch_rel,self.imp_ch_rel),
            Step('merge_volume_relationships','Merge Volume Relationships','volume','05_merge_volume_relationships.txt',self.in_merge_vol_rel,self.imp_vol_rel),
            Step('review_volume_relationships','Review/Finalize Volume Relationships','volume',None,None,None,self.focus_r,'Use editor tab, then Approve Relationships'),
            Step('build_segment_glossary','Build Segment Glossary (AI)','segment','03_build_segment_glossary.txt',self.in_seg_gloss,self.imp_seg_gloss),
            Step('build_segment_glossary_local','Build Segment Glossary (Local)','segment',None,None,None,self.build_sg_local,'Run local text matching to build segment glossary'),
            Step('review_segment_glossary','Review Segment Glossary','segment',None,None,None,self.focus_sg,'Inspect/edit imported row in Segment Glossaries tab'),
            Step('build_segment_pronouns','Build Segment Pronouns (AI)','segment','06_build_segment_pronouns.txt',self.in_seg_pron,self.imp_seg_pron),
            Step('build_segment_pronouns_local','Build Segment Pronouns (Local)','segment',None,None,None,self.build_sp_local,'Run local text matching to build segment pronouns'),
            Step('review_segment_pronouns','Review Segment Pronouns','segment',None,None,None,self.focus_sp,'Inspect/edit imported row in Segment Pronouns tab'),
            Step('build_segment_context','Build Segment Context','segment','07_build_segment_context.txt',self.in_seg_ctx,self.imp_seg_ctx),
            Step('label_dialogue','Label Dialogue','segment','08_label_dialogue.txt',self.in_label,self.imp_label),
            Step('translate','Translate','segment','09_translate_labeled_segment.txt',self.in_translate,self.imp_translate),
            Step('qa','QA (optional)','segment','10_qa_segment.txt',self.in_qa,self.imp_qa),
            Step('fix','Fix (optional)','segment','11_fix_segment.txt',self.in_fix,self.imp_fix),
            Step('assemble','Assemble Volume (local)','volume',None,None,None,self.assemble,'Local assemble into release files'),
        ]
    def open_root(self):
        p=filedialog.askdirectory(title='Select project root')
        if p: self.ws=WS(p); self.root_label.config(text=str(self.ws.root)); self.reload()
    def build_tree(self, preserve_id=None):
        self.tree.delete(*self.tree.get_children()); source_dir=self.ws.p('source')
        if not source_dir.exists(): return
        for vp in sorted(source_dir.glob('volume_*.json')):
            m=re.search(r'volume_(\d+)\.json',vp.name)
            if not m: continue
            v=int(m.group(1)); vid=f'volume:{v}'; self.tree.insert('', 'end', iid=vid, text=f'Volume {v:02d}')
            self.tree.insert(vid,'end',iid=f'{vid}:canon_g',text='Volume Glossary')
            self.tree.insert(vid,'end',iid=f'{vid}:canon_r',text='Volume Relationships')
            chs=self.ws.chapters(v); cids={}
            for ch in chs:
                c=int(ch.get('chapter',0)); cid=f'{vid}:chapter:{c}'; cids[c]=cid; self.tree.insert(vid,'end',iid=cid,text=f'Chapter {c:03d} — {ch.get("name","")}')
            for seg in self.ws.segments(v):
                c=int(seg.get('chapter',0)); sid=f'{vid}:segment:{seg.get("segment")}'; self.tree.insert(cids.get(c,vid),'end',iid=sid,text=f'Segment {seg.get("segment")}')
        children=self.tree.get_children()
        if preserve_id and self.tree.exists(preserve_id):
            self.tree.selection_set(preserve_id)
            self.tree.see(preserve_id)
            self.on_tree()
        elif children: self.tree.selection_set(children[0]); self.on_tree()
    def parse_node(self,i):
        p=i.split(':'); node={'type':'unknown'}
        if len(p)>=2 and p[0]=='volume':
            node={'type':'volume','volume':int(p[1])}
            if 'chapter' in p: node={'type':'chapter','volume':int(p[1]),'chapter':int(p[p.index('chapter')+1])}
            if 'segment' in p: node={'type':'segment','volume':int(p[1]),'segment':p[p.index('segment')+1]}
        return node
    def on_tree(self,_=None):
        s=self.tree.selection()
        if not s: return
        self.current=self.parse_node(s[0]); self.load_artifacts(); self.refresh_tabs(); self.populate_steps(); self.status.set(f'Selected {self.current}')
    def load_artifacts(self):
        v=self.vol() or 1
        self.data['glossary']=read_json(self.ws.g_draft(v),None) or read_json(self.ws.g_final(v),{'volume':v,'volume_merge_glossary':[],'review_notes':[]})
        self.data['relationships']=read_json(self.ws.r_draft(v),None) or read_json(self.ws.r_final(v),{'volume':v,'relationship_pronoun_canon':[],'review_notes':[]})
        self.data['segment_glossaries']=read_jsonl(self.ws.sg(v)); self.data['segment_pronouns']=read_jsonl(self.ws.sp(v))
    def populate_steps(self):
        self.step_list.delete(0,tk.END)
        for s in [x for x in self.steps if x.scope==self.current.get('type')]: self.step_list.insert(tk.END,s.label)
        if self.step_list.size(): self.step_list.selection_set(0); self.on_step()
    def selected_step(self):
        s=self.step_list.curselection()
        if not s: return None
        lst=[x for x in self.steps if x.scope==self.current.get('type')]
        return lst[s[0]] if s[0]<len(lst) else None
    def toggle_step(self):
        st=self.selected_step()
        if not st: return
        en = self.step_enabled_var.get()
        if en and st.id not in self.config.setdefault('enabled_steps', []):
            self.config['enabled_steps'].append(st.id)
            self.ws.save_config(self.config)
        elif not en and st.id in self.config.setdefault('enabled_steps', []):
            self.config['enabled_steps'].remove(st.id)
            self.ws.save_config(self.config)
        self.on_step()

    def on_step(self,_=None):
        st=self.selected_step()
        if not st: self.step_meta.config(text='No step selected'); return
        is_en = st.id in self.config.get('enabled_steps', [])
        self.step_enabled_var.set(is_en)
        if not is_en:
            self.step_meta.config(text=f"Step: {st.label}\n[DISABLED - Tick checkbox to enable]")
            self.prompt.delete('1.0',tk.END)
            return
        txt=[f"Step: {st.label}"]; 
        if st.prompt: txt.append(f"Prompt: {st.prompt}")
        if st.desc: txt.append(st.desc)
        self.step_meta.config(text='\n'.join(txt))
    def gen(self):
        st=self.selected_step()
        if not st or st.id not in self.config.get('enabled_steps', []): return
        if st.local and not st.prompt:
            self.prompt.delete('1.0',tk.END); self.prompt.insert('1.0',f'[LOCAL ACTION]\n{st.desc or st.label}'); return
        try: inp=st.build(); pr=self.ws.render(st.prompt,inp)
        except Exception as e: messagebox.showerror(APP,f'Could not generate prompt:\n{e}'); return
        self.prompt.delete('1.0',tk.END); self.prompt.insert('1.0',pr); self.status.set(f'Prompt generated for {st.label}')
    def copy_prompt(self):
        t=self.prompt.get('1.0',tk.END).strip()
        if not t: return
        self.clipboard_clear(); self.clipboard_append(t); self.update(); self.status.set('Prompt copied.')
    def validate_response(self):
        t=self.response.get('1.0',tk.END).strip()
        if not t: return
        try: o=parse_json_response(t)
        except Exception as e: messagebox.showerror(APP,f'Invalid JSON response:\n{e}'); return
        self.response.delete('1.0',tk.END); self.response.insert('1.0',pretty(o)); self.status.set('Response validated.')
    def import_resp(self):
        if getattr(self, 'current_quick_fix_data', None):
            t = self.response.get('1.0', tk.END).strip()
            if not t: return
            try:
                o = parse_json_response(t)
                new_text = o.get('new_translation_snippet', '')
                if not new_text: raise ValueError('Missing new_translation_snippet')
                tab = self.tabs.get('translations')
                if tab and tab.cur_id == self.current_quick_fix_data['item_id']:
                    tab.ed.delete(self.current_quick_fix_data['sel_first'], self.current_quick_fix_data['sel_last'])
                    tab.ed.insert(self.current_quick_fix_data['sel_first'], new_text)
                    messagebox.showinfo('Quick Fix', 'Translation updated! Click Save Translation when done.')
                self.current_quick_fix_data = None
                self.status.set('Quick Fix applied.')
            except Exception as e: messagebox.showerror(APP, f'Quick Fix failed:\n{e}')
            return
        st=self.selected_step()
        if not st or not st.importer or st.id not in self.config.get('enabled_steps', []): return
        t=self.response.get('1.0',tk.END).strip()
        if not t: return
        try: o=parse_json_response(t); st.importer(o)
        except Exception as e: messagebox.showerror(APP,f'Import failed:\n{e}'); return
        self.reload(); self.status.set(f'Imported response for {st.label}')
    def run_local(self):
        st=self.selected_step()
        if not st or not st.local or st.id not in self.config.get('enabled_steps', []): return
        try: st.local()
        except Exception as e: messagebox.showerror(APP,f'Local action failed:\n{e}'); return
        self.reload()
    def chapter_rec(self):
        if self.current.get('type')!='chapter': return None
        for ch in self.ws.chapters(self.vol()):
            if int(ch.get('chapter',0))==self.current['chapter']: return ch
    def segment_rec(self):
        if self.current.get('type')!='segment': return None
        for seg in self.ws.segments(self.vol()):
            if str(seg.get('segment'))==self.current['segment']: return seg
    def jsonl_map(self,p): return self.ws.map_jsonl(p)
    def build_sg_local(self):
        c = self.current
        if not c or c.get('type') != 'segment': messagebox.showerror(APP, 'Please select a segment.'); return
        vol = c.get('volume'); item_id = item_id_from_record(self.segment_rec()); seg_id = c.get('segment')
        vg = self.data.get('glossary', {}).get('volume_merge_glossary', [])
        if not vg: messagebox.showwarning(APP, 'Volume glossary is empty.'); return
        seg_data = self.segment_rec()
        if not seg_data: return
        content = seg_data.get('content', '')
        sg = []
        for term in vg:
            src = term.get('source', '')
            if src and src in content:
                sg.append({'id': term.get('id', ''), 'source': src, 'vi': term.get('vi', ''), 'type': term.get('type', ''), 'status': term.get('status', 'tentative'), 'aliases': term.get('aliases', ''), 'notes': term.get('notes', '')})
        res = {'item_id': item_id, 'chapter': seg_data.get('chapter', 0), 'segment': seg_id, 'segment_glossary': sg, 'missing_glossary_candidates': []}
        self.imp_seg_gloss(res)
        self.reload(); self.status.set(f'Local segment glossary built with {len(sg)} terms.')
    def build_sp_local(self):
        c = self.current
        if not c or c.get('type') != 'segment': messagebox.showerror(APP, 'Please select a segment.'); return
        vol = c.get('volume'); item_id = item_id_from_record(self.segment_rec()); seg_id = c.get('segment')
        vg = self.data.get('glossary', {}).get('volume_merge_glossary', [])
        vr = self.data.get('relationships', {}).get('relationship_pronoun_canon', [])
        seg_data = self.segment_rec()
        if not seg_data: return
        content = seg_data.get('content', '')
        present_chars = set()
        for term in vg:
            if term.get('type') in ['character', 'alias', 'title', 'epithet']:
                src = term.get('source', '')
                if src and src in content:
                    present_chars.add(term.get('vi', '')); present_chars.add(term.get('source', '')); present_chars.add(term.get('id', ''))
        sp = []
        for rel in vr:
            spk = rel.get('speaker')
            lsn = rel.get('listener')
            spk_in = (spk in present_chars) or (spk in ['UNKNOWN', 'GROUP'])
            lsn_in = (lsn in present_chars) or (lsn in ['UNKNOWN', 'GROUP', 'self', 'SELF'])
            if spk_in and lsn_in:
                sp.append({'speaker': spk, 'listener': lsn, 'relationship': rel.get('relationship', ''), 'self': rel.get('self', ''), 'other': rel.get('other', ''), 'variants': rel.get('variants', []), 'source': 'inherited_from_volume', 'notes': rel.get('notes', '')})
        res = {'item_id': item_id, 'chapter': seg_data.get('chapter', 0), 'segment': seg_id, 'segment_pronoun_table': sp, 'segment_override_candidates': [], 'missing_rules': []}
        self.imp_seg_pron(res)
        self.reload(); self.status.set(f'Local segment pronouns built with {len(sp)} rules.')
    # input builders
    def base_ch(self):
        ch=self.chapter_rec()
        if not ch: raise RuntimeError('No chapter selected')
        return {'item_id':item_id_from_record(ch),'volume':self.vol(),'chapter':ch.get('chapter'),'segment':ch.get('segment'),'name':ch.get('name'),'content':ch.get('content','')}
    def base_seg(self):
        seg=self.segment_rec()
        if not seg: raise RuntimeError('No segment selected')
        return {'item_id':item_id_from_record(seg),'volume':self.vol(),'chapter':seg.get('chapter'),'segment':seg.get('segment'),'name':seg.get('name'),'content':seg.get('content','')}
    def in_extract_ch_gloss(self): return self.base_ch()
    def in_merge_vol_gloss(self):
        prev=read_json(self.ws.g_final(self.vol()-1),None) if self.vol()>1 else None
        return {'volume':self.vol(),'chapter_extractions':[r.get('result') for r in read_jsonl(self.ws.ge(self.vol())) if r.get('status')=='success'],'previous_finalized_glossary':prev}
    def in_extract_ch_rel(self):
        o=self.base_ch(); o['volume_glossary']=read_json(self.ws.g_final(self.vol()),read_json(self.ws.g_draft(self.vol()),{})); return o
    def in_merge_vol_rel(self):
        prev=read_json(self.ws.r_final(self.vol()-1),None) if self.vol()>1 else None
        return {'volume':self.vol(),'relationship_extractions':[r.get('result') for r in read_jsonl(self.ws.re(self.vol())) if r.get('status')=='success'],'previous_finalized_relationships':prev}
    def in_seg_gloss(self):
        seg=self.base_seg(); seg['volume_glossary']=read_json(self.ws.g_final(self.vol()),read_json(self.ws.g_draft(self.vol()),{})); return seg
    def in_seg_pron(self):
        seg=self.base_seg(); seg['segment_glossary']=result(self.jsonl_map(self.ws.sg(self.vol())).get(seg['segment'],{})); seg['volume_relationship_pronoun_canon']=read_json(self.ws.r_final(self.vol()),read_json(self.ws.r_draft(self.vol()),{})); return seg
    def in_seg_ctx(self):
        seg=self.base_seg(); seg['segment_glossary']=result(self.jsonl_map(self.ws.sg(self.vol())).get(seg['segment'],{})); seg['segment_pronoun_table']=result(self.jsonl_map(self.ws.sp(self.vol())).get(seg['segment'],{})); return seg
    def in_label(self):
        seg=self.base_seg(); seg['segment_glossary']=result(self.jsonl_map(self.ws.sg(self.vol())).get(seg['segment'],{})); seg['segment_pronoun_table']=result(self.jsonl_map(self.ws.sp(self.vol())).get(seg['segment'],{})); seg['segment_context']=result(self.jsonl_map(self.ws.sc(self.vol())).get(seg['segment'],{})); seg['dialogue_labeling_config']={'review_confidence_threshold':0.72,'auto_accept_confidence_threshold':0.82}; return seg
    def in_translate(self):
        seg=self.base_seg(); del seg['content']; seg['segment_glossary']=result(self.jsonl_map(self.ws.sg(self.vol())).get(seg['segment'],{})); seg['segment_pronoun_table']=result(self.jsonl_map(self.ws.sp(self.vol())).get(seg['segment'],{})); seg['segment_context']=result(self.jsonl_map(self.ws.sc(self.vol())).get(seg['segment'],{})); seg['dialogue_labels']=result(self.jsonl_map(self.ws.dl(self.vol())).get(seg['segment'],{})); return seg
    def in_qa(self):
        seg=self.base_seg(); seg['source_content']=seg.pop('content'); seg['segment_glossary']=result(self.jsonl_map(self.ws.sg(self.vol())).get(seg['segment'],{})); seg['segment_pronoun_table']=result(self.jsonl_map(self.ws.sp(self.vol())).get(seg['segment'],{})); seg['segment_context']=result(self.jsonl_map(self.ws.sc(self.vol())).get(seg['segment'],{})); seg['dialogue_labels']=result(self.jsonl_map(self.ws.dl(self.vol())).get(seg['segment'],{})); seg['translation']=result(self.jsonl_map(self.ws.tr(self.vol())).get(seg['segment'],{})); return seg
    def in_fix(self):
        seg=self.in_qa(); seg['qa_report']=result(self.jsonl_map(self.ws.qa(self.vol())).get(seg['segment'],{})); return seg
    # importers
    def upsert_jsonl(self,p,item_id,obj):
        rows=read_jsonl(p); row={'item_id':item_id,'status':'success','result':obj}; ok=False
        for i,r in enumerate(rows):
            if iid(r)==item_id: rows[i]=row; ok=True; break
        if not ok: rows.append(row)
        backup(p); write_jsonl(p,rows)
    def imp_ch_gloss(self,obj): self.upsert_jsonl(self.ws.ge(self.vol()),item_id_from_record(self.chapter_rec()),obj)
    def imp_vol_gloss(self,obj): backup(self.ws.g_draft(self.vol())); write_json(self.ws.g_draft(self.vol()),obj)
    def imp_ch_rel(self,obj): self.upsert_jsonl(self.ws.re(self.vol()),item_id_from_record(self.chapter_rec()),obj)
    def imp_vol_rel(self,obj): backup(self.ws.r_draft(self.vol())); write_json(self.ws.r_draft(self.vol()),obj)
    def imp_seg_gloss(self,obj): self.upsert_jsonl(self.ws.sg(self.vol()),item_id_from_record(self.segment_rec()),obj)
    def imp_seg_pron(self,obj): self.upsert_jsonl(self.ws.sp(self.vol()),item_id_from_record(self.segment_rec()),obj)
    def imp_seg_ctx(self,obj): self.upsert_jsonl(self.ws.sc(self.vol()),item_id_from_record(self.segment_rec()),obj)
    def imp_label(self,obj): self.upsert_jsonl(self.ws.dl(self.vol()),item_id_from_record(self.segment_rec()),obj)
    def imp_translate(self,obj): self.upsert_jsonl(self.ws.tr(self.vol()),item_id_from_record(self.segment_rec()),obj)
    def imp_qa(self,obj): self.upsert_jsonl(self.ws.qa(self.vol()),item_id_from_record(self.segment_rec()),obj)
    def imp_fix(self,obj): self.upsert_jsonl(self.ws.fx(self.vol()),item_id_from_record(self.segment_rec()),obj)
    # local
    def assemble(self):
        segs=self.ws.segments(self.vol()); draft=self.jsonl_map(self.ws.tr(self.vol())); fixed=self.jsonl_map(self.ws.fx(self.vol())); chapters={}
        for seg in segs:
            sid=seg.get('segment')
            txt=(result(fixed.get(sid,{})).get('fixed_translation') or result(fixed.get(sid,{})).get('translation') or result(draft.get(sid,{})).get('translation') or '')
            c=int(seg.get('chapter',0)); chapters.setdefault(c,{'chapter':c,'name':seg.get('name',''),'segments':[]}); chapters[c]['segments'].append({'segment':sid,'translation':txt})
        out=[]
        for c in sorted(chapters):
            ch=chapters[c]; ch['content']='\n\n'.join(x['translation'] for x in ch['segments'] if x.get('translation')); out.append(ch)
        rel={'volume':self.vol(),'chapters':out}; write_json(self.ws.rel_json(self.vol()),rel)
        md=[f"# Volume {self.vol():02d}"]
        for ch in out: md.append(f"\n## Chapter {ch['chapter']} — {ch.get('name','')}\n"); md.append(ch.get('content',''))
        self.ws.rel_md(self.vol()).write_text('\n'.join(md).strip()+'\n',encoding='utf-8'); messagebox.showinfo(APP,f'Assembled release for volume {self.vol():02d}.')
    def focus_g(self): self.nb.select(self.tabs['glossary'])
    def focus_r(self): self.nb.select(self.tabs['relationships'])
    def focus_sg(self): self.nb.select(self.tabs['segment_glossaries'])
    def focus_sp(self): self.nb.select(self.tabs['segment_pronouns'])
    # misc
    def mark(self,key): self.dirty.add(key); self.status.set('Dirty: '+', '.join(sorted(self.dirty))); self.title(APP+' *')
    def refresh_tabs(self):
        for t in self.tabs.values():
            try: t.refresh()
            except Exception: pass
    def save_all(self):
        v=self.vol() or 1
        try:
            if 'glossary' in self.dirty: p=self.ws.g_draft(v) if self.ws.g_draft(v).exists() or not self.ws.g_final(v).exists() else self.ws.g_final(v); backup(p); write_json(p,self.data['glossary'])
            if 'relationships' in self.dirty: p=self.ws.r_draft(v) if self.ws.r_draft(v).exists() or not self.ws.r_final(v).exists() else self.ws.r_final(v); backup(p); write_json(p,self.data['relationships'])
            if 'segment_glossaries' in self.dirty: backup(self.ws.sg(v)); write_jsonl(self.ws.sg(v),self.data['segment_glossaries'])
            if 'segment_pronouns' in self.dirty: backup(self.ws.sp(v)); write_jsonl(self.ws.sp(v),self.data['segment_pronouns'])
        except Exception as e: messagebox.showerror(APP,f'Save failed:\n{e}'); return
        self.dirty.clear(); self.status.set('Editors saved.'); self.title(APP)
    def approve_g(self):
        self.save_all(); src=self.ws.g_draft(self.vol()); dst=self.ws.g_final(self.vol())
        if not src.exists(): messagebox.showerror(APP,f'Missing glossary draft:\n{src}'); return
        if dst.exists() and not messagebox.askyesno(APP,f'Overwrite finalized glossary?\n{dst}'): return
        dst.parent.mkdir(parents=True,exist_ok=True); backup(dst); shutil.copy2(src,dst); messagebox.showinfo(APP,f'Approved glossary:\n{dst}'); self.reload()
    def approve_r(self):
        self.save_all(); src=self.ws.r_draft(self.vol()); dst=self.ws.r_final(self.vol())
        if not src.exists(): messagebox.showerror(APP,f'Missing relationships draft:\n{src}'); return
        if dst.exists() and not messagebox.askyesno(APP,f'Overwrite finalized relationships?\n{dst}'): return
        dst.parent.mkdir(parents=True,exist_ok=True); backup(dst); shutil.copy2(src,dst); messagebox.showinfo(APP,f'Approved relationships:\n{dst}'); self.reload()
    def open_ref(self):
        p=filedialog.askopenfilename(initialdir=str(self.ws.root),filetypes=[('Text/JSON','*.json *.jsonl *.md *.txt'),('All','*.*')])
        if p: self.ref_path.set(p); self.reload_ref()
    def reload_ref(self):
        p=Path(self.ref_path.get().strip())
        if not p.exists(): return
        txt=p.read_text(encoding='utf-8')
        if p.suffix.lower()=='.json':
            try: txt=pretty(json.loads(txt))
            except Exception: pass
        self.ref.delete('1.0',tk.END); self.ref.insert('1.0',txt)
    def reload(self):
        old_sel = self.tree.selection()
        old_id = old_sel[0] if old_sel else None
        self.root_label.config(text=str(self.ws.root)); self.load_artifacts(); self.build_tree(old_id); self.refresh_tabs(); self.status.set('Workspace reloaded.')
    def exit(self):
        if self.dirty:
            a=messagebox.askyesnocancel(APP,'Save editor changes before exit?')
            if a is None: return
            if a: self.save_all()
        self.destroy()

class StartupApp(tk.Tk):
    def __init__(self, root_dir):
        super().__init__(); setup(self); self.title('Select Project'); self.geometry('600x400'); self.minsize(600,400)
        self.root_dir = Path(root_dir)
        self.selected_project = None
        self.build_ui()
    def build_ui(self):
        self.columnconfigure(0, weight=1)
        ttk.Label(self, text='Manual Prompt Studio - Project Selection', font=('Segoe UI',14,'bold')).grid(row=0, column=0, pady=20)
        f = ttk.Frame(self); f.grid(row=1, column=0, sticky='nsew', padx=40); f.columnconfigure(1, weight=1)
        ttk.Label(f, text='Existing Projects:').grid(row=0, column=0, sticky='w', pady=(0,5))
        self.proj_combo = ttk.Combobox(f, state='readonly')
        self.proj_combo.grid(row=0, column=1, sticky='ew', pady=(0,5))
        data_dir = self.root_dir.joinpath('data')
        projs = []
        if data_dir.exists():
            projs = [d.name for d in data_dir.iterdir() if d.is_dir() and d.name not in ('source', 'segments')]
        self.proj_combo['values'] = projs
        if projs: self.proj_combo.current(0)
        ttk.Button(f, text='Load Project', style='Accent.TButton', command=self.load_proj).grid(row=0, column=2, padx=5, pady=(0,5))
        ttk.Separator(f, orient='horizontal').grid(row=1, column=0, columnspan=3, sticky='ew', pady=20)
        ttk.Label(f, text='Create New Project:', font=('Segoe UI', 12, 'bold')).grid(row=2, column=0, columnspan=3, sticky='w', pady=(0,10))
        ttk.Label(f, text='Project Name:').grid(row=3, column=0, sticky='w', pady=5)
        self.new_name = tk.StringVar()
        ttk.Entry(f, textvariable=self.new_name).grid(row=3, column=1, columnspan=2, sticky='ew', pady=5)
        ttk.Label(f, text='Genre:').grid(row=4, column=0, sticky='w', pady=5)
        self.new_genre = tk.StringVar(value='Fantasy / Adventure')
        ttk.Entry(f, textvariable=self.new_genre).grid(row=4, column=1, columnspan=2, sticky='ew', pady=5)
        ttk.Label(f, text='Level:').grid(row=5, column=0, sticky='w', pady=5)
        self.new_level = tk.StringVar(value='Heavy')
        ttk.Combobox(f, textvariable=self.new_level, values=['Heavy', 'Medium', 'Lite'], state='readonly').grid(row=5, column=1, columnspan=2, sticky='ew', pady=5)
        ttk.Button(f, text='Create Project', style='Ok.TButton', command=self.create_proj).grid(row=6, column=1, pady=20)
    def load_proj(self):
        val = self.proj_combo.get()
        if not val: return
        self.selected_project = val
        self.destroy()
    def create_proj(self):
        name = self.new_name.get().strip()
        if not name: messagebox.showerror('Error', 'Project Name is required'); return
        if name in ('source', 'segments'): messagebox.showerror('Error', 'Invalid Project Name'); return
        lvl = self.new_level.get()
        steps = []
        if lvl == 'Heavy':
            steps = ['extract_chapter_glossary', 'merge_volume_glossary', 'review_volume_glossary', 'extract_chapter_relationships', 'merge_volume_relationships', 'review_volume_relationships', 'build_segment_glossary', 'review_segment_glossary', 'build_segment_pronouns', 'review_segment_pronouns', 'build_segment_context', 'label_dialogue', 'translate', 'qa', 'fix', 'assemble']
        else: # Medium / Lite
            steps = ['extract_chapter_glossary', 'merge_volume_glossary', 'review_volume_glossary', 'extract_chapter_relationships', 'merge_volume_relationships', 'review_volume_relationships', 'label_dialogue', 'translate', 'assemble']
        cfg = {'name': name, 'genre': self.new_genre.get().strip(), 'level': lvl, 'enabled_steps': steps}
        cfg_path = self.root_dir.joinpath('data', name, 'project_config.json')
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(cfg_path, cfg)
        self.selected_project = name
        self.destroy()

def main():
    root=Path.cwd()
    if len(sys.argv)>1:
        p=Path(sys.argv[1])
        if p.exists() and p.is_dir(): root=p
    startup = StartupApp(root)
    startup.mainloop()
    if startup.selected_project:
        app=App(root, startup.selected_project)
        app.mainloop()

if __name__=='__main__': main()
