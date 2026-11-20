export const DIMENSIONS=[['venue','场馆'],['play','演出'],['channel','渠道'],['month','月份']];export const VENUES=['云幕大剧场','河畔小剧场','星光排练厅'];export const CHANNELS=['剧院直营','票务合作','团体专场'];export const ROLES=['admin','analyst','viewer'];export const STATES=['queued','running','done','failed'];
export const CURRENCIES=[['CNY','人民币 CNY'],['USD','美元 USD'],['EUR','欧元 EUR'],['HKD','港币 HKD'],['JPY','日元 JPY'],['GBP','英镑 GBP'],['SGD','新元 SGD'],['AUD','澳元 AUD']];export const FX_CURRENCIES=CURRENCIES.filter(([c])=>c!=='CNY');
export const BASES=[['local','本币（人民币）'],['original','原币（分币种）']];
export const RECEIVABLE_STATES={pending:'缺率暂挂',open:'在途',settled:'已结清'};
export const VALUATION_STATES={queued:'排队中',running:'运算中',done:'已生效',failed:'失败',stale:'已失效'};
