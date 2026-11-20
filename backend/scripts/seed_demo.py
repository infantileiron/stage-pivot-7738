import random
from datetime import date,timedelta
from src.config.database import Base,engine,Session
from src.models.entities import User,Settlement,FxRate,Receivable,Receipt
from src.utils.security import hash_password
from src.constants.enums import VENUES,CHANNELS
from src.services.fx import sync,conv
RATES=[('USD','2026-08-30','7.1025'),('USD','2026-09-15','7.1580'),('USD','2026-10-20','7.1210'),('EUR','2026-09-01','7.8800'),('EUR','2026-10-08','7.9400'),('HKD','2026-09-05','0.9120')]
OVERSEAS=[('YM-181','2026-09-20','云幕大剧场','星河漫游','票务合作',5000000,100000,200000,800,700,'USD'),('YM-182','2026-10-25','云幕大剧场','星河漫游','票务合作',4200000,0,150000,800,640,'USD'),('YM-183','2026-09-10','河畔小剧场','渡口来信','票务合作',1800000,50000,90000,240,200,'EUR'),('YM-184','2026-10-10','河畔小剧场','冬日序曲','票务合作',1600000,0,80000,240,180,'EUR'),('YM-185','2026-09-08','星光排练厅','一间书房','团体专场',900000,0,0,120,110,'HKD'),('YM-186','2026-11-01','云幕大剧场','冬日序曲','票务合作',6600000,0,300000,800,600,'JPY')]
RECEIPTS=[('YM-181','2026-09-25',2000000,14500000),('YM-181','2026-10-02',1000000,7200000)]
def micros(text):
 from decimal import Decimal
 return int(Decimal(text)*1000000)
def seed():
 Base.metadata.create_all(engine);rng=random.Random(3112)
 with Session() as s:
  for role in ('admin','analyst','viewer'):
   email=role+'@demo.local'
   if not s.query(User).filter_by(email=email).first():s.add(User(email=email,role=role,password=hash_password('Demo123!')))
  for i in range(180):
   code=f'YM-{i+1:03}';seats=[800,240,120][i%3];checked=rng.randint(seats//2,seats);gross=checked*rng.choice([8000,12000,18000]);refund=rng.randint(0,checked//10)*8000;fee=int((gross-refund)*[0,.07,.03][i%3])
   if not s.query(Settlement).filter_by(code=code).first():s.add(Settlement(code=code,day=(date(2026,9,1)+timedelta(days=i//3)).isoformat(),venue=VENUES[i%3],play=['渡口来信','星河漫游','一间书房','冬日序曲'][i%4],channel=CHANNELS[(i//3)%3],gross_cents=gross,refund_cents=refund,fee_cents=fee,seats=seats,checked=checked,currency='CNY'))
  s.commit()
  for cur,day,rate in RATES:
   if not s.query(FxRate).filter_by(currency=cur,day=day).first():s.add(FxRate(currency=cur,day=day,rate_micros=micros(rate),created=date(2026,11,15).isoformat()+'T00:00:00+00:00'))
  s.commit()
  for code,day,venue,play,channel,gross,refund,fee,seats,checked,cur in OVERSEAS:
   st=s.query(Settlement).filter_by(code=code).first()
   if not st:st=Settlement(code=code,day=day,venue=venue,play=play,channel=channel,gross_cents=gross,refund_cents=refund,fee_cents=fee,seats=seats,checked=checked,currency=cur);s.add(st);s.flush()
  s.commit()
  have={r.settlement_id for r in s.query(Receivable).all()}
  for st in s.query(Settlement).all():
   if st.id not in have:sync(s,st)
  s.commit()
  for code,day,foreign,cny in RECEIPTS:
   st=s.query(Settlement).filter_by(code=code).first();r=s.query(Receivable).filter_by(settlement_id=st.id).first()
   if not r or r.status!='open' or s.query(Receipt).filter_by(receivable_id=r.id,day=day,foreign_cents=foreign).count():continue
   w=conv(foreign,r.rate_micros)
   s.add(Receipt(receivable_id=r.id,day=day,foreign_cents=foreign,cny_cents=cny,book_cents=w,realized_cents=cny-w,created=date(2026,11,15).isoformat()+'T00:00:00+00:00'))
   r.written_off_foreign_cents+=foreign;r.written_off_book_cents+=w;r.balance_book_cents-=w;r.realized_cents=(r.realized_cents or 0)+cny-w
   if r.written_off_foreign_cents>=r.foreign_cents:r.status='settled';r.balance_book_cents=0
  s.commit();print({'users':s.query(User).count(),'settlements':s.query(Settlement).count(),'rates':s.query(FxRate).count(),'receivables':s.query(Receivable).count()})
if __name__=='__main__':seed()
