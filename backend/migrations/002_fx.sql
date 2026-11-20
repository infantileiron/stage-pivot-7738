
-- 外汇结算：场次原币应收、汇率、到账核销、估值
-- 旧数据按人民币迁移：settlements.currency 默认 CNY，并为存量场次补建人民币应收

ALTER TABLE settlements ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'CNY';

ALTER TABLE pivots ADD COLUMN basis VARCHAR(10) NOT NULL DEFAULT 'local';

CREATE TABLE fx_rates (
	id INTEGER NOT NULL AUTO_INCREMENT,
	currency VARCHAR(3) NOT NULL,
	day VARCHAR(10) NOT NULL,
	rate_micros BIGINT NOT NULL,
	created VARCHAR(40),
	PRIMARY KEY (id),
	UNIQUE (currency, day)
)

;


CREATE TABLE receivables (
	id INTEGER NOT NULL AUTO_INCREMENT,
	settlement_id INTEGER NOT NULL,
	code VARCHAR(60),
	day VARCHAR(10),
	currency VARCHAR(3) NOT NULL,
	foreign_cents BIGINT,
	book_cents BIGINT,
	rate_micros BIGINT,
	rate_day VARCHAR(10),
	written_off_foreign_cents BIGINT,
	written_off_book_cents BIGINT,
	balance_book_cents BIGINT,
	realized_cents BIGINT,
	unrealized_cents BIGINT,
	status VARCHAR(10),
	PRIMARY KEY (id),
	FOREIGN KEY(settlement_id) REFERENCES settlements (id),
	UNIQUE (settlement_id)
)

;


CREATE TABLE receipts (
	id INTEGER NOT NULL AUTO_INCREMENT,
	receivable_id INTEGER NOT NULL,
	day VARCHAR(10),
	foreign_cents BIGINT,
	cny_cents BIGINT,
	book_cents BIGINT,
	realized_cents BIGINT,
	created VARCHAR(40),
	PRIMARY KEY (id),
	FOREIGN KEY(receivable_id) REFERENCES receivables (id)
)

;


CREATE TABLE valuations (
	id INTEGER NOT NULL AUTO_INCREMENT,
	day VARCHAR(10) NOT NULL,
	state VARCHAR(10),
	base_version BIGINT,
	result JSON,
	error TEXT,
	created VARCHAR(40),
	PRIMARY KEY (id)
)

;


CREATE TABLE valuation_lines (
	id INTEGER NOT NULL AUTO_INCREMENT,
	valuation_id INTEGER NOT NULL,
	receivable_id INTEGER NOT NULL,
	currency VARCHAR(3),
	foreign_cents BIGINT,
	rate_micros BIGINT,
	rate_day VARCHAR(10),
	old_book_cents BIGINT,
	new_book_cents BIGINT,
	unrealized_cents BIGINT,
	PRIMARY KEY (id),
	FOREIGN KEY(valuation_id) REFERENCES valuations (id),
	FOREIGN KEY(receivable_id) REFERENCES receivables (id),
	UNIQUE (valuation_id, receivable_id)
)

;


CREATE TABLE fx_meta (
	id INTEGER NOT NULL AUTO_INCREMENT,
	version BIGINT,
	PRIMARY KEY (id)
)

;


INSERT INTO fx_meta (id, version) VALUES (1, 1);

INSERT INTO receivables (settlement_id, code, day, currency, foreign_cents, book_cents, rate_micros, rate_day, written_off_foreign_cents, written_off_book_cents, balance_book_cents, realized_cents, unrealized_cents, status)
SELECT id, code, day, 'CNY', gross_cents-refund_cents-fee_cents, gross_cents-refund_cents-fee_cents, 1000000, day, 0, 0, gross_cents-refund_cents-fee_cents, 0, 0, CASE WHEN gross_cents-refund_cents-fee_cents=0 THEN 'settled' ELSE 'open' END FROM settlements;
