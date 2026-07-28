# 币圈与区块链英语：MVP 内容 QA

## 自动化结果

- Course / Level / Unit / Day / Sentence：1 / 1 / 2 / 14 / 40。
- Unit 1 与 Unit 2 各 7 Day、20 条新句。
- 40 个 sentence ID、Item stable key 和英文目标均唯一。
- 英文句长为 8–11 词，符合中级技术英语的短句学习目标。
- Day 5、6、7 只复用已学 stable key，没有为复习重复创建 Item。
- 全课程活动类型只有必做 `typing` 和 Day 7 可选 `fsrs`。
- 40 个 `audio_hint` 均为 `null`，没有 `speaking`、`listening` 或 `dictation` 标签和活动。

## 内容与术语检查

- 钱包、地址、私钥和恢复短语各自承担不同语义，没有把资产描述成保存在钱包应用内部。
- pending、confirmed、transaction hash、gas fee、network 等术语放在真实转账场景中。
- centralized exchange 与 decentralized exchange、market order 与 limit order、liquidity 与 slippage 分别对比。
- `TVL` 明确写为 `Total Value Locked`，中文统一为“总锁定价值”。
- market capitalization、fully diluted valuation、trading volume 和 TVL 不互相混用。
- yield、leverage、liquidation、stablecoin 和 audit 都带有风险边界，不承诺收益或绝对安全。
- 固定大小写包括 `DeFi`、`TVL`、`Total Value Locked`、`Layer 2` 和 `FSRS`。

## 事实来源抽查

- 钱包、账户和交易表述参考 [Ethereum accounts](https://ethereum.org/developers/docs/accounts)、[How to use Ethereum wallets](https://ethereum.org/guides/how-to-use-a-wallet)、[Transactions](https://ethereum.org/developers/docs/transactions) 与 [Block explorers](https://ethereum.org/developers/docs/data-and-analytics/block-explorers/)。
- 市价单、限价单和滑点参考 [Coinbase order types](https://help.coinbase.com/en-gb/coinbase/trading-and-funding/advanced-trade/order-types) 与 [Coinbase slippage and spread](https://help.coinbase.com/en/coinbase/trading-and-funding/buying-selling-or-converting-crypto/understanding-slippage-and-spread)。
- 流动性与无常损失参考 [Uniswap impermanent loss](https://support.uniswap.org/hc/en-us/articles/20904453751693-What-is-Impermanent-Loss)。
- TVL 定义参考 [DefiLlama FAQ](https://docs.llama.fi/faqs/frequently-asked-questions) 与 [DefiLlama data definitions](https://docs.llama.fi/analysts/data-definitions)。
- 市值和 FDV 公式参考 [CoinGecko market capitalization](https://www.coingecko.com/learn/what-is-market-cap-in-crypto) 与 [CoinGecko FDV](https://www.coingecko.com/learn/what-is-fully-diluted-valuation-fdv-in-crypto)。
- 质押、Layer 2、跨链和审计风险参考 [Ethereum proof of stake](https://ethereum.org/developers/docs/consensus-mechanisms/pos/)、[What is Layer 2](https://ethereum.org/layer-2/learn/)、[Bridges](https://ethereum.org/developers/docs/bridges) 与 [Smart contract security](https://ethereum.org/developers/docs/smart-contracts/security)。

## 已知风险与人工试学建议

- 不同链、钱包、交易所和协议可能对 confirmation、staking、bridge、TVL 等术语采用更具体的口径；本课只提供通用入门表达。
- FDV 数据源可能根据 total supply 或 max supply 的可用性采用不同口径；当前句子使用常见的 total supply 入门定义。
- stablecoin、Layer 2 和 bridge 的实现差异较大，不能从一句定义推断具体产品安全性。
- 建议由熟悉 DeFi 数据与链上安全的审核者逐句签核，再让 3–5 名目标用户试学两个 Unit。
- 完成技术复核与真人试学前，课程状态必须保持 `draft`。
