from sqlalchemy import text
from src.config.database import Base,engine,Session
from src.models import entities
from src.models.entities import Settlement,Receivable,FxMeta
from src.services.fx import book
ADDS={'settlements':[('currency',"VARCHAR(3) NOT NULL DEFAULT 'CNY'")],'pivots':[('basis',"VARCHAR(10) NOT NULL DEFAULT 'local'")]}
def has_column(c,table,col):
 if c.dialect.name=='sqlite':return col in [r[1] for r in c.execute(text(f'PRAGMA table_info({table})'))]
 return c.execute(text('SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=:t AND column_name=:c'),{'t':table,'c':col}).scalar()>0
def migrate():
 Base.metadata.create_all(engine)
 with engine.begin() as c:
  for table,cols in ADDS.items():
   for col,ddl in cols:
    if not has_column(c,table,col):c.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {ddl}'))
 with Session() as s:
  if not s.get(FxMeta,1):s.add(FxMeta(id=1,version=1))
  have={r.settlement_id for r in s.query(Receivable).all()}
  n=0
  for st in s.query(Settlement).all():
   if st.id in have:continue
   if not st.currency:st.currency='CNY'
   r=Receivable(settlement_id=st.id,code=st.code,day=st.day,currency=st.currency,foreign_cents=st.gross_cents-st.refund_cents-st.fee_cents,written_off_foreign_cents=0,written_off_book_cents=0,realized_cents=0,unrealized_cents=0,status='pending')
   s.add(r);s.flush();book(s,r);n+=1
  s.commit()
  return n
