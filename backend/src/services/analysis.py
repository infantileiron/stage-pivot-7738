import json,hashlib
DIMENSIONS={'venue','play','channel','month'}
SUMS=('gross_cents','refund_cents','fee_cents','seats','checked')
def key(row,dim):return row['day'][:7] if dim=='month' else row[dim]
def conv(x,rate):return (x*rate+500000)//1000000
def book_of(r):
 b=r.get('book_cents')
 if b is None and r.get('currency','CNY')=='CNY':b=r['gross_cents']-r['refund_cents']-r['fee_cents']
 return b
def rate_of(r):
 q=r.get('rate_micros')
 if q is None and r.get('currency','CNY')=='CNY':q=1000000
 return q
def checksum(rows):return hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
def aggregate_local(rows):
 out={k:sum(r[k] for r in rows) for k in ('seats','checked')};out['count']=len(rows)
 booked=[r for r in rows if r['_book'] is not None]
 out['pending_count']=len(rows)-len(booked)
 out['gross_cents']=sum(r['_g'] for r in booked);out['refund_cents']=sum(r['_r'] for r in booked);out['fee_cents']=sum(r['_f'] for r in booked)
 out['net_cents']=sum(r['_book'] for r in booked)
 out['occupancy']=out['checked']/out['seats'] if out['seats'] else None
 return out
def aggregate_original(rows):
 out={k:sum(r[k] for r in rows) for k in ('seats','checked')};out['count']=len(rows)
 by={}
 for r in rows:
  cur=r.get('currency','CNY');by[cur]=by.get(cur,0)+r['gross_cents']-r['refund_cents']-r['fee_cents']
 out['by_currency']=by;out['net_cents']=None;out['pending_count']=0
 out['occupancy']=out['checked']/out['seats'] if out['seats'] else None
 return out
def check(rows,row_dim,col_dim):
 if row_dim not in DIMENSIONS or col_dim not in DIMENSIONS or row_dim==col_dim:raise ValueError('请选择两个不同的白名单维度')
 if not rows:raise ValueError('没有结算记录，请先录入场次')
 if len({r['code'] for r in rows})!=len(rows):raise ValueError('场次编号重复，无法保证结算守恒')
def build(rows,row_dim,col_dim,agg):
 row_keys=sorted({key(r,row_dim) for r in rows});col_keys=sorted({key(r,col_dim) for r in rows})
 cells=[{'row_key':a,'col_key':b,**agg([r for r in rows if key(r,row_dim)==a and key(r,col_dim)==b])} for a in row_keys for b in col_keys]
 row_totals=[{'key':a,**agg([r for r in rows if key(r,row_dim)==a])} for a in row_keys]
 col_totals=[{'key':b,**agg([r for r in rows if key(r,col_dim)==b])} for b in col_keys]
 return dict(row_keys=row_keys,col_keys=col_keys,cells=cells,row_totals=row_totals,col_totals=col_totals,total=agg(rows))
def rollup_conserved(out,keys):
 return all(sum(x[k] for x in out['cells'])==sum(x[k] for x in out['row_totals'])==sum(x[k] for x in out['col_totals'])==out['total'][k] for k in keys)
def pivot(rows,row_dim,col_dim,basis='local'):
 check(rows,row_dim,col_dim)
 if basis=='original':
  out=build(rows,row_dim,col_dim,aggregate_original)
  currencies=sorted({r.get('currency','CNY') for r in rows})
  conserved=rollup_conserved(out,('seats','checked','count'))
  for cur in currencies:
   for part in ('cells','row_totals','col_totals'):
    if sum(x['by_currency'].get(cur,0) for x in out[part])!=out['total']['by_currency'].get(cur,0):conserved=False
  if not conserved:raise ValueError('行列总计不守恒，请核对输入')
  out.update(conserved=True,basis='original',currencies=currencies,checksum=checksum(rows))
  out['method']='原币透视按币种分列，不跨币种相加：各单元为净结算原币=票款−退款−渠道费，按场次币种分组求和，各币种行列总计分别守恒。金额以整数分求和；上座率=总核验人数/总座位，零座位显示未定义。人民币折算与汇兑损益请用本币透视；下钻始终读取冻结快照。'
  return out
 erows=[]
 for r in rows:
  q=rate_of(r)
  erows.append({**r,'_book':book_of(r),'_g':conv(r['gross_cents'],q) if q else None,'_r':conv(r['refund_cents'],q) if q else None,'_f':conv(r['fee_cents'],q) if q else None})
 out=build(erows,row_dim,col_dim,aggregate_local)
 if not rollup_conserved(out,('gross_cents','refund_cents','fee_cents','seats','checked','net_cents','count','pending_count')):raise ValueError('行列总计不守恒，请核对输入')
 out.update(conserved=True,basis='local',checksum=checksum(rows))
 out['method']='本币透视以人民币汇总：净结算=应收台账账面额（按场次日最近前值汇率折算），票款/退款/渠道费分项按同一汇率折算，尾差不摊派，分项轧差与账面净额可能相差分币。缺率暂挂场次不计入金额，以pending_count列示。金额以整数分求和；上座率=总核验人数/总座位，零座位显示未定义。下钻始终读取冻结快照。'
 return out
