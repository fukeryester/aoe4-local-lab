"""Synthetic memory layouts test bounds/failure handling, not live-game accuracy."""
import struct
import unittest
from types import SimpleNamespace
from live_12260 import local_player,production_names,modified_value,population_capacity,army_statistics
from reader_12260 import Entity

class Memory:
    def __init__(self):self.data={}
    def put(self,a,raw):self.data.update({a+i:b for i,b in enumerate(raw)})
    def q(self,a,n):self.put(a,struct.pack('<Q',n))
    def d(self,a,n):self.put(a,struct.pack('<I',n))
    def read(self,a,n):
        try:return bytes(self.data[a+i] for i in range(n))
        except KeyError:raise OSError('unmapped')
    def u64(self,a):return struct.unpack('<Q',self.read(a,8))[0]
    def u32(self,a):return struct.unpack('<I',self.read(a,4))[0]

class LiveAssistanceTests(unittest.TestCase):
    def setUp(self):
        self.p=Memory();self.r=SimpleNamespace(p=self.p,base=0x10000000,arena=0x20000000,players={1007:(4,'red')},player_offsets={10:1007},name=lambda p:'building_town_center_test' if p==0x4444 else 'unit_villager_test')
    def test_local_player_is_id_mapping_not_first_slot(self):
        p=self.p;b=self.r.base;p.q(b+0x7ceada8,100);p.q(100+0x330,200);p.d(200+0x154,1007)
        self.assertEqual(local_player(self.r),4)
        p.d(200+0x154,999);self.assertIsNone(local_player(self.r))
    def queue(self):
        p=self.p;r=self.r;b=r.base;a=0x30000000;e=Entity(42,'building_town_center_test',4,'red',(0,0,0),a)
        raw=bytearray(0x70);struct.pack_into('<Q',raw,0,0x4444);struct.pack_into('<I',raw,8,0x100);struct.pack_into('<H',raw,0x14,191);struct.pack_into('<I',raw,0x68,42)
        p.put(a+0x38,raw);p.q(a,0x4000);p.q(0x40b0,b+0x1f48a80)
        p.put(b+0x7ceb197+191*128,b'\x05');p.q(b+0x85f1990,r.arena);p.q(b+0x85f19c0,0x40000000)
        raw=bytearray(24);struct.pack_into('<I',raw,0,8);struct.pack_into('<Q',raw,8,0x5000);raw[16]=1
        p.put(0x40000000+0x100+5*24,raw);p.d(0x5054,0x6000);p.put(r.arena+0x6040,struct.pack('<II',0x7000,0));return e
    def test_queue_empty_and_villager_order(self):
        e=self.queue();r=self.r;p=self.p
        self.assertEqual(production_names(r,e),[])
        p.d(r.arena+0x6044,1);raw=bytearray(144);struct.pack_into('<I',raw,0x88,0x8000);p.put(r.arena+0x7000,raw)
        p.q(r.arena+0x8000,0x9000);p.q(0x9008,r.base+0x25fc840);p.q(0x9010,r.base+0x25fe370);p.q(r.arena+0x8010,0x5555)
        self.assertEqual(production_names(r,e),['unit_villager_test'])
        p.q(0x9008,0)
        with self.assertRaises(ValueError):production_names(r,e)
    def test_queue_unbounded_and_reused_entity_rejected(self):
        e=self.queue();self.p.d(self.r.arena+0x6044,257)
        with self.assertRaises(ValueError):production_names(self.r,e)
        self.p.d(e.address+0xa0,43)
        with self.assertRaises(ValueError):production_names(self.r,e)
    def modifier(self,descriptor,index):
        p=self.p;r=self.r;b=r.base;mask=0xffffffffffffffff
        encoded=((index^0xed9318d5daf7db22)+0x56a537c05d0681e4)&mask
        p.q(b+descriptor+8,encoded);p.q(b+0x8640d68,0x1000);p.q(0x1000,0x2000);p.d(0x2064,0x100)
        p.d(r.arena+0x100+index*4,1);p.d(0x3300,0x200);p.q(b+0x85f19c0,0x50000000)
        p.d(r.arena+0x200,0x300);p.d(r.arena+0x20c,0x400);p.put(0x50000300+index,b'\x00')
    def test_modifier_add_scale_and_override(self):
        self.modifier(0x8640b58,12);p=self.p
        p.put(0x50000400,struct.pack('<6f4B',2,10,.5,.25,0,77,0,1,0,0))
        self.assertEqual(modified_value(self.r,0x3000,20,0x8640b58),101.25)
        p.put(0x50000418,b'\x01')
        self.assertEqual(modified_value(self.r,0x3000,20,0x8640b58),77)
    def test_capacity_clamps_to_hard_limit(self):
        self.modifier(0x8640b58,12);self.modifier(0x8640bf8,8);p=self.p
        p.put(0x50000308,b'\xff');p.put(0x50000400,struct.pack('<6f4B',0,10,0,0,0,0,0,0,0,0))
        raw=bytearray(40);struct.pack_into('<f',raw,0,200);struct.pack_into('<f',raw,12,200);raw[36:40]=b'\xff\xff\x7f\x7f';p.put(0x3460,raw)
        self.assertEqual(population_capacity(self.r,0x3000),(200,200))
    def test_army_value_uses_resource_vector_and_rejects_tree_cycle(self):
        p=self.p;r=self.r;b=r.base
        p.q(b+0x7ceada8,0x1000);p.q(0x1330,0x2000);p.q(0x2238,0x3000);p.q(0x3000,0x4000);p.q(0x4000,b+0x63e8820)
        p.put(0x40b0,struct.pack('<QQ',0x5000,1));p.q(0x5008,0x6000)
        p.put(b+0x885d1a0+0x2e8,struct.pack('<QQ',0x7000,0x7000+9*48))
        row=bytearray(0x28+0x73c);struct.pack_into('<QQQ',row,0,0x5000,0x5000,0x5000);struct.pack_into('<I',row,0x20,1007)
        struct.pack_into('<9f',row,0x28+0x2c4,20,40,65,0,0,0,0,0,0);struct.pack_into('<I',row,0x28+0x734,3);p.put(0x6000,row)
        self.assertEqual(army_statistics(r),{1007:(125,3)})
        p.q(0x6000,0x6000)
        with self.assertRaises(ValueError):army_statistics(r)

if __name__=='__main__':unittest.main()
