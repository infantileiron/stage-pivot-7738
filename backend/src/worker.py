import os,time,json,logging
from pathlib import Path
import redis
from src.config.database import Session
from src.models.entities import Pivot,Valuation
from src.services.analysis import pivot
from src.services.fx import run_valuation
ARTIFACTS=os.getenv('ARTIFACTS_DIR','/artifacts')
QUEUES=['stage:pivots','stage:valuations']
def recover(s,q):
 for r in s.query(Pivot).filter(Pivot.state.in_(['queued','running'])).all():r.state='queued';q.rpush('stage:pivots',r.id)
 for r in s.query(Valuation).filter(Valuation.state.in_(['queued','running'])).all():r.state='queued';q.rpush('stage:valuations',r.id)
 s.commit()
def handle_pivot(tid):
 with Session() as s:
  r=s.get(Pivot,tid)
  if not r or r.state!='queued':return
  snapshot=r.result['snapshot'];r.state='running';s.commit()
  try:
   r.result={**pivot(snapshot,r.row_dim,r.col_dim,r.basis or 'local'),'snapshot':snapshot};r.state='done';Path(ARTIFACTS+'/'+str(r.id)+'.json').write_text(json.dumps(r.result,ensure_ascii=False))
  except Exception as e:r.state='failed';r.error=str(e)
  s.commit()
def main():
 q=redis.Redis.from_url(os.environ['REDIS_URL'])
 with Session() as s:recover(s,q)
 while True:
  Path('/tmp/heartbeat').touch()
  try:
   item=q.blpop(QUEUES,timeout=3)
   if not item:continue
   name=item[0].decode() if isinstance(item[0],bytes) else item[0]
   if name.endswith('pivots'):handle_pivot(int(item[1]))
   else:run_valuation(int(item[1]))
  except Exception:logging.exception('worker');time.sleep(2)
if __name__=='__main__':main()
