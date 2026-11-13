"""Transactional game session; no state change is committed on a model failure."""
from __future__ import annotations
import json, copy, threading
from pathlib import Path
from datetime import datetime, timezone
from engine import State, ACTIONS, INTRO, available, resolve
from llm import Client

class Game:
    def __init__(self, client: Client):
        self.client = client
        self.lock = threading.Lock()
        self.state = State()
        self.history = [{'action':'故事开始','narration':INTRO,'source':'authored_opening','state':self.state.public()}]

    def public(self):
        return {'state':self.state.public(), 'actions':available(self.state),
                'history':copy.deepcopy(self.history), 'model':self.client.model,
                'requests_this_session':self.client.calls,
                'tokens_observed':sum((r.get('usage') or {}).get('total_tokens',0) for r in self.client.records),
                'usage_complete':all(r.get('usage') is not None for r in self.client.records),
                'mode':'live','title':'雾港末班车'}

    def turn(self, action: str, intent: str | None = None):
        if not isinstance(action,str) or not 1 <= len(action.strip()) <= 500:
            raise ValueError('行动请输入1至500字。')
        if not self.lock.acquire(blocking=False): raise RuntimeError('上一回合仍在生成，请勿重复提交。')
        try:
            if self.state.ending: raise ValueError('本局已结束；请重新开始。')
            if intent is not None and intent not in ACTIONS: raise ValueError('无效动作ID')
            before = copy.deepcopy(self.state)
            resolved = intent or self.client.interpret(action.strip(),before)
            after, event = resolve(before,resolved)
            text = self.client.narrate(action,before,after,event,self.history[-1]['narration'])
            # Commit only after the narrator returned a usable final response.
            self.state = after
            self.history.append({'action':action,'intent':resolved,'event':event,
                'narration':text,'source':'live_api','state':after.public(),
                'timestamp_utc':datetime.now(timezone.utc).isoformat()})
            return self.public()
        finally: self.lock.release()

    def save(self, path: Path):
        with self.lock:
            data={'schema':1,'state':self.state.public(),'history':self.history,'model':self.client.model}
            tmp=path.with_suffix('.tmp')
            tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            tmp.replace(path)

    def load(self, path: Path):
        with self.lock:
            if path.stat().st_size>2_000_000: raise ValueError('存档过大')
            raw=json.loads(path.read_text(encoding='utf-8'))
            state=State.from_dict(raw['state'])
            history=raw.get('history')
            if not isinstance(history,list) or not history or len(history)>101: raise ValueError('存档历史无效')
            for entry in history:
                if not isinstance(entry,dict) or not isinstance(entry.get('narration'),str): raise ValueError('存档段落无效')
            if history[-1].get('state',{}).get('location')!=state.location: raise ValueError('存档状态不一致')
            self.state,self.history=state,history

    def reset(self):
        with self.lock:
            self.state=State()
            self.history=[{'action':'故事开始','narration':INTRO,'source':'authored_opening','state':self.state.public()}]
