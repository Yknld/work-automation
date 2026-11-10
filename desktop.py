"""Run: python desktop.py. Native desktop UI; no localhost server."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from openpyxl import load_workbook
from automation import Copilot
from spreadsheet_jobs import read_sheet, prepare, request, run_job

class App:
    def __init__(self, root):
        self.root=root;root.title('Work Automation — Spreadsheet prompts');root.geometry('1050x800')
        self.events=queue.Queue();self.stop=threading.Event();self.running=False
        self.paths={};self.sheets={};self.keys={};self.lists={};self.rows={}
        shell=ttk.Frame(root,padding=12);shell.pack(fill='both',expand=True)
        ttk.Label(shell,text='Spreadsheet A supplies the rows. B is optional and matches by a shared column.',wraplength=980).pack(anchor='w')
        sources=ttk.Frame(shell);sources.pack(fill='x',pady=8)
        for name in ('A','B'):
            box=ttk.LabelFrame(sources,text=f'Spreadsheet {name}',padding=8);box.pack(side='left',fill='both',expand=True,padx=4)
            self.paths[name]=tk.StringVar();ttk.Button(box,text='Choose .xlsx',command=lambda n=name:self.choose(n)).pack(anchor='w')
            ttk.Entry(box,textvariable=self.paths[name],state='readonly').pack(fill='x',pady=4)
            self.sheets[name]=ttk.Combobox(box,state='readonly');self.sheets[name].pack(fill='x')
            self.sheets[name].bind('<<ComboboxSelected>>',lambda e,n=name:self.load(n))
            ttk.Label(box,text='Match column (required only for B tags)').pack(anchor='w')
            self.keys[name]=ttk.Combobox(box,state='readonly');self.keys[name].pack(fill='x')
            self.lists[name]=tk.Listbox(box,height=6,exportselection=False);self.lists[name].pack(fill='x')
            self.lists[name].bind('<Double-Button-1>',lambda e,n=name:self.insert(n))
            ttk.Button(box,text=f'Insert selected {name} column tag',command=lambda n=name:self.insert(n)).pack(anchor='w')
        ttk.Label(shell,text='Prompt — double-click a column to insert its tag. Describe each requested output.').pack(anchor='w')
        self.prompt=tk.Text(shell,height=7,wrap='word');self.prompt.pack(fill='both',expand=True)
        self.prompt.insert('1.0','Evaluate this text: {{A.Description}}\nFor Assessment, return Yes, No, or Unclear. For Reason, briefly explain using the text.')
        settings=ttk.Frame(shell);settings.pack(fill='x',pady=8)
        ttk.Label(settings,text='New output columns (comma-separated):').grid(row=0,column=0,sticky='w')
        self.outputs=tk.StringVar(value='Assessment, Reason');ttk.Entry(settings,textvariable=self.outputs,width=55).grid(row=0,column=1,columnspan=3,sticky='we')
        self.first=tk.StringVar(value='2');self.last=tk.StringVar(value='2')
        ttk.Label(settings,text='Excel rows, inclusive:').grid(row=1,column=0,sticky='w')
        ttk.Entry(settings,textvariable=self.first,width=8).grid(row=1,column=1,sticky='w')
        ttk.Label(settings,text='through').grid(row=1,column=2)
        ttk.Entry(settings,textvariable=self.last,width=8).grid(row=1,column=3)
        self.destination=tk.StringVar()
        ttk.Button(settings,text='Choose output file',command=self.output).grid(row=2,column=0,sticky='w')
        ttk.Entry(settings,textvariable=self.destination,width=65,state='readonly').grid(row=2,column=1,columnspan=3)
        actions=ttk.Frame(shell);actions.pack(fill='x')
        ttk.Button(actions,text='Preview first selected row',command=self.preview).pack(side='left')
        self.test=ttk.Button(actions,text='Run one row',command=lambda:self.start(True));self.test.pack(side='left',padx=6)
        self.run=ttk.Button(actions,text='Run row range',command=lambda:self.start(False));self.run.pack(side='left')
        ttk.Button(actions,text='Stop after current row',command=self.stop.set).pack(side='left',padx=6)
        self.log=tk.Text(shell,height=6,state='disabled',wrap='word');self.log.pack(fill='x',pady=8)
        ttk.Label(shell,text='Prompts go to Microsoft 365 Copilot through Edge. Originals stay unchanged. Close output Excel while running.').pack(anchor='w')
        root.after(100,self.poll);root.protocol('WM_DELETE_WINDOW',self.close)
    def choose(self,n):
        if self.running:return
        path=filedialog.askopenfilename(filetypes=[('Excel workbook','*.xlsx')])
        if not path:return
        try:
            book=load_workbook(path,read_only=True);names=book.sheetnames;book.close()
            self.paths[n].set(path);self.sheets[n]['values']=names;self.sheets[n].set(names[0]);self.load(n)
        except Exception as exc:messagebox.showerror('Workbook',str(exc))
    def load(self,n):
        try:
            headers,rows=read_sheet(self.paths[n].get(),self.sheets[n].get());self.rows[n]=rows
            self.lists[n].delete(0,'end')
            for h in headers:
                if h:self.lists[n].insert('end',h)
            self.keys[n]['values']=[h for h in headers if h];self.keys[n].set('')
            if n=='A':self.last.set(str(max(rows,default=2)))
        except Exception as exc:messagebox.showerror('Sheet',str(exc))
    def insert(self,n):
        selection=self.lists[n].curselection()
        if selection:self.prompt.insert('insert','{{'+n+'.'+self.lists[n].get(selection[0])+'}}')
    def output(self):
        if self.running:return
        path=filedialog.asksaveasfilename(defaultextension='.xlsx',filetypes=[('Excel workbook','*.xlsx')],initialfile='automation_results.xlsx')
        if path:self.destination.set(path)
    def config(self):
        return dict(a=self.paths['A'].get(),b=self.paths['B'].get(),sheet_a=self.sheets['A'].get(),sheet_b=self.sheets['B'].get(),key_a=self.keys['A'].get(),key_b=self.keys['B'].get(),prompt=self.prompt.get('1.0','end').strip(),outputs=[s.strip() for s in self.outputs.get().split(',')],first=int(self.first.get()),last=int(self.last.get()),output=self.destination.get())
    def preview(self):
        try:
            c=self.config();_,rows=read_sheet(c['a'],c['sheet_a'])
            b=read_sheet(c['b'],c['sheet_b'])[1] if c['b'] else None
            text=request(prepare(c['prompt'],rows[c['first']],b,c['key_a'],c['key_b']),c['outputs'])
            window=tk.Toplevel(self.root);window.title('Exact prompt preview — nothing sent')
            view=tk.Text(window,wrap='word',width=100,height=25);view.pack(fill='both',expand=True);view.insert('1.0',text);view.config(state='disabled')
        except Exception as exc:messagebox.showerror('Preview',str(exc))
    def start(self,one):
        if self.running:return
        try:
            c=self.config()
            if not c['a'] or not c['output']:raise ValueError('Choose spreadsheet A and a new output filename.')
            if one:c['last']=c['first']
        except Exception as exc:messagebox.showerror('Settings',str(exc));return
        self.running=True;self.stop.clear();self.run.config(state='disabled');self.test.config(state='disabled')
        def work():
            try:run_job(c,Copilot,self.stop,lambda msg:self.events.put(msg))
            except Exception as exc:self.events.put(f'Stopped: {exc}')
            finally:self.events.put(None)
        threading.Thread(target=work,daemon=False).start()
    def poll(self):
        while not self.events.empty():
            msg=self.events.get()
            if msg is None:
                self.running=False;self.run.config(state='normal');self.test.config(state='normal')
            else:
                self.log.config(state='normal');self.log.insert('end',msg+'\n');self.log.see('end');self.log.config(state='disabled')
        self.root.after(100,self.poll)
    def close(self):
        if self.running:
            self.stop.set();messagebox.showinfo('Stopping','Stopping after the current request. Close this window once the run has stopped.');return
        self.root.destroy()

if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
