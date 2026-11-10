import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from openpyxl import Workbook, load_workbook
from spreadsheet_jobs import prepare, parse_reply, run_job

class JobsTests(unittest.TestCase):
    def test_tags_match_and_preserve_inserted_braces(self):
        result=prepare('{{A.Text}} / {{B.Value}}',{'ID':'001','Text':'{{literal}}'}, {2:{'Key':'001','Value':'yes'}},'ID','Key')
        self.assertEqual(result,'"{{literal}}" / "yes"')
    def test_missing_and_duplicate_matches(self):
        for rows in ({},{2:{'K':'1'},3:{'K':'1'}}):
            with self.assertRaises(ValueError):prepare('{{B.K}}',{'ID':'1'},rows,'ID','K')
    def test_json_validation(self):
        self.assertEqual(parse_reply('Copilot said: ```json\n{"Answer":"Yes"}\n```',['Answer']),{'Answer':'Yes'})
        for value in ['{"Answer":"Yes","Answer":"No"}','{"Other":"Yes"}','{"Answer":3}','truncated']:
            with self.assertRaises(ValueError):parse_reply(value,['Answer'])
    def test_batch_saves_outputs_as_literal_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'source.xlsx';output=Path(td)/'out.xlsx'
            w=Workbook();w.active.append(['ID','Text']);w.active.append(['001','fiction']);w.active.append(['002','fiction']);w.save(source)
            original=source.read_bytes()
            class Fake:
                def __enter__(self):return self
                def __exit__(self,*a):pass
                def ask(self,p):return '{"Answer":"=1+1"}'
            c=dict(a=str(source),b='',sheet_a='Sheet',key_a='',key_b='',first=2,last=3,prompt='{{A.Text}}',outputs=['Answer'],output=str(output))
            c.update(pause_every=1,pause_minutes=15)
            with patch('spreadsheet_jobs.cooldown',return_value=True) as pause:
                run_job(c,Fake,threading.Event(),lambda _:None)
                self.assertEqual(pause.call_count,1)
                self.assertEqual(pause.call_args.args[0],900)
            out=load_workbook(output);self.assertEqual(out.active['C2'].value,'=1+1');self.assertEqual(out.active['C2'].data_type,'s')
            self.assertEqual(out.active['D3'].value,'Completed');self.assertEqual(source.read_bytes(),original)
            with self.assertRaises(ValueError):run_job(c,Fake,threading.Event(),lambda _:None)
    def test_uncertain_failure_stops_and_saves(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'s.xlsx';out=Path(td)/'o.xlsx';w=Workbook();w.active.append(['Text']);w.active.append(['data']);w.save(source)
            class Fake:
                def __enter__(self):return self
                def __exit__(self,*a):pass
                def ask(self,p):raise RuntimeError('private detail')
            c=dict(a=str(source),b='',sheet_a='Sheet',key_a='',key_b='',first=2,last=2,prompt='{{A.Text}}',outputs=['Answer'],output=str(out))
            with self.assertRaises(RuntimeError):run_job(c,Fake,threading.Event(),lambda _:None)
            self.assertEqual(load_workbook(out).active['C2'].value,'Submission uncertain')

    def test_cleanup_only_after_valid_output_saved(self):
        for reply, expected in [('{"Answer":"Yes"}',1), ('not json',0), ('{"Answer":null}',0)]:
            with tempfile.TemporaryDirectory() as td:
                source=Path(td)/'s.xlsx';out=Path(td)/'o.xlsx'
                w=Workbook();w.active.append(['Text']);w.active.append(['data']);w.save(source)
                deleted=[]
                class Fake:
                    def __enter__(self):return self
                    def __exit__(self,*a):pass
                    def ask(self,p):return reply
                    def delete_saved_chat(self):
                        saved=load_workbook(out)
                        assert saved.active['B2'].value=='Yes'
                        assert saved.active['C2'].value=='Completed'
                        saved.close();deleted.append(True)
                c=dict(a=str(source),b='',sheet_a='Sheet',key_a='',key_b='',first=2,last=2,prompt='{{A.Text}}',outputs=['Answer'],output=str(out),delete_chats=True)
                run_job(c,Fake,threading.Event(),lambda _:None)
                self.assertEqual(len(deleted),expected)
