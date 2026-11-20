import os,json
import redis
from fastapi import APIRouter,Depends,HTTPException,Response
from src.config.database import db
from src.models.entities import User,Settlement,Pivot,Review,Audit,FxRate,Receivable,Receipt,Valuation
from src.schemas.business import Login,SettlementInput,PivotInput,ReviewInput,ReviewEdit,RateInput,RateEdit,ReceiptInput,ValuationInput
from src.middlewares.auth import current,editor,admin
from src.utils.security import verify,token
from src.services.business import audit,dump
from src.services.settlements import save
from src.services.analysis import key
from src.services.fx import add_rate,edit_rate,receive,dump_receivable,meta
from src.services.fx import now as fxnow
from src.controllers.business import ensure_pivot,ensure_review,cell,reviewable
router=APIRouter()
@router.post('/auth/login')
def login(data:Login,s=Depends(db)):
 u=s.query(User).filter_by(email=data.email).first()
 if not u or not verify(data.password,u.password):raise HTTPException(401,'账号或密码错误')
 return {'token':token(u),'user':dump(u)}
@router.get('/me')
def me(u=Depends(current)):return dump(u)
@router.get('/settlements')
def settlements(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Settlement).order_by(Settlement.id).all()]
@router.post('/settlements')
def create(data:SettlementInput,u=Depends(editor),s=Depends(db)):
 r=save(s,data);audit(s,u,'录入结算 '+r['code']);return r
@router.put('/settlements/{i}')
def edit(i:int,data:SettlementInput,u=Depends(editor),s=Depends(db)):
 r=save(s,data,i);audit(s,u,'修订结算 '+str(i));return r
@router.get('/pivots')
def pivots(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Pivot).order_by(Pivot.id.desc()).all()]
@router.post('/pivots')
def submit(data:PivotInput,u=Depends(editor),s=Depends(db)):
 recs={r.settlement_id:r for r in s.query(Receivable).all()}
 rows=[]
 for st in s.query(Settlement).order_by(Settlement.id).all():
  d=dump(st);r=recs.get(st.id)
  d['book_cents']=r.book_cents if r else None;d['rate_micros']=r.rate_micros if r else None
  rows.append(d)
 r=Pivot(**data.model_dump(),result={'snapshot':rows});s.add(r);s.commit()
 try:redis.Redis.from_url(os.environ['REDIS_URL']).rpush('stage:pivots',r.id)
 except redis.RedisError:r.state='failed';r.error='队列暂不可用，请恢复后新建透视';s.commit();raise HTTPException(503,r.error)
 audit(s,u,'提交透视 '+str(r.id));return dump(r)
@router.get('/pivots/{i}')
def detail(i:int,u=Depends(current),s=Depends(db)):return dump(ensure_pivot(s,i))
@router.get('/pivots/{i}/drill')
def drill(i:int,row_key:str,col_key:str,u=Depends(current),s=Depends(db)):
 r,c=cell(s,i,row_key,col_key)
 return {'cell':c,'rows':[x for x in r.result['snapshot'] if key(x,r.row_dim)==row_key and key(x,r.col_dim)==col_key]}
@router.get('/pivots/{i}/export')
def export(i:int,u=Depends(current),s=Depends(db)):
 r=ensure_pivot(s,i)
 if r.state!='done':raise HTTPException(409,'仅成功透视可以导出')
 return Response(json.dumps(dump(r),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="stage-pivot-{i}.json"'})
@router.get('/reviews')
def reviews(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Review).order_by(Review.id.desc()).all()]
@router.post('/reviews')
def review(data:ReviewInput,u=Depends(editor),s=Depends(db)):
 run,c=reviewable(s,data.pivot_id,data.row_key,data.col_key)
 r=Review(**data.model_dump(),book_cents=c['net_cents'],difference_cents=data.expected_cents-c['net_cents']);s.add(r);s.commit();audit(s,u,'起草差异复核 '+str(r.id));return dump(r)
@router.put('/reviews/{i}')
def edit_review(i:int,data:ReviewEdit,u=Depends(editor),s=Depends(db)):
 r=ensure_review(s,i)
 if r.status!='draft':raise HTTPException(409,'已签核复核单不可覆盖，请新建复核')
 r.expected_cents=data.expected_cents;r.difference_cents=data.expected_cents-r.book_cents;r.note=data.note;s.commit();audit(s,u,'修改差异复核 '+str(i));return dump(r)
@router.post('/reviews/{i}/approve')
def approve(i:int,u=Depends(admin),s=Depends(db)):
 r=ensure_review(s,i)
 if r.status!='draft':raise HTTPException(409,'已签核复核单不可重复签核')
 r.status='approved';s.commit();audit(s,u,'签核差异复核 '+str(i));return dump(r)
@router.get('/audits')
def audits(u=Depends(admin),s=Depends(db)):return [dump(r) for r in s.query(Audit).order_by(Audit.id.desc()).limit(100)]
@router.get('/fx/rates')
def rates(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(FxRate).order_by(FxRate.currency,FxRate.day,FxRate.id).all()]
@router.post('/fx/rates')
def rate_add(data:RateInput,u=Depends(editor),s=Depends(db)):
 r=add_rate(s,data);audit(s,u,'登记汇率 '+data.currency+' '+data.day.isoformat());return r
@router.put('/fx/rates/{i}')
def rate_edit(i:int,data:RateEdit,u=Depends(editor),s=Depends(db)):
 r=edit_rate(s,i,data);audit(s,u,'更正汇率 '+str(i));return r
@router.get('/fx/receivables')
def receivables(u=Depends(current),s=Depends(db)):return [dump_receivable(s,r) for r in s.query(Receivable).order_by(Receivable.id).all()]
@router.get('/fx/receipts')
def receipts(u=Depends(current),s=Depends(db)):
 out=[]
 for r in s.query(Receipt).order_by(Receipt.id).all():
  d=dump(r);rv=s.get(Receivable,r.receivable_id);d['code']=rv.code if rv else '';d['currency']=rv.currency if rv else '';out.append(d)
 return out
@router.post('/fx/receipts')
def receipt_add(data:ReceiptInput,u=Depends(editor),s=Depends(db)):
 r=receive(s,data);audit(s,u,'登记到账 应收'+str(data.receivable_id));return r
@router.get('/fx/valuations')
def valuations(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Valuation).order_by(Valuation.id.desc()).all()]
@router.post('/fx/valuations')
def valuation_add(data:ValuationInput,u=Depends(editor),s=Depends(db)):
 t=Valuation(day=data.day.isoformat(),state='queued',base_version=meta(s).version,created=fxnow(),error='');s.add(t);s.commit()
 try:redis.Redis.from_url(os.environ['REDIS_URL']).rpush('stage:valuations',t.id)
 except redis.RedisError:t.state='failed';t.error='队列暂不可用，请恢复后重新提交估值';s.commit();raise HTTPException(503,t.error)
 audit(s,u,'提交估值 '+str(t.id));return dump(t)
@router.get('/fx/valuations/{i}')
def valuation_detail(i:int,u=Depends(current),s=Depends(db)):
 t=s.get(Valuation,i)
 if not t:raise HTTPException(404,'估值任务不存在')
 return dump(t)
@router.get('/fx/valuations/{i}/export')
def valuation_export(i:int,u=Depends(current),s=Depends(db)):
 t=s.get(Valuation,i)
 if not t:raise HTTPException(404,'估值任务不存在')
 if t.state!='done':raise HTTPException(409,'仅已生效估值可以下载依据')
 return Response(json.dumps(dump(t),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="fx-valuation-{i}.json"'})
