from sqlalchemy import Column,Integer,BigInteger,String,JSON,Text,ForeignKey,UniqueConstraint
from src.config.database import Base
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True);email=Column(String(100),unique=True,nullable=False);password=Column(String(200));role=Column(String(20))
class Settlement(Base):
 __tablename__='settlements'
 id=Column(Integer,primary_key=True);code=Column(String(60),unique=True,nullable=False);day=Column(String(10));venue=Column(String(40));play=Column(String(60));channel=Column(String(30));gross_cents=Column(BigInteger);refund_cents=Column(BigInteger);fee_cents=Column(BigInteger);seats=Column(Integer);checked=Column(Integer);currency=Column(String(3),default='CNY',nullable=False)
class Pivot(Base):
 __tablename__='pivots'
 id=Column(Integer,primary_key=True);name=Column(String(100));row_dim=Column(String(30));col_dim=Column(String(30));state=Column(String(20),default='queued');basis=Column(String(10),default='local',nullable=False);result=Column(JSON,nullable=True);error=Column(Text,default='')
class Review(Base):
 __tablename__='reviews'
 id=Column(Integer,primary_key=True);pivot_id=Column(Integer,ForeignKey('pivots.id'));row_key=Column(String(100));col_key=Column(String(100));book_cents=Column(BigInteger);expected_cents=Column(BigInteger);difference_cents=Column(BigInteger);note=Column(Text);status=Column(String(20),default='draft')
class Audit(Base):
 __tablename__='audits'
 id=Column(Integer,primary_key=True);actor=Column(String(100));action=Column(String(200));created=Column(String(40))
class FxRate(Base):
 __tablename__='fx_rates'
 __table_args__=(UniqueConstraint('currency','day'),)
 id=Column(Integer,primary_key=True);currency=Column(String(3),nullable=False);day=Column(String(10),nullable=False);rate_micros=Column(BigInteger,nullable=False);created=Column(String(40))
class Receivable(Base):
 __tablename__='receivables'
 id=Column(Integer,primary_key=True);settlement_id=Column(Integer,ForeignKey('settlements.id'),unique=True,nullable=False);code=Column(String(60));day=Column(String(10));currency=Column(String(3),nullable=False);foreign_cents=Column(BigInteger);book_cents=Column(BigInteger,nullable=True);rate_micros=Column(BigInteger,nullable=True);rate_day=Column(String(10),nullable=True);written_off_foreign_cents=Column(BigInteger,default=0);written_off_book_cents=Column(BigInteger,default=0);balance_book_cents=Column(BigInteger,nullable=True);realized_cents=Column(BigInteger,default=0);unrealized_cents=Column(BigInteger,default=0);status=Column(String(10),default='pending')
class Receipt(Base):
 __tablename__='receipts'
 id=Column(Integer,primary_key=True);receivable_id=Column(Integer,ForeignKey('receivables.id'),nullable=False);day=Column(String(10));foreign_cents=Column(BigInteger);cny_cents=Column(BigInteger);book_cents=Column(BigInteger);realized_cents=Column(BigInteger);created=Column(String(40))
class Valuation(Base):
 __tablename__='valuations'
 id=Column(Integer,primary_key=True);day=Column(String(10),nullable=False);state=Column(String(10),default='queued');base_version=Column(BigInteger,default=0);result=Column(JSON,nullable=True);error=Column(Text,default='');created=Column(String(40))
class ValuationLine(Base):
 __tablename__='valuation_lines'
 __table_args__=(UniqueConstraint('valuation_id','receivable_id'),)
 id=Column(Integer,primary_key=True);valuation_id=Column(Integer,ForeignKey('valuations.id'),nullable=False);receivable_id=Column(Integer,ForeignKey('receivables.id'),nullable=False);currency=Column(String(3));foreign_cents=Column(BigInteger);rate_micros=Column(BigInteger,nullable=True);rate_day=Column(String(10),nullable=True);old_book_cents=Column(BigInteger,nullable=True);new_book_cents=Column(BigInteger,nullable=True);unrealized_cents=Column(BigInteger,nullable=True)
class FxMeta(Base):
 __tablename__='fx_meta'
 id=Column(Integer,primary_key=True);version=Column(BigInteger,default=0)
