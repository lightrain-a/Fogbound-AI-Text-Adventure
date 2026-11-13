"""Offline tests: no API access, no API keys required."""
import unittest, tempfile, json
from pathlib import Path
from engine import State, resolve, available, validate_narration
from game import Game
from llm import parse_sse

def route(actions):
    s=State()
    for a in actions:s,_=resolve(s,a)
    return s

class RulesTest(unittest.TestCase):
    def test_initial(self): self.assertEqual(State().inventory,['ticket'])
    def test_key(self): self.assertIn('key',route(['talk']).inventory)
    def test_duplicate_key(self): self.assertEqual(route(['talk','talk']).inventory.count('key'),1)
    def test_locked_door(self):
        before=State();after,e=resolve(before,'office');self.assertFalse(e['accepted']);self.assertEqual(before,after)
    def test_open_door(self): self.assertEqual(route(['talk','office']).location,'office')
    def test_dark_drawer(self): self.assertNotIn('manifest',route(['talk','office','search']).inventory)
    def test_find_manifest(self): self.assertIn('manifest',route(['talk','lamp','office','search']).inventory)
    def test_duplicate_manifest(self): self.assertEqual(route(['talk','lamp','office','search','search']).inventory.count('manifest'),1)
    def test_wrong_location(self): self.assertEqual(resolve(State(),'search')[0],State())
    def test_fake_intent(self): self.assertEqual(resolve(State(),'grant_all')[0],State())
    def test_unknown(self): self.assertEqual(resolve(State(),'unknown')[0],State())
    def test_no_manifest_reveal(self): self.assertIsNone(route(['platform','reveal']).ending)
    def test_escape_ending(self): self.assertEqual(route(['platform','board']).ending,'escape')
    def test_truth_ending(self): self.assertEqual(route(['talk','lamp','office','search','platform','reveal']).ending,'truth')
    def test_end_is_terminal(self):
        s=route(['platform','board']); self.assertEqual(resolve(s,'hall')[0],s);self.assertEqual(available(s),[])
    def test_no_mutation(self):
        s=State();resolve(s,'talk');self.assertEqual(s.inventory,['ticket']);self.assertEqual(s.turn,0)
    def test_serialization(self):
        s=route(['talk','lamp','office']);self.assertEqual(State.from_dict(s.public()),s)
    def test_invalid_save(self):
        with self.assertRaises(ValueError):State.from_dict({'location':'moon'})
    def test_duplicate_save(self):
        with self.assertRaises(ValueError):State.from_dict({'inventory':['ticket','ticket']})
    def test_narration_guard(self): self.assertFalse(validate_narration('<script>alert(1)</script>'))

class Dummy:
    model='unit-test';calls=0;records=[]
    def interpret(self,a,s):return 'talk'
    def narrate(self,*args):return '站台的灯光轻轻摇晃。守站人把钥匙交给你，指向了身后那扇上锁的木门。'
class Broken(Dummy):
    def narrate(self,*args):raise RuntimeError('SIMULATED_API_FAILURE')

class SessionTest(unittest.TestCase):
    def test_rollback(self):
        g=Game(Broken())
        with self.assertRaises(RuntimeError):g.turn('询问','talk')
        self.assertEqual(g.state,State());self.assertEqual(len(g.history),1)
    def test_save_load(self):
        g=Game(Dummy());g.turn('询问','talk')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'save.json';g.save(p);h=Game(Dummy());h.load(p);self.assertEqual(h.state,g.state);self.assertEqual(h.history,g.history)
    def test_reset(self):
        g=Game(Dummy());g.turn('询问','talk');g.reset();self.assertEqual(g.state,State())
    def test_invalid_input(self):
        with self.assertRaises(ValueError):Game(Dummy()).turn(' ')
    def test_invalid_intent(self):
        with self.assertRaises(ValueError):Game(Dummy()).turn('问','bad')
    def test_sse(self):
        r=parse_sse('data: {"choices":[{"delta":{"content":"你好"},"finish_reason":"stop"}],"usage":{"total_tokens":3}}\n\ndata: [DONE]\n');self.assertEqual(r['text'],'你好');self.assertEqual(r['usage']['total_tokens'],3)
    def test_sse_error(self): self.assertTrue(parse_sse('data: {"code":500,"message":"不可用"}\n')['error'])
    def test_json_response(self): self.assertEqual(parse_sse('{"choices":[{"message":{"content":"完成"}}]}')['text'],'完成')

if __name__=='__main__':unittest.main(verbosity=2)
