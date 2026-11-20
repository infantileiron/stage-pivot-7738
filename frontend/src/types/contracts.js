/** @typedef {{id:number,code:string,day:string,venue:string,play:string,channel:string,gross_cents:number,refund_cents:number,fee_cents:number,seats:number,checked:number,currency:string}} Settlement */
/** @typedef {{id:number,name:string,row_dim:string,col_dim:string,state:string,basis:string,result:object}} Pivot */
/** @typedef {{id:number,pivot_id:number,row_key:string,col_key:string,book_cents:number,expected_cents:number,difference_cents:number,status:string,note:string}} Review */
/** @typedef {{id:number,currency:string,day:string,rate_micros:number,created:string}} FxRate */
/** @typedef {{id:number,settlement_id:number,code:string,day:string,currency:string,foreign_cents:number,book_cents:number,rate_micros:number,rate_day:string,written_off_foreign_cents:number,written_off_book_cents:number,balance_book_cents:number,realized_cents:number,unrealized_cents:number,status:string,remaining_foreign_cents:number,reconciled:boolean}} Receivable */
/** @typedef {{id:number,receivable_id:number,day:string,foreign_cents:number,cny_cents:number,book_cents:number,realized_cents:number,code:string,currency:string}} Receipt */
/** @typedef {{id:number,day:string,state:string,base_version:number,result:object,error:string,created:string}} Valuation */
