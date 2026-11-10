import csv
import tempfile
import threading
import unittest
from pathlib import Path
from openpyxl import load_workbook
from spreadsheet_jobs import read_sheet, run_job, csv_records

class CsvTests(unittest.TestCase):
    def test_roundtrip_and_formats(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'in.csv'
            with src.open('w',encoding='utf-8-sig',newline='') as f:
                csv.writer(f).writerows([['ID','Text'],['001','Hello, café\nsecond line']])
            headers,rows=read_sheet(src,'CSV')
            self.assertEqual(rows[2]['ID'],'001');self.assertIn('\n',rows[2]['Text'])
            class Fake:
                def __enter__(self):return self
                def __exit__(self,*a):pass
                def ask(self,p):return '{"Answer":"=1+1"}'
            for extension in ['csv','xlsx']:
                out=Path(td)/('out.'+extension)
                c=dict(a=str(src),b='',sheet_a='CSV',key_a='',key_b='',first=2,last=2,prompt='{{A.Text}}',outputs=['Answer'],output=str(out))
                run_job(c,Fake,threading.Event(),lambda _:None)
                if extension=='csv':
                    records=csv_records(out);self.assertEqual(records[1][0],'001');self.assertEqual(records[1][2],"'=1+1")
                else:
                    ws=load_workbook(out).active;self.assertEqual(ws['A2'].value,'001');self.assertEqual(ws['C2'].data_type,'s')
    def test_semicolon_and_bad_width(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.csv';p.write_text('ID;Text\n001;hello\n',encoding='utf-8')
            self.assertEqual(read_sheet(p,'CSV')[1][2]['ID'],'001')
            p.write_text('ID,Text\n1,hello,extra\n',encoding='utf-8')
            with self.assertRaises(ValueError):csv_records(p)
