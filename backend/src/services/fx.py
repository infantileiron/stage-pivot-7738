import os,json,logging
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from src.config.database import Session
from src.models.entities import FxRate,Receivable,Receipt,Valuation,ValuationLine,FxMeta,Settlement
from src.services.business import dump
ARTIFACTS=os.getenv('ARTIFACTS_DIR','/artifacts')
CNY_MICROS=1000000
METHOD='应收按场次日最近前值汇率折算入账；到账分次核销，核销账面=到账原币×入账汇率（最后一笔核销剩余全部账面，尾差留在余款）；已实现汇兑损益=实兑人民币−核销账面；估值按估值日最近前值汇率重估余款，未实现损益=重估后余款−重估前余款；原账面额=已核销账面额+余款账面额（重估后差额为累计未实现损益）；汇率更正或新到账使未完成估值失效，已核销账面额不变；余款与损益在同一事务原子替换。'
def now():return datetime.now(timezone.utc).isoformat()
def micros(rate):return int((rate*1000000).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def conv(foreign_cents,rate_micros):return (foreign_cents*rate_micros+500000)//1000000
def rate_for(s,currency,day):
 return s.query(FxRate).filter(FxRate.currency==currency,FxRate.day<=day).order_by(FxRate.day.desc(),FxRate.id.desc()).first()
def meta(s):
 m=s.get(FxMeta,1)
 if not m:m=FxMeta(id=1,version=0);s.add(m);s.flush()
 return m
def bump(s):
 meta(s).version+=1;s.flush()
 s.query(Valuation).filter(Valuation.state.in_(['queued','running'])).update({'state':'stale'},synchronize_session=False)
def book(s,r):
 if r.currency=='CNY':r.rate_micros=CNY_MICROS;r.rate_day=r.day
 else:
  q=rate_for(s,r.currency,r.day)
  if not q:
   r.book_cents=None;r.rate_micros=None;r.rate_day=None;r.balance_book_cents=None;r.status='pending';s.flush();return
  r.rate_micros=q.rate_micros;r.rate_day=q.day
 r.book_cents=conv(r.foreign_cents,r.rate_micros)
 r.balance_book_cents=r.book_cents-r.written_off_book_cents
 r.status='settled' if r.written_off_foreign_cents>=r.foreign_cents else 'open'
 s.flush()
def rebook(s,currency):
 for r in s.query(Receivable).filter_by(status='pending',currency=currency).all():book(s,r)
def sync(s,st):
 net=st.gross_cents-st.refund_cents-st.fee_cents
 r=s.query(Receivable).filter_by(settlement_id=st.id).first()
 if not r:
  r=Receivable(settlement_id=st.id,written_off_foreign_cents=0,written_off_book_cents=0,realized_cents=0,unrealized_cents=0,status='pending');s.add(r)
 if r.written_off_foreign_cents:
  if r.currency!=st.currency or r.foreign_cents!=net or r.day!=st.day:raise HTTPException(409,'该场次已发生到账核销，不能修订币种、金额或日期')
  return r
 r.code=st.code;r.day=st.day.isoformat() if hasattr(st.day,'isoformat') else st.day;r.currency=st.currency;r.foreign_cents=net
 book(s,r)
 return r
def dump_receivable(s,r):
 d=dump(r);st=s.get(Settlement,r.settlement_id)
 d['code']=st.code if st else r.code;d['venue']=st.venue if st else ''
 d['remaining_foreign_cents']=(r.foreign_cents or 0)-(r.written_off_foreign_cents or 0)
 d['reconciled']=None if r.book_cents is None else r.book_cents+(r.unrealized_cents or 0)==(r.written_off_book_cents or 0)+(r.balance_book_cents or 0)
 return d
def add_rate(s,data):
 r=FxRate(currency=data.currency,day=data.day.isoformat(),rate_micros=micros(data.rate),created=now());s.add(r)
 try:s.flush()
 except IntegrityError:s.rollback();raise HTTPException(409,'该币种该生效日已有汇率，请用更正')
 bump(s);rebook(s,data.currency);s.commit();return dump(r)
def edit_rate(s,i,data):
 r=s.get(FxRate,i)
 if not r:raise HTTPException(404,'汇率记录不存在')
 r.rate_micros=micros(data.rate)
 if data.day:r.day=data.day.isoformat()
 try:s.flush()
 except IntegrityError:s.rollback();raise HTTPException(409,'该币种该生效日已有汇率')
 bump(s);rebook(s,r.currency);s.commit();return dump(r)
def receive(s,data):
 r=s.get(Receivable,data.receivable_id)
 if not r:raise HTTPException(404,'应收记录不存在')
 if r.status=='pending':raise HTTPException(409,'该应收缺率暂挂，补登汇率后再核销')
 if r.status=='settled':raise HTTPException(409,'该应收已结清，不能再到账')
 remaining=r.foreign_cents-r.written_off_foreign_cents
 if data.foreign_cents>remaining:raise HTTPException(422,'到账原币超过应收余款，应收不超额')
 bump(s)
 w=r.balance_book_cents if data.foreign_cents==remaining else conv(data.foreign_cents,r.rate_micros)
 realized=data.cny_cents-w
 rc=Receipt(receivable_id=r.id,day=data.day.isoformat(),foreign_cents=data.foreign_cents,cny_cents=data.cny_cents,book_cents=w,realized_cents=realized,created=now());s.add(rc)
 r.written_off_foreign_cents+=data.foreign_cents;r.written_off_book_cents+=w;r.balance_book_cents-=w;r.realized_cents=(r.realized_cents or 0)+realized
 if r.written_off_foreign_cents>=r.foreign_cents:r.status='settled';r.balance_book_cents=0
 else:r.status='open'
 s.commit();return dump(rc)
def compute_valuation(s,t):
 lines=[]
 for r in s.query(Receivable).filter(Receivable.status=='open',Receivable.currency!='CNY').order_by(Receivable.id).all():
  remaining=r.foreign_cents-r.written_off_foreign_cents
  if remaining<=0:continue
  q=rate_for(s,r.currency,t.day)
  if not q:
   lines.append(dict(receivable_id=r.id,currency=r.currency,foreign_cents=remaining,rate_micros=None,rate_day=None,old_book_cents=r.balance_book_cents,new_book_cents=None,unrealized_cents=None,note='缺估值日汇率，暂挂不重估'))
   continue
  lines.append(dict(receivable_id=r.id,currency=r.currency,foreign_cents=remaining,rate_micros=q.rate_micros,rate_day=q.day,old_book_cents=r.balance_book_cents,new_book_cents=conv(remaining,q.rate_micros),unrealized_cents=None,note=''))
 return lines
def run_valuation(tid):
 with Session() as s:
  t=s.get(Valuation,tid)
  if not t or t.state!='queued':return
  t.state='running';s.commit()
  try:
   lines=compute_valuation(s,t)
   m=s.query(FxMeta).filter_by(id=1).with_for_update().populate_existing().first()
   t=s.query(Valuation).filter_by(id=tid).with_for_update().populate_existing().first()
   if not t or t.state!='running':s.rollback();return
   if not m or m.version!=t.base_version:
    t.state='stale';t.error='估值期间发生到账或汇率变动，结果已失效';s.commit();return
   m.version+=1
   s.query(Valuation).filter(Valuation.state.in_(['queued','running']),Valuation.id!=tid).update({'state':'stale'},synchronize_session=False)
   n=0;tot=0
   for ln in lines:
    if ln['new_book_cents'] is None:continue
    r=s.get(Receivable,ln['receivable_id'])
    if not r or r.status!='open':continue
    ln['old_book_cents']=r.balance_book_cents;ln['unrealized_cents']=ln['new_book_cents']-r.balance_book_cents
    r.balance_book_cents=ln['new_book_cents'];r.unrealized_cents=(r.unrealized_cents or 0)+ln['unrealized_cents']
    s.add(ValuationLine(valuation_id=tid,**{k:v for k,v in ln.items() if k!='note'}))
    n+=1;tot+=ln['unrealized_cents']
   t.result={'day':t.day,'base_version':t.base_version,'lines':lines,'revalued':n,'unrealized_cents':tot,'applied_at':now(),'method':METHOD}
   t.state='done';s.commit()
   try:Path(ARTIFACTS+'/valuation-'+str(tid)+'.json').write_text(json.dumps(t.result,ensure_ascii=False))
   except OSError:logging.exception('valuation artifact')
  except Exception as e:
   s.rollback();logging.exception('valuation %s',tid)
   t=s.get(Valuation,tid)
   if t and t.state=='running':t.state='failed';t.error=str(e);s.commit()
