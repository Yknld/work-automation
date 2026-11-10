"""Local, configurable replacement of row-derived values; no external services."""
import re
import unicodedata
from difflib import SequenceMatcher


def normalized(value):
    chars=[];positions=[]
    for i,c in enumerate(value):
        for d in unicodedata.normalize('NFKD',c).casefold():
            if d.isalnum():chars.append(d);positions.append(i)
    return ''.join(chars),positions


def rules_for_rows(rules, a, b):
    result=[]
    for rule in rules:
        source=rule.get('source','A');column=rule.get('column','')
        row=a if source=='A' else b
        if source not in ('A','B') or column not in row:
            raise ValueError('Redaction source column unavailable. Check the rule and B matching settings.')
        placeholder=rule.get('placeholder','').strip()
        if not re.fullmatch(r'\[[A-Za-z0-9_ -]+\]',placeholder):
            raise ValueError('Redaction placeholders must look like [COMPANY] or [PRIVATE_VALUE].')
        mode=rule.get('mode','Normalized')
        if mode not in ('Exact','Normalized','Fuzzy'):
            raise ValueError('Unknown redaction matching mode.')
        value=row[column]
        terms=([str(value)] if value is not None and str(value).strip() else [])
        terms += [x.strip() for x in rule.get('aliases','').split(';') if x.strip()]
        for term in terms:
            result.append((term.strip(),placeholder,mode))
    return result


def redact(text, terms):
    """Longest overlapping match wins; placeholders are not processed recursively."""
    spans=[]
    compact,positions=normalized(text)
    protected=[m.span() for placeholder in {r[1] for r in terms}
               for m in re.finditer(re.escape(placeholder),text)]
    def add(start,end,replacement):
        if start and text[start-1]=='(' and ')' in text[start:end] and '(' not in text[start:end]:
            start -= 1
        if any(start<b and end>a for a,b in protected):return
        if start and text[start-1].isalnum() and text[start].isalnum():return
        if end<len(text) and text[end-1].isalnum() and text[end].isalnum():return
        spans.append((start,end,replacement))
    for term,placeholder,mode in terms:
        if not term:continue
        if mode=='Exact':
            for m in re.finditer(re.escape(term),text,re.I):add(*m.span(),placeholder)
            continue
        needle,_=normalized(term)
        if not needle:continue
        for m in re.finditer(re.escape(needle),compact):
            add(positions[m.start()],positions[m.end()-1]+1,placeholder)
        # Conservative fuzzy matching: long alphabetic values only, >=92% similarity.
        # Short aliases, IDs and phone numbers use normalized matching only.
        if mode=='Fuzzy' and len(needle)>=8 and needle.isalpha():
            words=list(re.finditer(r'[^\W\d_]+',text,re.UNICODE))
            count=max(1,len(re.findall(r'[^\W\d_]+',term,re.UNICODE)))
            for i in range(len(words)):
                for n in range(max(1,count-1),count+2):
                    chunk=words[i:i+n]
                    if len(chunk)!=n:continue
                    start,end=chunk[0].start(),chunk[-1].end()
                    if end-start>len(term)*2+10:continue
                    candidate,_=normalized(text[start:end])
                    if SequenceMatcher(None,needle,candidate).ratio()>=.92:add(start,end,placeholder)
    selected=[]
    for span in sorted(spans,key=lambda x:(-(x[1]-x[0]),x[0])):
        if not any(span[0]<b and span[1]>a for a,b,_ in selected):selected.append(span)
    for start,end,replacement in sorted(selected,reverse=True):
        text=text[:start]+replacement+text[end:]
    return text
