import unittest
from redaction import redact
from spreadsheet_jobs import prepare

class RedactionTests(unittest.TestCase):
    def test_phone_and_boundaries(self):
        self.assertEqual(redact('Call (613) 555-0123 or 161355501234.', [('613-555-0123','[PHONE]','Normalized')]),'Call [PHONE] or 161355501234.')
    def test_case_accents_alias_and_overlap(self):
        terms=[('Café North','[ORG]','Normalized'),('CN','[ORG]','Normalized'),('North','[PLACE]','Exact')]
        self.assertEqual(redact('CAFE NORTH and CN, not CNC.',terms),'[ORG] and [ORG], not CNC.')
    def test_bracketed_sensitive_values(self):
        self.assertEqual(redact('[Acme]',[('Acme','[ORG]','Exact')]),'[[ORG]]')
    def test_fuzzy(self):
        self.assertEqual(redact('North Valley Associaton', [('North Valley Association','[ORG]','Fuzzy')]),'[ORG]')
    def test_all_prompt_values_and_literal_redacted(self):
        rules=[dict(source='A',column='Company',placeholder='[ORG]',mode='Normalized',aliases='NVCA')]
        result=prepare('Check NVCA: {{A.Answer}}',{'Company':'North Valley','Answer':'NORTH VALLEY and NVCA'},redaction_rules=rules)
        self.assertNotIn('NVCA',result);self.assertNotIn('VALLEY',result)
        self.assertEqual(result,'Check [ORG]: "[ORG] and [ORG]"')
    def test_b_rule_requires_match_even_without_b_tag(self):
        rules=[dict(source='B',column='Secret',placeholder='[PRIVATE]',mode='Exact')]
        with self.assertRaises(ValueError):prepare('{{A.Text}}',{'Text':'hidden'},redaction_rules=rules)
        self.assertEqual(prepare('{{A.Text}}',{'Text':'hidden','ID':1},{2:{'ID':1,'Secret':'hidden'}},'ID','ID',rules),'"[PRIVATE]"')
    def test_missing_rule_column_blocks(self):
        with self.assertRaises(ValueError):prepare('{{A.Text}}',{'Text':'data'},redaction_rules=[dict(source='A',column='Missing',placeholder='[X]')])
    def test_numeric_zero_is_redacted(self):
        self.assertEqual(prepare('{{A.Value}}',{'Value':0},redaction_rules=[dict(source='A',column='Value',placeholder='[VALUE]')]),'"[VALUE]"')
