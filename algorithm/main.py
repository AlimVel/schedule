#!/usr/bin/env python3
"""
Расписание университета — быстрый Greedy + Local Search солвер
Для масштаба 100-300 событий/неделю.

python3 solve.py [--input real_input.json] [--weeks 18] [--week 1]
"""

import json, os, sys, time, math, random
from collections import defaultdict
from datetime import datetime

def load_json(p):
    with open(p,'r',encoding='utf-8') as f: return json.load(f)
def save_json(d,p):
    with open(p,'w',encoding='utf-8') as f: json.dump(d,f,ensure_ascii=False,indent=2)

# ═══════════════════════════════════════════════════════════
#  MODEL
# ═══════════════════════════════════════════════════════════

class Model:
    def __init__(self, inp, state, week_num):
        self.inp = inp; self.state = state; self.week_num = week_num
        s = inp['settings']
        self.DAYS=s['days']; self.NS=s['max_pairs_per_day']
        self.ND=len(self.DAYS); self.TOTAL=self.ND*self.NS
        self.slot_times=s.get('slot_times',{})
        self.weights=s.get('solver',{})
        self.SEM_WEEKS=s.get('semester_weeks',18)

        self.rooms=inp['rooms']
        self.room_ids=[r['id'] for r in self.rooms]
        self.R2I={r['id']:i for i,r in enumerate(self.rooms)}
        self.room_map={r['id']:r for r in self.rooms}
        self.groups={g['id']:g for g in inp['groups']}
        self.teachers={t['id']:t for t in inp['teachers']}

        self.teacher_forbidden={}
        self.teacher_preferred={}
        for t_id,t in self.teachers.items():
            self.teacher_forbidden[t_id]=self._avail(t.get('unavailable',[]))
            self.teacher_preferred[t_id]=self._avail(t.get('preferred',[]))

        self.events=[]; self.links=[]
        self._build_events()
        
        self.teacher_evts=defaultdict(list)
        self.group_evts=defaultdict(list)
        for e in self.events:
            self.teacher_evts[e['teacher']].append(e['id'])
            for g in e['groups']: self.group_evts[g].append(e['id'])
        
        self.link_map={}
        for a,b in self.links: self.link_map[a]=b; self.link_map[b]=a

    def _avail(self,rules):
        r=set()
        for rule in rules:
            d=rule.get('day')
            if d not in self.DAYS: continue
            di=self.DAYS.index(d)
            sl=rule.get('slots')
            if sl:
                for s in sl:
                    if 1<=s<=self.NS: r.add(di*self.NS+(s-1))
            else:
                for s in range(self.NS): r.add(di*self.NS+s)
        return r

    def _get_rooms(self, room_type, total_st, fixed_room=None):
        if fixed_room and fixed_room in self.R2I:
            return [self.R2I[fixed_room]]
        max_sem=max((r['capacity'] for r in self.rooms if r['type']=='seminar'),default=0)
        large=total_st>max_sem
        out=[]
        for room in self.rooms:
            if room['type']=='comp':
                if room_type!='comp': continue
            elif room['type']=='special':
                if room_type!='special': continue
            else:
                if room_type in ('comp','special'): continue
            if room_type=='lecture' and room['type']!='lecture': continue
            if room_type=='seminar':
                if large:
                    if room['type']!='lecture': continue
                else:
                    if room['type'] not in ('seminar','lecture'): continue
            if room.get('capacity',999)<total_st: continue
            # Deprioritize low_priority rooms (append at end)
            out.append(self.R2I[room['id']])
        # Sort: non-low-priority first
        out.sort(key=lambda ri: 1 if self.rooms[ri].get('low_priority') else 0)
        return out

    def _det_hash(self, s):
        """Детерминированный хэш для создания псевдослучайного смещения по неделям"""
        return sum(ord(c)*(i+1) for i,c in enumerate(s))

    def _ppw(self,subj,kind,gid=None):
        sid=subj['id']
        rem=self.state['remaining']
        wl=max(1,self.SEM_WEEKS-self.week_num+1)
        if kind=='lecture':
            key=f"{sid}__lec"; total=subj['lecture']['total_pairs']
        else:
            key=f"{sid}__sem__{gid}" if gid else f"{sid}__sem"
            total=subj['seminar'].get('total_pairs_per_group',36)
        remaining=rem.get(key,total)
        if remaining<=0: return 0
        
        # Равномерное распределение по неделям
        ideal = remaining / wl
        # Смещение (от 0.0 до 0.99) на основе ключа состояния. 
        offset = (self._det_hash(key) % 100) / 100.0
        ppw = int(ideal + offset)
        
        ppw=min(ppw,remaining)
        
        # Ordering
        ordering=subj.get('ordering')
        if ordering and kind=='seminar' and subj.get('lecture'):
            lk=f"{sid}__lec"; lt=subj['lecture']['total_pairs']
            lg=lt-rem.get(lk,lt)
            ml=ordering.get('min_lectures_before_seminars_start',0)
            ratio=ordering.get('lecture_to_seminar_ratio',0.5)  # default: 1 лекция → 2 семинара
            unlocked=max(0,(lg-ml)/ratio) if ratio>0 else 999
            sg=total-remaining; cg=max(0,int(unlocked)-sg)
            ppw=min(ppw,max(1,cg))
        return max(0,ppw)

    def _build_events(self):
        eid=0
        for subj in self.inp['subjects']:
            sid=subj['id']; grps=subj['groups']
            
            if subj.get('lecture'):
                lec=subj['lecture']
                ppw=self._ppw(subj,'lecture')
                if ppw>0:
                    tst=sum(self.groups[g]['students'] for g in grps if g in self.groups)
                    rms=self._get_rooms(lec.get('room_type','lecture'),tst,lec.get('fixed_room'))
                    if rms:
                        for _ in range(ppw):
                            self.events.append({'id':eid,'subject_id':sid,'subject':subj['name'],
                                'kind':'lecture','teacher':lec['teacher'],'groups':list(grps),
                                'rooms':list(rms),'state_key':f"{sid}__lec"})
                            eid+=1

            if subj.get('seminar'):
                sem=subj['seminar']; st=sem.get('type','seminar')
                rt=sem.get('room_type',st if st!='comp' else 'comp')

                if sem.get('subgroups'):
                    subs=sem['subgroups']; simul=sem.get('simultaneous',False)
                    all_sg=[]
                    for sg in subs:
                        sg_g=sg.get('groups',grps)
                        ppw=self._ppw(subj,'seminar',sg['id'])
                        if ppw<=0: continue
                        tst=sum(self.groups[g]['students'] for g in sg_g if g in self.groups)//max(1,len(subs))
                        rms=self._get_rooms(rt,tst,sg.get('fixed_room'))
                        if not rms: continue
                        knd='comp' if st=='comp' else 'seminar'
                        sg_eids=[]
                        for _ in range(ppw):
                            self.events.append({'id':eid,'subject_id':sid,'subject':subj['name'],
                                'kind':knd,'teacher':sg['teacher'],'groups':sg_g,
                                'rooms':list(rms),'subgroup_id':sg['id'],
                                'state_key':f"{sid}__sem__{sg['id']}"})
                            sg_eids.append(eid); eid+=1
                        all_sg.append(sg_eids)
                    if simul and len(all_sg)>=2:
                        ml=min(len(se) for se in all_sg)
                        for i in range(ml):
                            for j in range(1,len(all_sg)):
                                self.links.append((all_sg[0][i],all_sg[j][i]))

                elif sem.get('per_group'):
                    for g in grps:
                        ppw=self._ppw(subj,'seminar',g)
                        if ppw<=0: continue
                        tst=self.groups[g]['students'] if g in self.groups else 20
                        rms=self._get_rooms(rt,tst)
                        if not rms: continue
                        for _ in range(ppw):
                            self.events.append({'id':eid,'subject_id':sid,'subject':subj['name'],
                                'kind':'seminar','teacher':sem['teacher'],'groups':[g],
                                'rooms':list(rms),'state_key':f"{sid}__sem__{g}"})
                            eid+=1
                else:
                    ppw=self._ppw(subj,'seminar')
                    if ppw>0:
                        tst=sum(self.groups[g]['students'] for g in grps if g in self.groups)
                        rms=self._get_rooms(rt,tst)
                        if rms:
                            for _ in range(ppw):
                                self.events.append({'id':eid,'subject_id':sid,'subject':subj['name'],
                                    'kind':'seminar','teacher':sem['teacher'],'groups':list(grps),
                                    'rooms':list(rms),'state_key':f"{sid}__sem"})
                                eid+=1


