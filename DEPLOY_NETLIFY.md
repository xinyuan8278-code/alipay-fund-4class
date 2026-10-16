# 部署到 Netlify（连接 GitHub 仓库 · 每周自动更新）

目标形态：

```
GitHub 仓库（代码 + 每周产物）
   │  push（每周六 09:00 由 GitHub Actions 自动提交新页面）
   ▼
Netlify  ← 收到 push 自动发布  →  https://<站点名>.netlify.app/
```

**Netlify 这边不跑任何构建**（不装 Python、不抓数据），只负责把 `deploy_site/` 目录发布出去。
重活全部在 GitHub Actions 里干——这样最稳：Netlify 构建机在境外，直接抓东财接口可能被限流。

---

## 第 0 步（30 秒先看效果，可选）

不想等仓库就先看效果：打开 <https://app.netlify.com/drop>，
把本机的 `alipay_fund_4class/deploy_site` **整个文件夹拖进去**，几秒后得到一个临时网址。
确认页面没问题再走下面的正式流程。

---

## 第 1 步：建 GitHub 仓库

仓库里必须包含 `.github/workflows/weekly.yml` 和 `netlify.toml`（项目已经带好了）。

**方式一（推荐，一条命令）**：给我一个 GitHub 令牌，我直接建仓库 + 推送：

```bash
# 令牌权限：Classic → repo + workflow；Fine-grained → Contents/Workflows = Read and write
set GITHUB_TOKEN=ghp_xxx            # CMD；Git Bash 用 export
cd alipay_fund_4class
python deploy_github.py --dry-run   # 先校验
python deploy_github.py --no-pages  # 建仓库 + 推送 27 个文件（不启用 GitHub Pages，走 Netlify）
```

**方式二（自己在网页做）**：GitHub 新建 Public 仓库 → 名为 `alipay-fund-4class` → 不要勾 Add README
→ 然后用本机 git 或 GitHub 网页上传 `alipay_fund_4class` 目录下的全部文件。

> ⚠️ 公司网把 git 协议拦了（HTTPS 直连 reset、SSH 无密钥），本机 `git push` 走不通。
> 所以方式一用的是 REST API 发布脚本；方式二建议用 GitHub 网页「Upload files」拖拽上传，
> 或把仓库目录打包后让 IT 放行。

---

## 第 2 步：Netlify 连接仓库（点 5 下）

1. 登录 <https://app.netlify.com> → 右上 **Add new site** → **Import an existing project**
2. 选 **GitHub** → 首次会要求授权 Netlify 访问你的 GitHub（授权后可选 All repositories 或只选这一个仓库）
3. 在列表里点 **alipay-fund-4class**
4. 站点设置页会读到仓库里的 `netlify.toml`，确认三项：
   - **Branch to deploy**：`main`
   - **Build command**：留空 / 默认（`netlify.toml` 里写的是 echo 占位，不干活）
   - **Publish directory**：`deploy_site`  ← 如果没自动填上，手动填这个
   - 其它（Functions directory、Environment variables）都不用动
5. 点 **Deploy site**，约 20 秒后就能打开 `https://随机名.netlify.app/`
6. 想换简洁网址：**Site configuration → Site details → Change site name**（例如 `alipay-fund-4class`）

---

## 第 3 步：让每周自动更新生效

仓库里已经有 `.github/workflows/weekly.yml`，**每周六 01:00 UTC（北京 09:00）** 自动做三件事：
跑流水线 → 把新页面提交回 `main` → Netlify 收到 push 自动发布。

- 想马上验证：仓库 → **Actions** → 「四大类基金组合周更」→ **Run workflow**
- 想改时间：编辑 `.github/workflows/weekly.yml` 里的 `cron`（UTC，比北京早 8 小时）

**再加一道保险（建议，2 分钟）**——万一 Netlify 的「push 自动发布」被关掉，也能强制刷新：

1. Netlify：**Site configuration → Build & deploy → Build hooks → Add build hook**
   名称填 `weekly`、分支选 `main` → 创建后复制那个 URL（形如 `https://api.netlify.com/build_hooks/xxxxxxxx`）
2. GitHub：仓库 → **Settings → Secrets and variables → Actions → New repository secret**
   名称 `NETLIFY_BUILD_HOOK`，值粘贴上一步的 URL
3. 之后每次周更，工作流会顺手 POST 这个 hook，Netlify 必定重新发布

---

## 第 4 步：不用等定时，随时手动刷新

- Netlify：**Deploys → Trigger deploy → Deploy site**（重新发布现有文件）
- 想重新抓数据出最新一版：GitHub → **Actions → Run workflow**（跑流水线 + 自动发布）

---

## 可选：让 Netlify 自己跑流水线

如果你更希望「Netlify 构建时才抓数据」（而不是靠 GitHub Actions），把 `netlify.toml` 里改成：

```toml
[build]
  publish = "deploy_site"
  command = "python3 run_weekly.py"
```

然后在 Netlify 后台把构建机 Python 设为 3.12（`netlify.toml` 的 `[build.environment]` 已写好）。
**但不推荐**：Netlify 构建机在境外，抓 `fund.eastmoney.com` 可能被限流；一旦失败会沿用仓库里上一版。

---

## 常见问题

**Q：Netlify 部署后 4 张图是空白？**
页面是单文件自包含（ECharts 内联），不该出现这种情况。先在本地用 `python scripts/verify_page.py deploy_site/index.html`
自查（应显示「`<canvas>` 数量：4」）。若自检通过而线上空白，清一次浏览器缓存（`netlify.toml` 已给 HTML 关了长缓存）。

**Q：为什么 `deploy_site/` 里还有 `latest.html` 和 `archive/`？**
`index.html` 是入口；`latest.html` 是同一份的别名；`archive/` 存最近 8 期历史版本，方便回看上周的权重。

**Q：能用自定义域名吗？**
可以：**Site configuration → Domain management → Add a domain**。内部使用的话建议加个密码或改用内网地址。

**Q：更新后页面还是旧的？**
按顺序查：① GitHub Actions 那次 run 是否成功（失败会沿用上一版，属预期）；
② Netlify Deploys 里有没有那次 push 触发的构建；③ 浏览器强刷（Ctrl+F5）。

**Q：合规提示还在吗？**
在。页面顶部有「本网页不涉及任何基金推荐，仅限研究使用。回测基于历史净值，不代表未来收益。」，
页脚有华泰期货国际业务部内部研究限定与联系人。
