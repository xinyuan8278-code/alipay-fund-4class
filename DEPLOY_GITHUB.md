# 部署说明 · GitHub 定时任务（周六 09:00 北京时间）

> 这个项目**不需要任何密钥**：数据全部来自公开接口（东方财富 / 天天基金 / 腾讯行情）。
> 所以在 GitHub Actions 上可以直接跑，不需要配置 Secrets。

---

## 零、最快路径：一条命令（推荐）

公司网里 `git` 协议被拦（HTTPS 直连 reset、SSH 无密钥），所以项目自带一个**全程走 REST API 的发布脚本**，
不依赖 git：

```bash
# 1) 建一个 GitHub 个人访问令牌（Fine-grained 或 Classic 都行）
#    权限：Contents = Read and write、Workflows = Read and write、Pages = Read and write
export GITHUB_TOKEN=ghp_xxx          # Git Bash；Windows CMD 用 set GITHUB_TOKEN=ghp_xxx
python deploy_github.py --dry-run    # 先只看清单 + 校验令牌，不写远端
python deploy_github.py              # 建仓库 → 推送 26 个文件 → 开 Pages → 触发一次周更
```

脚本会打印仓库地址、Actions 地址和线上地址。默认仓库名 `alipay-fund-4class`，
可用 `--repo 别的名字` 改。

> 网络说明：脚本自动读取系统代理（`HTTPS_PROXY=http://127.0.0.1:9567/`，即本机 Clash），
> 与 `curl` 走同一条通路；`git push` 走不通时用它即可。

---

## 一、仓库怎么建（3 分钟）

1. 在 GitHub 新建一个 **Public** 仓库（Private 也能用 Pages，但需要 Pro；Public 免费）。
   建议仓库名：`alipay-fund-4class`（与 `us-tech-morning-report` 保持一致的命名风格）。
2. 把 `alipay_fund_4class/` 这个目录**整个**作为仓库根目录推上去（目录里已经带好 `.github/workflows/weekly.yml`）：

```bash
cd alipay_fund_4class
git init
git add -A
git commit -m "feat: 四大类基金组合筛选与回测站点 v9（首次提交）"
git branch -M main
git remote add origin https://github.com/<你的用户名>/alipay-fund-4class.git
git push -u origin main
```

3. 仓库 → **Settings → Pages** → Source 选 **GitHub Actions**（不要选 Deploy from a branch）。

## 二、首次跑通（手动触发）

仓库 → **Actions** → 左侧「四大类基金组合周更」→ 右上 **Run workflow**。

流水线会依次跑 12 步（候选池 → 净值 → 官方字段 → 指标 → 打分 → 换标闸门 → 回测网格 → 52 周滚动 → 渲染 → 自检 → 发布），
实测本地全量约 **2.5 分钟**（首次抓 600+ 只净值会久一点）。

跑完后：
- 线上地址：`https://<你的用户名>.github.io/alipay-fund-4class/`（Pages 首次生效要等 1~2 分钟）
- 每次运行的产物（HTML + 全部 JSON）在 Actions 页面的 **Artifacts: page-and-data** 里可下载

## 三、定时任务

`.github/workflows/weekly.yml` 里已经写好：

```yaml
on:
  schedule:
    - cron: '0 1 * * 6'      # 每周六 01:00 UTC = 北京时间 09:00
  workflow_dispatch:          # 也支持手动触发
```

> 注意：GitHub 的 `schedule` 在高峰期可能延迟几分钟到十几分钟，属正常现象。

## 四、改口径 / 换腿

- **改权重网格范围**：`scripts/n_bt2.py` 顶部 `CAP_LO / CAP_HI`、`enumerate_grid(0, 8)`。
- **改回测窗口**：`scripts/n_bt2.py` 的 `LOOKBACK_DAYS = 1095`（3 年）。
- **改腿集（在持标的）**：`work/qdii2026/swap_state.json` 的 `hold`。
  换腿后**必须**重跑 `v_wt_hist.py` 与 `s_page_data4.py`（否则页面数字会自相矛盾）。
- **改候选池关键词**：`scripts/h_universe.py` 的 `INC / EXC / EXC_A`。
- **对齐历史某一时点**：`QDII_UNTIL=2026-10-14 python run_weekly.py`（产物名会带 `_asof20261014`）。

## 五、需要注意的风险

1. **GitHub Actions 出口在境外**：东财 `fund.eastmoney.com` / `fundmobapi.eastmoney.com` 目前公网可直连，
   但若哪天对境外 IP 限流，`b_fetch.py` 会失败。失败时**不会覆盖上一版页面**（渲染步骤没跑到就不会发布新产物），
   线上会保持上一周的版本。可退而求其次：本地跑 `python run_weekly.py` 后手动 `git push` `deploy_site/`。
2. **接口硬约束**（写死在代码里，别改）：
   `fundmobapi` 必须走纯 `http://`；`User-Agent` 只能写 `Mozilla/5.0`（多一个字符就 403）。
3. **数据合规**：页面已内置「本网页不涉及任何基金推荐，仅限研究使用」与内部研究限定。

## 六、本地怎么跑（Windows）

```bash
cd alipay_fund_4class
python run_weekly.py                 # 全量周更
python run_weekly.py --fast          # 跳过净值缓存刷新（调试）
python scripts/verify_page.py deploy_site/index.html   # 页面自检
```

产物：
- `outputs/final/alipay_fund_4class_portfolio_<YYYYMMDD>_<HHMMSS>_v9.html`（版本号命名，不覆盖旧版）
- `deploy_site/index.html`（发布包，GitHub Pages 就是用它）
- `deploy_site/archive/`（最近 8 期留档）
