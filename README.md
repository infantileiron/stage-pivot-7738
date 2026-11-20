# 云幕 · 剧院场次结算透视

将场次票款、退款、渠道费汇成可下钻的冻结透视，再由财务记录并签核回单差异。海外票款按原币登记应收、分次核销到账、估值日重估余款，不再把外币当人民币相加。原生HTML/CSS/JavaScript前端，Python真实计算。

## 客户、工作流和模块

云幕剧院有云幕大剧场、河畔小剧场和星光排练厅。财务组当前把 `云幕_场次结算_20261115.xlsx` 中多张表复制到工作簿，再按场馆和渠道求和，最后在邮件里解释回单差异。痛点是座位百分比被简单平均、分币四舍五入不守恒、原始明细改动后难以重现旧结论，且海外票款被当成人民币直接相加。上游是独立场次票款及核验记录；本项目替代布局、计算、追溯及复核；下游是财务负责人核对渠道回单，不触发付款。

五页：结算明细（录入/修订/币种）、透视布局（白名单行列方案+金额口径）、结算透视（守恒总计/冻结下钻/导出）、差异复核（回单预期/原因/签核）、外汇结算（汇率/应收台账/到账核销/估值）。核心实体 Settlement、Pivot、Review、FxRate、Receivable、Receipt、Valuation，另有User/Audit。每条结算记录为独立场次，渠道是主售票渠道；当前不拆分同一场次的多个售票渠道座位。

|角色|权限|动作|
|---|---|---|
|admin|业务读写、签核、审计|签核回单差异|
|analyst|录入修订、提交计算、登记汇率到账估值、起草复核、导出|下钻后核对回单|
|viewer|业务只读和导出；服务器拒绝全部写入|下载冻结透视与估值依据|

## 快速启动

```sh
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
```

