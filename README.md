# 支付宝可申购基金 · 四大类筛选与组合回测（v9 复刻版）

按 `alipay_fund_4class_site_build_spec_20261016.md` 从零重建的完整流水线 + 单页网站。
参考线上样式：<http://101.96.243.251/share/20261015114046-3a60d35e545c/>

## 一、这个站是什么

为一个「支付宝能买到的场外基金」组合做**四大类筛选 + 组合回测 + 每周实盘下单清单**的单页网页：

- 四条腿：**债券ETF / 黄金ETF / A股·科创ETF / 能源ETF**（只做场外可申购的联接份额，场内 ETF 支付宝买不到）
- 权重：**5% 整数倍网格（单腿 0%~40%，允许为 0）**，周度再平衡，扣逐腿真实申赎费
- 主推规则：五窗口（上周／近一月／近三月／今年以来／近2年）**全部跑赢余额宝 000198** 的可行解里取**夏普最高**；
  **无可行解则整仓货基**（页面会醒目提示）
- 页面：单文件自包含 HTML（ECharts 内联、无外链）、4 张图、下单清单可按本金重算、下周操作给 200 字行情判断

## 二、目录结构

```
alipay_fund_4class/
├─ run_weekly.py              ← 一键周更（本地 / GitHub Actions 通用）
├─ DEPLOY_NETLIFY.md          ← 【推荐】Netlify 部署说明（连 GitHub 仓库自动更新）
├─ DEPLOY_GITHUB.md           ← GitHub Pages 部署说明（备选）
├─ netlify.toml               ← Netlify 站点配置（publish = deploy_site）
├─ deploy_github.py           ← 一键建仓库+推送（REST API，不依赖 git 协议）
├─ .github/workflows/weekly.yml
├─ assets/echarts.min.js      ← 内联用的 ECharts（约 1.0MB）
├─ scripts/                   ← 12 步流水线（只用 Python 标准库）
│   ├─ common.py              HTTP/缓存/日期/指标
│   ├─ h_universe.py          候选池（ETF 族 + 四大类关键词）
│   ├─ b_fetch.py             逐日净值（pingzhongdata）
│   ├─ h_fetch.py             官方字段 + f10 申赎费
│   ├─ c_metrics.py           自算指标 + 跟踪误差
│   ├─ m_pick.py              债券/黄金/能源 四项 100 分
│   ├─ p_astock.py            A股/科创 120 分优选
│   ├─ j_exch.py              场内折溢价（腾讯行情）
│   ├─ swap_guard.py          换标闸门 S1/S2/S3
│   ├─ n_bt2.py               周度回测 + 5% 网格 + 无解退化
│   ├─ v_wt_hist.py           近一年权重 52 周滚动重构
│   ├─ s_page_data4.py        页面数据组装
│   ├─ o_build_page9.py       渲染单文件 HTML
│   └─ verify_page.py         页面自检
├─ work/qdii2026/             ← 中间产物（JSON / cache / logs）
├─ outputs/final/             ← 交付页（版本号命名，不覆盖旧版）
└─ deploy_site/               ← 发布包（index.html + archive/）
```

## 三、怎么跑

```bash
python run_weekly.py                    # 全量周更（含刷新净值缓存），约 2.5 分钟
python run_weekly.py --fast             # 跳过缓存刷新（调试用）
QDII_UNTIL=2026-10-14 python run_weekly.py   # 对齐历史口径（产物名带 _asof）
python scripts/verify_page.py deploy_site/index.html

# 一键发布到 GitHub（建仓 + 推送；之后在 Netlify 连仓库就能自动更新）
GITHUB_TOKEN=ghp_xxx python deploy_github.py --dry-run   # 先校验
GITHUB_TOKEN=ghp_xxx python deploy_github.py             # 加 --pages 才启用 GitHub Pages
```

> **部署推荐走 Netlify**：`netlify.toml` 已配好 `publish = deploy_site`，Netlify 只发布静态文件、
> 不跑构建；每周由 GitHub Actions 提交新页面 → Netlify 收到 push 自动发布。
> 详细步骤见 `DEPLOY_NETLIFY.md`。

## 四、口径校验（可复查）

用同一窗口 `2023-10-16 ~ 2026-10-14（728 个交易日）`跑，本实现与参考站的行为一致：

| 项 | 本实现 | 参考站 |
|---|---|---|
| 沪深300 五窗口 | −3.21% / −5.69% / −11.26% / −7.45% / +11.26% | 完全一致 |
| 货基 五窗口 | +0.03% / +0.07% / +0.21% / +0.72% / +2.19% | 完全一致 |
| 主推权重 | 能源 40 / 债券 40 / 黄金 15 / 科创 5 | 一致 |
| 可行解组数 | 3 / 375（另两组同参考） | 3 / 375 |
| 主推指标 | 年化 11.48% / 波动 11.50% / 回撤 10.22% / 夏普 0.87 / 卡玛 1.12 | 11.51% / 11.50% / 10.22% / 0.87 / 1.13 |
| v4 旧口径对照 | 能源20/债券40/黄金20/科创20，年化 16.88%、近2年 +38.95% | 16.91% / +39.04% |
| 近一年无解周 | 16 / 52 | 16 / 52 |
| 自算 vs 官方近1年 | 偏差中位数 0.03pp、90 分位 0.08pp | 0.04pp / 0.10pp |

差异都在 0.05pp 量级，来自一天的数据更新与再平衡日的微差。

## 五、两条数据口径

- **默认（最新净值日）**：数据到 2026-10-15。这一周**无可行解** → 按规则整仓货基，页面会给出醒目提示。
  这是规则设计内的正常结果（近一年 17/52 周如此）。
- **对齐版**：`QDII_UNTIL=2026-10-14`，数据到 2026-10-14，与参考站逐项可比。

## 六、已知坑（已在代码里规避）

1. `fundmobapi` 必须纯 `http://`；`User-Agent` 只能写 `Mozilla/5.0`（长 UA 会 403）。
2. 货币基金**没有净值序列**，要用 `Data_millionCopiesIncome`（万份收益）累乘。
3. 周/月边界用**自然周序号**（`date.toordinal()`），别用 `mktime` + `strftime('%G%V')`，会因时区差一周。
4. 网格枚举必须先算 `d = 20 - a - b - c` 再校验区间，不能写成「上界递减」。
5. 风险平价的 `1/σ²` 会把债券推到 80%+，必须配单腿 10%~40% 的水填充夹逼。
6. 筛选明细主表只列**场外可申购**（参考站口径）；场内 ETF 走折叠表。
7. 页面上「申购费」不是剩余现金：正确写法是「合计下单 X 元，其中费用 Y 元，实际买入市值 X−Y 元」。