# ═══════════════════════════════════════════════════════════
#  GREEDY + LOCAL SEARCH SOLVER
# ═══════════════════════════════════════════════════════════

class GreedySolver:
    def __init__(self, model):
        self.m = model
        self.N = len(model.events)
        self.events = model.events
        w = model.weights
        self.W_EVEN = w.get('weight_even_distribution',10)
        self.W_MORN = w.get('weight_prefer_morning',5)
        self.W_GAPS = w.get('weight_no_gaps', 3000)
        self.W_ROOM = w.get('weight_room_stickiness',15)
        self.W_SINGLE = 0
        self.W_MSPD = w.get('weight_max_same_subject_per_day',60)
        self.W_PREF = w.get('weight_teacher_preferred', 8000)
        self.W_LBS = w.get('weight_lecture_before_seminar', 500)
        
        self.asgn = [None]*self.N
        self._tch_ts = defaultdict(set)
        self._grp_ts = defaultdict(set)
        self._room_ts = defaultdict(set)
        self._tch_day = defaultdict(lambda: defaultdict(int))
        self._tch_day_slots = defaultdict(lambda: defaultdict(set))
        self._grp_day = defaultdict(lambda: defaultdict(int))
        self._grp_day_slots = defaultdict(lambda: defaultdict(set))
        self._skd = defaultdict(int)
        self._sdr = defaultdict(lambda: defaultdict(set))
        self._lec_ts = defaultdict(set)
        self._sem_ts = defaultdict(set)

    def _do(self, eid, ts, r):
        self.asgn[eid]=(ts,r); e=self.events[eid]; d=ts//self.m.NS; s=ts%self.m.NS
        self._tch_ts[e['teacher']].add(ts)
        self._tch_day[e['teacher']][d]+=1
        self._tch_day_slots[e['teacher']][d].add(s)
        for g in e['groups']:
            self._grp_ts[g].add(ts); self._grp_day[g][d]+=1
            self._grp_day_slots[g][d].add(s)
        self._room_ts[ts].add(r)
        self._skd[(e['subject_id'],e['kind'],d)]+=1
        self._sdr[e['subject_id']][d].add(r)
        if e['kind']=='lecture': self._lec_ts[e['subject_id']].add(ts)
        elif e['kind'] in ('seminar','comp'): self._sem_ts[e['subject_id']].add(ts)

    def _un(self, eid):
        ts,r=self.asgn[eid]; self.asgn[eid]=None
        e=self.events[eid]; d=ts//self.m.NS; s=ts%self.m.NS
        self._tch_ts[e['teacher']].discard(ts)
        self._tch_day[e['teacher']][d]-=1
        self._tch_day_slots[e['teacher']][d].discard(s)
        for g in e['groups']:
            self._grp_ts[g].discard(ts); self._grp_day[g][d]-=1
            self._grp_day_slots[g][d].discard(s)
        self._room_ts[ts].discard(r)
        self._skd[(e['subject_id'],e['kind'],d)]-=1
        self._sdr[e['subject_id']][d].discard(r)
        if e['kind']=='lecture': self._lec_ts[e['subject_id']].discard(ts)
        elif e['kind'] in ('seminar','comp'): self._sem_ts[e['subject_id']].discard(ts)

    def _ok(self, eid, ts, r, level=2):
        """
        Уровни жёсткости (применяются каскадно сверху вниз):
          level=2  strict   – все правила
          level=1  relaxed  – без lec/sem ordering, без max_per_day для группы
          level=0  minimal  – без max_per_day, без окон для ГРУПП,
                              но preferred + teacher-no-gaps ВСЕГДА хард
          level=-1 last     – как 0, но разрешаем окна для преподавателя
                              (только если preferred уже заняты — крайний случай)
          level=-2 forced   – допускаются абсолютно все слоты, проверка только коллизий
        """
        e=self.events[eid]; d=ts//self.m.NS; s=ts%self.m.NS

        # ══ АБСОЛЮТНЫЙ ХАД (все уровни, без исключений) ══════════════════
        if r in self._room_ts[ts]: return False
        if ts in self._tch_ts[e['teacher']]: return False
        for g in e['groups']:
            if ts in self._grp_ts[g]: return False
        if eid in self.m.link_map:
            p=self.m.link_map[eid]
            if self.asgn[p] is not None and self.asgn[p][0]!=ts: return False

        # Форсированное размещение: только проверка пересечений
        if level == -2:
            return True

        # Запреты преподавателя — всегда хард
        fb=self.m.teacher_forbidden.get(e['teacher'],set())
        if ts in fb: return False

        # Preferred — всегда хард (если заданы, значит преподаватель физически
        # не может в другое время)
        pref=self.m.teacher_preferred.get(e['teacher'],set())
        if pref and ts not in pref: return False

        # Без окон у ПРЕПОДАВАТЕЛЯ — всегда хард (кроме level=-1 rescue)
        if level >= 0:
            tch_occ=self._tch_day_slots[e['teacher']][d]
            if tch_occ:
                tmn,tmx=min(tch_occ),max(tch_occ)
                if s<tmn-1 or s>tmx+1: return False

        if level == -1:
            # Крайний rescue: окна у препода допускаем, группы не проверяем
            return True

        # ── level 0+: без окон для ГРУПП ─────────────────────────────────
        if level >= 1:
            for g in e['groups']:
                occ=self._grp_day_slots[g][d]
                if occ:
                    mn,mx=min(occ),max(occ)
                    if s<mn-1 or s>mx+1: return False

        # ── level 1+: max_per_day ─────────────────────────────────────────
        if level >= 1:
            ti=self.m.teachers.get(e['teacher'],{})
            if self._tch_day[e['teacher']][d]>=ti.get('max_pairs_per_day',self.m.NS):
                return False

        # ── лекция строго раньше семинара (все уровни кроме forced) ───
        sid=e['subject_id']
        if e['kind'] in ('seminar','comp'):
            lec_slots=self._lec_ts.get(sid)
            if lec_slots and ts<=min(lec_slots): return False
        elif e['kind']=='lecture':
            sem_slots=self._sem_ts.get(sid)
            if sem_slots and ts>=min(sem_slots): return False
 
        if level <= 1:
            return True
 
        return True
    def _score(self, eid, ts, r):
        e=self.events[eid]; d=ts//self.m.NS; s=ts%self.m.NS
        sc=0
        
        for g in e['groups']:
            cnt = self._grp_day[g][d]
            sc += (cnt ** 2) * self.W_EVEN

        sc += s * self.W_MORN
        
        for g in e['groups']:
            occ=self._grp_day_slots[g][d]
            if not occ:
                sc += s*3
        
        tch_occ = self._tch_day_slots[e['teacher']][d]
        if not tch_occ:
            sc += s * 3

        used=self._sdr[e['subject_id']][d]
        if used:
            if r in used: sc-=self.W_ROOM
            else: sc+=self.W_ROOM//3

        if self.m.rooms[r].get('low_priority'): sc+=20
        
        cur=self._skd.get((e['subject_id'],e['kind'],d),0)
        if cur>=2: sc+=self.W_MSPD
        return sc

    def _sorted_slots(self, teacher):
        """Возвращает слоты: если есть preferred — строго только их."""
        pref = self.m.teacher_preferred.get(teacher, set())
        fb   = self.m.teacher_forbidden.get(teacher, set())
        total = self.m.TOTAL
        
        if pref:
            return [ts for ts in range(total) if ts in pref and ts not in fb]
        else:
            return [ts for ts in range(total) if ts not in fb]

    def solve(self):
        t0=time.time()
        N=self.N
        print(f"\n  🔄 Greedy solver: {N} событий")

        # ── Порядок размещения: самые ограниченные — первыми ────────────
        linked_done=set()
        linked_order=[]
        for a,b in self.m.links:
            if a not in linked_done:
                linked_order.extend([a,b])
                linked_done.add(a); linked_done.add(b)

        remaining=[eid for eid in range(N) if eid not in linked_done]

        def sort_key(eid):
            e=self.events[eid]
            has_pref=1 if self.m.teacher_preferred.get(e['teacher']) else 0
            dom=self._effective_slots(eid)
            return (1-has_pref, dom)   # preferred-события первыми, затем по domain

        remaining.sort(key=sort_key)
        final_order=linked_order+remaining

        # ── Жадный проход ────────────────────────────────────────────────
        placed=0; failed=[]

        for eid in final_order:
            if self.asgn[eid] is not None:
                placed+=1; continue

            e=self.events[eid]

            # Связанная пара (simultaneous subgroups)
            if eid in self.m.link_map and self.asgn[self.m.link_map[eid]] is None:
                partner=self.m.link_map[eid]
                best=None; best_sc=float('inf')
                for lvl in (2,1,0):
                    for ts in range(self.m.TOTAL):
                        for r in e['rooms']:
                            if not self._ok(eid,ts,r,lvl): continue
                            self._do(eid,ts,r)
                            for r2 in self.events[partner]['rooms']:
                                if self._ok(partner,ts,r2,lvl):
                                    sc=self._score(eid,ts,r)+self._score(partner,ts,r2)
                                    if sc<best_sc: best_sc=sc; best=(ts,r,r2)
                            self._un(eid)
                    if best: break
                if best:
                    ts,r,r2=best
                    self._do(eid,ts,r); self._do(partner,ts,r2); placed+=2
                else:
                    failed.extend([eid,partner])
                continue

            if self.asgn[eid] is not None: continue

            best=None; best_sc=float('inf')
            slots=self._sorted_slots(e['teacher'])
            for lvl in (2,1,0):
                for ts in slots:
                    for r in e['rooms']:
                        if self._ok(eid,ts,r,lvl):
                            sc=self._score(eid,ts,r)
                            if sc<best_sc: best_sc=sc; best=(ts,r)
                if best: break

            if best:
                self._do(eid,best[0],best[1]); placed+=1
            else:
                failed.append(eid)

        # ── RESCUE 1: swap, preferred + teacher-no-gaps хард ────────────
        if failed:
            still=[]
            for eid in failed:
                if self._swap_rescue(eid, min_level=0):
                    placed+=1
                else:
                    still.append(eid)
            failed=still

        # ── RESCUE 2: swap с допустимым окном у препода (level=-1) ──────
        if failed:
            still=[]
            for eid in failed:
                e=self.events[eid]
                # Сначала пробуем напрямую с level=-1 (окно у препода допускаем)
                best=None; best_sc=float('inf')
                slots=self._sorted_slots(e['teacher'])
                for ts in slots:
                    for r in e['rooms']:
                        if self._ok(eid,ts,r,-1):
                            sc=self._score(eid,ts,r)
                            if sc<best_sc: best_sc=sc; best=(ts,r)
                if best:
                    self._do(eid,best[0],best[1]); placed+=1
                    print(f"  ⚠️  Rescue-2 (окно у препода): {e['subject']} ({e['teacher']})")
                elif self._swap_rescue(eid, min_level=-1):
                    placed+=1
                    print(f"  ⚠️  Rescue-2 swap: {e['subject']} ({e['teacher']})")
                else:
                    still.append(eid)
            failed=still

        # ── RESCUE 3: ФОРСИРОВАННОЕ РАЗМЕЩЕНИЕ (100% гарантия, level=-2) ──────
        if failed:
            still = []
            for eid in failed:
                e = self.events[eid]
                best = None; best_sc = float('inf')
                slots = range(self.m.TOTAL)
                for ts in slots:
                    for r in e['rooms']:
                        if self._ok(eid, ts, r, -2):
                            sc = self._score(eid, ts, r)
                            if sc < best_sc: best_sc = sc; best = (ts, r)
                if best:
                    self._do(eid, best[0], best[1]); placed += 1
                    print(f"  🚨  Rescue-3 (FORCED): {e['subject']} ({e['teacher']})")
                else:
                    still.append(eid)
            failed = still

        el=time.time()-t0
        if failed:
            print(f"  ❌ НЕРАЗМЕЩЕНО {len(failed)}/{N} — невозможно при данных preferred/forbidden:")
            for eid in failed[:8]:
                e=self.events[eid]
                pref=self.m.teacher_preferred.get(e['teacher'],set())
                print(f"    - {e['subject']} | {e['teacher']} | preferred слотов: {len(pref)}")

        improvements=self._local_search()

        el=time.time()-t0
        print(f"  ✅ Размещено {placed}/{N}, улучшений: {improvements} ({el:.2f}s)")
        return len(failed)==0

    def _effective_slots(self, eid):
        """Реальный размер домена: preferred∩¬forbidden × rooms."""
        e=self.events[eid]
        pref=self.m.teacher_preferred.get(e['teacher'],set())
        fb=self.m.teacher_forbidden.get(e['teacher'],set())
        slots=pref-fb if pref else set(range(self.m.TOTAL))-fb
        return len(slots)*len(e['rooms'])

    def _swap_rescue(self, eid, min_level=0):
        """
        Находит единственный блокирующий eid2, убирает его,
        ставит eid (с уровнем min_level), потом перекладывает eid2.
        Preferred + teacher-no-gaps у обоих событий соблюдаются при min_level=0.
        """
        e=self.events[eid]
        total=self.m.TOTAL
        slots=self._sorted_slots(e['teacher'])  # preferred или все без forbidden

        for ts in slots:
            for r in e['rooms']:
                # Собираем блокирующие события
                blockers=set()
                if r in self._room_ts[ts]:
                    for b,a in enumerate(self.asgn):
                        if a and a[0]==ts and a[1]==r:
                            blockers.add(b); break
                if ts in self._tch_ts[e['teacher']]:
                    for b in self.m.teacher_evts.get(e['teacher'],[]):
                        if self.asgn[b] and self.asgn[b][0]==ts: blockers.add(b)
                for g in e['groups']:
                    if ts in self._grp_ts[g]:
                        for b in self.m.group_evts.get(g,[]):
                            if self.asgn[b] and self.asgn[b][0]==ts: blockers.add(b)

                if len(blockers)!=1: continue
                blk=next(iter(blockers))
                blk_ts,blk_r=self.asgn[blk]
                blk_e=self.events[blk]

                self._un(blk)
                if self._ok(eid,ts,r,min_level):
                    self._do(eid,ts,r)
                    # Перекладываем блокирующее с теми же ограничениями
                    blk_slots=self._sorted_slots(blk_e['teacher'])
                    for ts2 in blk_slots:
                        for r2 in blk_e['rooms']:
                            if self._ok(blk,ts2,r2,min_level):
                                self._do(blk,ts2,r2)
                                return True
                    self._un(eid)
                self._do(blk,blk_ts,blk_r)
        return False

    def _will_create_gap_if_removed(self, eid):
        old_ts = self.asgn[eid][0]
        d = old_ts // self.m.NS
        s = old_ts % self.m.NS
        for g in self.events[eid]['groups']:
            occ = self._grp_day_slots[g][d]
            if len(occ) >= 3:
                mn, mx = min(occ), max(occ)
                if mn < s < mx: return True
        tch = self.events[eid]['teacher']
        tch_occ = self._tch_day_slots[tch][d]
        if len(tch_occ) >= 3:
            tmn, tmx = min(tch_occ), max(tch_occ)
            if tmn < s < tmx: return True
        return False

    def _local_search(self, max_iter=20000):
        """Phase A: Агрессивно ликвидируем дни с 1 парой. Окна устранять больше не нужно."""
        improvements=0
        m=self.m

        all_groups=sorted(set(g for e in self.events for g in e['groups']))
        for _iter in range(max_iter//2):
            if not all_groups: break
            grp=random.choice(all_groups)
            eids_g=m.group_evts.get(grp,[])
            
            day_pairs=defaultdict(list)
            for eid in eids_g:
                if self.asgn[eid] is None: continue
                d=self.asgn[eid][0]//m.NS
                day_pairs[d].append(eid)
                
            single_days=[d for d,lst in day_pairs.items() if len(lst)==1]
            target_days=[d for d,lst in day_pairs.items() if len(lst)>=1]
            
            if not single_days or len(target_days) < 2: continue

            src_day=random.choice(single_days)
            tgt_day=random.choice(target_days)
            if src_day == tgt_day: continue
            
            eid=day_pairs[src_day][0]
            if self._will_create_gap_if_removed(eid): continue

            e=self.events[eid]
            old_ts,old_r=self.asgn[eid]
            old_sc=self._total_score_for(eid)

            self._un(eid)
            best=None; best_sc=float('inf')
            for lvl in (2,1):
                for s in range(m.NS):
                    new_ts=tgt_day*m.NS+s
                    for r in e['rooms']:
                        if self._ok(eid,new_ts,r,lvl):
                            sc=self._score(eid,new_ts,r)
                            if sc<best_sc: best_sc=sc; best=(new_ts,r)
                if best: break
            if best and best_sc<old_sc-1:
                self._do(eid,best[0],best[1]); improvements+=1
            else:
                self._do(eid,old_ts,old_r)

        all_teachers = sorted(set(e['teacher'] for e in self.events))
        for _iter in range(max_iter // 2):
            if not all_teachers: break
            tch = random.choice(all_teachers)
            eids_t = m.teacher_evts.get(tch, [])

            day_pairs_t = defaultdict(list)
            for eid in eids_t:
                if self.asgn[eid] is None: continue
                d = self.asgn[eid][0] // m.NS
                day_pairs_t[d].append(eid)

            single_days_t = [d for d, lst in day_pairs_t.items() if len(lst) == 1]
            target_days_t = [d for d, lst in day_pairs_t.items() if len(lst) >= 1]
            if not single_days_t or len(target_days_t) < 2: continue

            src_day = random.choice(single_days_t)
            tgt_day = random.choice(target_days_t)
            if src_day == tgt_day: continue

            eid = day_pairs_t[src_day][0]
            if self._will_create_gap_if_removed(eid): continue

            e = self.events[eid]
            old_ts, old_r = self.asgn[eid]
            old_sc = self._total_score_for(eid)

            self._un(eid)
            best = None; best_sc = float('inf')
            for lvl in (2,1):
                for s in range(m.NS):
                    new_ts = tgt_day * m.NS + s
                    for r in e['rooms']:
                        if self._ok(eid, new_ts, r, lvl):
                            sc = self._score(eid, new_ts, r)
                            if sc < best_sc: best_sc = sc; best = (new_ts, r)
                if best: break
            if best and best_sc < old_sc - 1:
                self._do(eid, best[0], best[1]); improvements += 1
            else:
                self._do(eid, old_ts, old_r)

        return improvements
        
    def _total_score_for(self,eid):
        ts,r=self.asgn[eid]
        return self._score(eid,ts,r)


# ═══════════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════════

def init_state(inp):
    st={'generated_at':None,'semester_weeks':inp['settings'].get('semester_weeks',18),
        'current_week':0,'remaining':{},'history':[]}
    for subj in inp['subjects']:
        sid=subj['id']
        if subj.get('lecture'):
            st['remaining'][f"{sid}__lec"]=subj['lecture']['total_pairs']
        if subj.get('seminar'):
            sem=subj['seminar']
            if sem.get('subgroups'):
                for sg in sem['subgroups']:
                    st['remaining'][f"{sid}__sem__{sg['id']}"]=sem.get('total_pairs_per_group',36)
            elif sem.get('per_group'):
                for g in subj['groups']:
                    st['remaining'][f"{sid}__sem__{g}"]=sem['total_pairs_per_group']
            else:
                st['remaining'][f"{sid}__sem"]=sem.get('total_pairs_per_group',36)
    return st

def load_state(path,inp):
    if os.path.exists(path):
        st=load_json(path)
        if st.get('current_week',0)>0 and st.get('remaining'): return st
    return init_state(inp)

def update_state(state,model,wn,path):
    for e in model.events:
        key=e.get('state_key')
        if key and key in state['remaining']:
            state['remaining'][key]=max(0,state['remaining'][key]-1)
    state['current_week']=wn
    state['generated_at']=datetime.now().isoformat()
    state['history'].append({'week':wn,'events':len(model.events)})
    save_json(state,path)


# ═══════════════════════════════════════════════════════════
#  OUTPUT
# ═══════════════════════════════════════════════════════════

KI={'lecture':'ЛЕК','seminar':'СЕМ','comp':'КОМП'}

def export_json(model,solver,wn,path):
    m=model
    result={'week':wn,'generated_at':datetime.now().isoformat(),'events':[],'schedule':{}}
    for e in m.events:
        if solver.asgn[e['id']] is None: continue
        ts,r=solver.asgn[e['id']]
        result['events'].append({'eid':e['id'],'ts':ts,'r':r,'subject_id':e['subject_id'],
            'subject':e['subject'],'kind':e['kind'],'teacher':e['teacher'],
            'groups':e['groups'],'room':m.room_ids[r]})
    for d in range(m.ND):
        dd={}
        for s in range(m.NS):
            items=[ev for ev in result['events'] if ev['ts']//m.NS==d and ev['ts']%m.NS==s]
            if items:
                dd[f"pair_{s+1}"]={'time':m.slot_times.get(str(s+1),''),
                    'classes':[{k:v for k,v in it.items() if k not in ('eid','ts','r')} for it in items]}
        if dd: result['schedule'][m.DAYS[d]]=dd
    save_json(result,path)

def verify(model,solver):
    m=model; ok=True; issues=[]
    for t,eids in m.teacher_evts.items():
        tsm=defaultdict(list)
        for eid in eids:
            if solver.asgn[eid] is None: continue
            tsm[solver.asgn[eid][0]].append(eid)
        for ts,lst in tsm.items():
            if len(lst)>1:
                d,s=ts//m.NS,ts%m.NS
                issues.append(f"Препод {t}: {m.DAYS[d]} п.{s+1}"); ok=False
    for g,eids in m.group_evts.items():
        tsm=defaultdict(list)
        for eid in eids:
            if solver.asgn[eid] is None: continue
            tsm[solver.asgn[eid][0]].append(eid)
        for ts,lst in tsm.items():
            # Filter linked
            real=lst
            if len(real)>1:
                linked_pairs=set()
                for a,b in m.links: linked_pairs.add((min(a,b),max(a,b)))
                is_all_linked=all(
                    any((min(real[i],real[j]),max(real[i],real[j])) in linked_pairs
                        for j in range(len(real)) if i!=j)
                    for i in range(len(real)))
                if not is_all_linked:
                    d,s=ts//m.NS,ts%m.NS
                    names=[m.events[e]['subject'] for e in real]
                    issues.append(f"Группа {g}: {m.DAYS[d]} п.{s+1} → {names[:3]}"); ok=False
    rts=defaultdict(list)
    for e in m.events:
        if solver.asgn[e['id']] is None: continue
        ts,r=solver.asgn[e['id']]; rts[(ts,r)].append(e['subject'])
    for (ts,r),lst in rts.items():
        if len(lst)>1:
            d,s=ts//m.NS,ts%m.NS
            issues.append(f"Ауд.{m.room_ids[r]}: {m.DAYS[d]} п.{s+1}"); ok=False
    
    # Count gaps and single-pair days
    all_groups=sorted(set(g for e in m.events for g in e['groups']))
    gaps=0; singles=0
    for g in all_groups:
        for d in range(m.ND):
            occ=sorted(set(solver.asgn[eid][0]%m.NS for eid in m.group_evts.get(g,[])
                           if solver.asgn[eid] is not None and solver.asgn[eid][0]//m.NS==d))
            if len(occ)==1: singles+=1
            for i in range(1,len(occ)):
                if occ[i]-occ[i-1]>1: gaps+=occ[i]-occ[i-1]-1
    
    if issues:
        print(f"  ❌ {len(issues)} конфликтов:")
        for iss in issues[:10]: print(f"    - {iss}")
    else:
        print(f"  ✅ Конфликтов нет")
    if gaps: print(f"  ⚠️  {gaps} окон")
    if singles: print(f"  ⚠️  {singles} дней с 1 парой")
    return ok


def print_summary(model,solver,wn):
    m=model
    ag=sorted(set(g for e in m.events for g in e['groups']))
    print(f"\n  По группам:")
    for g in ag:
        dc=defaultdict(int)
        for eid in m.group_evts.get(g,[]):
            if solver.asgn[eid] is None: continue
            dc[solver.asgn[eid][0]//m.NS]+=1
        cnt=sum(dc.values()); mx=max(dc.values()) if dc else 0
        ds='  '.join(f"{m.DAYS[d]}:{c}" for d,c in sorted(dc.items()))
        print(f"    {g:<8}: {cnt:>2} пар, макс/день: {mx}  [{ds}]")


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

def main():
    import argparse
    pa=argparse.ArgumentParser()
    pa.add_argument('--input',default='real_input.json')
    pa.add_argument('--state',default='real_state.json')
    pa.add_argument('--output',default='real_output.json')
    pa.add_argument('--week',type=int,default=None)
    pa.add_argument('--weeks',type=int,default=1)
    pa.add_argument('--reset',action='store_true')
    args=pa.parse_args()

    inp=load_json(args.input)
    if args.reset and os.path.exists(args.state):
        os.remove(args.state)
    state=load_state(args.state,inp)
    
    start=args.week or (state['current_week']+1)
    sw=inp['settings'].get('semester_weeks',18)

    for w in range(args.weeks):
        wn=start+w
        if wn>sw: break
        print(f"\n{'▓'*80}\n  НЕДЕЛЯ {wn}\n{'▓'*80}")
        model=Model(inp,state,wn)
        if not model.events: print("  ⏹  Нет событий"); break
        
        solver=GreedySolver(model)
        solver.solve()
        verify(model,solver)
        print_summary(model,solver,wn)
        update_state(state,model,wn,args.state)
        
        out=args.output.replace('.json',f'_w{wn}.json')
        export_json(model,solver,wn,out)
        print(f"  📄 → {out}")

    print(f"\n  🏁 Готово!\n")

if __name__=='__main__': main()