前端 [localhost:18211](http://localhost:18211)，后端 [localhost:19211/docs](http://localhost:19211/docs)，MySQL宿主17711。账号 `admin@demo.local`、`analyst@demo.local`、`viewer@demo.local`，密码均 `Demo123!`。`SEED_DEMO=true`启动自动种子；再次执行不新增同编号、不覆盖人工修订。种子包含180场人民币场次、6场海外场次（USD/EUR/HKD/JPY各档汇率）、YM-181两笔分次到账、YM-186缺率暂挂。

## 一天的剧本

1. 08:50 viewer浏览YM-001到YM-186，核对场次日期、主渠道与币种。
2. 09:00 analyst核对`云幕_场次结算_20261115.xlsx`，录入YM-187，2026-11-15，云幕大剧场，票款100000分、退款10000分、渠道费5000分、座位100、核验80，币种人民币。
3. 09:10 若需修订，在表单填写记录ID和完整字段；重复场次409，核验大于座位422；已发生到账核销的场次不能修订币种、金额或日期。
4. 09:20 外汇结算页登记USD汇率（生效日、1美元=7.12元）；JPY场次YM-186缺率暂挂，补登JPY汇率后自动按场次日前值入账。
5. 09:30 新建“11月场馆渠道结算复核”，行场馆、列渠道、口径本币；再建同布局原币方案，两种口径分开成案。
6. 09:40 worker完成透视，刷新确认本币净额85000分计入相应单元，总计守恒；原币方案按币种分列，不跨币种相加。
7. 10:00 点击单元格下钻，查看原始场次与分项金额，选“为该单元起草差异复核”（仅本币透视）。
8. 10:10 回单预期比账面多1234分，写明“回单晚入账12.34元，已核对凭据”，保存草案。
9. 10:20 admin签核，viewer下载 `stage-pivot-<id>.json`，包含冻结明细与所有边际总计。
10. 10:40 海外票款到账：在应收台账选YM-181，登记到账原币与实兑人民币，系统按入账汇率核销账面并确认已实现汇兑损益；应收不超额，超量422。
11. 11:00 月末提交估值日估值，任务排队、运算、生效；余款按估值日最近前值汇率重估，未实现损益与余款原子替换，viewer下载 `fx-valuation-<id>.json` 依据。

## 口径和算法

输入金额为非负整数分，退款+渠道费不得超过票款；座位和核验为整数，核验≤座位；场次编号唯一。业务日期由date校验，月份取YYYY-MM。行/列仅允许venue/play/channel/month且不可相同，不执行SQL或表达式。每个单元由Python按所选维度groupby，净额=票款−退款−渠道费。金额、座位、核验和场次计数的单元求和、行合计、列合计必须严格等于总计，否则任务失败。

上座率=总核验/总座位，不能平均各场百分比。零座位为null/未定义，不能伪装0%。已知样例：100座100核验和300座150核验，上座率250/400=.625，简单平均.75是错误口径。金额分币保持整数，持久化采用BIGINT，显示时除100。

**外汇口径。** 每场保存原币应收=票款−退款−渠道费（净额，原币分）。汇率按币种+生效日维护，场次按场次日最近前值折算入账，缺率应收暂挂（pending），补登或更正汇率后自动补入账；人民币场次按1:1。到账可分次核销：核销账面=到账原币×入账汇率快照，应收不超额；已实现汇兑损益=实兑人民币−核销账面。原账面额=已核销账面额+余款账面额，分币尾差留在余款，最后一笔核销结清全部剩余账面。估值按指定估值日的最近前值汇率重估余款，未实现损益=重估后余款−重估前余款；重估后 原账面+累计未实现=已核销+余款。汇率更正或新到账使未完成估值失效，已核销账面额不变；估值生效也会使其他未完成估值失效。估值任务经历排队、运算、生效；故障恢复仍用原任务编号，重试不重复核销；版本号兜底拒绝过期结果，余款与损益在同一事务原子替换。已入账应收保持历史汇率快照，更正汇率只影响暂挂补入账与后续估值。

**透视口径。** 本币透视以人民币汇总：净额=应收台账账面额，分项按场汇率折算，缺率暂挂场次不计入金额并以pending_count列示。原币透视按币种分列求和，不跨币种相加，各币种行列总计分别守恒；差异复核只能建在本币透视单元上。

提交时冻结输入快照，worker保留checksum。下钻只读该快照，原始明细修订不会改变历史结果。差异=回单预期净额−冻结账面净额，可正可负。签核只确认复核理由，不改账、不付款。已签核Review不可更新，需新增复核；Pivot为不可覆盖版本，重新计算需新建。空数据、重复场次或非法维度失败可恢复，补录/调整后新建任务。单worker启动恢复queued/running任务（透视与估值两队列）。

## 技术和目录

|层|实现|
|---|---|
|前端|原生ES modules、Noto双字体、OKLCH色板、共用表格/字段/状态组件|
|服务|Python3.11/FastAPI、SQLAlchemy、PyJWT、Redis队列|
|持久化|MySQL8 + Redis7 + 共享结果卷|
|网关|Nginx1.27，同源`/api/`剥离前缀转到后端根路由|

`backend/src`分routes/controllers/services/models/schemas/config/middlewares/utils/constants；`frontend/src`分api/stores/pages/components/hooks/utils/constants/types/router。Settlement、Pivot、Review、FxRate、Receivable、Receipt、Valuation贯穿数据库/API/页面。请求ID、安全响应头两中间件；写操作审计、全局错误响应。角色ROLES、状态STATES、维度DIMENSIONS、场馆VENUES、渠道CHANNELS、币种CURRENCIES、口径BASES：后端`src/constants/enums.py`与`schemas/business.py`，前端`src/constants/enums.js`；折算/核销/估值算法在后端`services/fx.py`，透视维度白名单另见`services/analysis.py`；持久化列见models/entities.py。

5服务frontend/backend/worker/db/redis均有healthcheck。backend等db/redis，worker额外等backend，frontend等backend。MySQL/Redis/结果使用命名卷，worker `/tmp/heartbeat`验证活性，结果落共享 `/artifacts`（可用ARTIFACTS_DIR覆盖）。`NETWORK_SUBNET=10.253.112.0/24`规避本机默认地址池耗尽，可移机修改；其他环境变量COMPOSE_PROJECT_NAME、FRONTEND_PORT、BACKEND_PORT、DB_PORT、DB_PASSWORD、JWT_SECRET、SEED_DEMO见.env.example。演示密码与JWT密钥部署时替换。

本地开发：先起db/redis，在backend安装requirements并配置DATABASE_URL/REDIS_URL/JWT_SECRET，运行 `uvicorn src.main:app --reload`；前端继续用Nginx同源代理。初表由ORM创建；启动时执行轻量迁移（`services/migrate.py`）：为settlements补currency、pivots补basis、建外汇新表、把存量场次按人民币补建应收，幂等可重复。migrations提供对应DDL（001初始、002外汇），无在线版本迁移执行器。清理用 `docker compose down -v --remove-orphans`。

范围：逐条表单/API录入，无Excel导入、删除/分页或多渠道拆场；仅提供JSON完整导出；回单预期与实兑人民币人工输入，不对接银行；本地签核、单worker、Google Fonts离线回退。测试与截图在 `../../test-artifacts/gb-3112/TESTING.md`，不在源码目录。许可证MIT，见LICENSE。
