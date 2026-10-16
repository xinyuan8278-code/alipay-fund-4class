# -*- coding: utf-8 -*-
"""一键把项目发布到 GitHub（不需要 git，全程走 REST API —— 公司网里 git 协议被拦、HTTPS 走代理即可）

用法：
    set GITHUB_TOKEN=ghp_xxx            # Windows
    export GITHUB_TOKEN=ghp_xxx         # Git Bash / Linux
    python deploy_github.py                       # 默认 owner=xinyuan8278-code, repo=alipay-fund-4class
    python deploy_github.py --repo 别的仓库名
    python deploy_github.py --dry-run             # 只校验 token 与文件清单，不写远端

做四件事：
  ① 校验 token（GET /user）
  ② 建仓库（已存在则跳过）
  ③ 用 Git Data API 一次性提交全部文件（blobs → tree → commit → ref）
  ④ 打开 Pages（build_type=workflow）并立刻触发 weekly.yml 跑一次
"""
import os, sys, json, base64, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
API = 'https://api.github.com'
OWNER = 'xinyuan8278-code'
REPO = 'alipay-fund-4class'
BRANCH = 'main'
HTTP_TIMEOUT = 60


# ---------------------------------------------------------------- 需要提交的文件
def collect_files():
    out = []
    keep_root = ['run_weekly.py', 'deploy_github.py', 'README.md',
                 'DEPLOY_NETLIFY.md', 'DEPLOY_GITHUB.md', 'netlify.toml', '.gitignore',
                 '.github/workflows/weekly.yml', 'assets/echarts.min.js']
    for rel in keep_root:
        p = os.path.join(ROOT, rel.replace('/', os.sep))
        if os.path.exists(p):
            out.append(rel)
        else:
            print('  ! 缺文件 %s' % rel)
    for d, pat in (('scripts', '.py'), ('deploy_site', '')):
        base = os.path.join(ROOT, d)
        for dp, dn, fn in os.walk(base):
            dn[:] = [x for x in dn if x != '__pycache__']
            for f in sorted(fn):
                if pat and not f.endswith(pat):
                    continue
                p = os.path.join(dp, f)
                out.append(os.path.relpath(p, ROOT).replace(os.sep, '/'))
    # 最新交付页 + 整页截图也带上（便于留档）
    # 只带最新一版交付页 + 整页截图留档（历史版本不入库，避免仓库臃肿）
    fin = os.path.join(ROOT, 'outputs', 'final')
    if os.path.isdir(fin):
        cand = [f for f in os.listdir(fin)
                if f.startswith('alipay_fund_4class_portfolio_') and '_asof' not in f]
        htm = sorted([f for f in cand if f.endswith('.html')],
                     key=lambda f: os.path.getmtime(os.path.join(fin, f)))
        png = sorted([f for f in cand if f.endswith('.png')],
                     key=lambda f: os.path.getmtime(os.path.join(fin, f)))
        for f in htm[-1:] + png[-1:]:
            out.append('outputs/final/' + f)
    return sorted(set(out))


# ---------------------------------------------------------------- HTTP
def api(method, path, token, body=None, raw=False):
    url = path if path.startswith('http') else API + path
    data = None
    if body is not None:
        data = json.dumps(body).encode('utf-8')
    hdr = {'User-Agent': 'alipay-fund-4class-deployer',
           'Accept': 'application/vnd.github+json',
           'Authorization': 'token ' + token}
    if data:
        hdr['Content-Type'] = 'application/json'
    op = urllib.request.build_opener(urllib.request.ProxyHandler(urllib.request.getproxies()))
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    try:
        with op.open(req, timeout=HTTP_TIMEOUT) as r:
            t = r.read().decode('utf-8', 'replace')
            return r.status, (t if raw else (json.loads(t) if t.strip() else {}))
    except urllib.error.HTTPError as e:
        t = e.read().decode('utf-8', 'replace')
        try:
            t = json.loads(t)
        except Exception:
            pass
        return e.code, t


def main():
    args = sys.argv[1:]
    owner, repo = OWNER, REPO
    if '--repo' in args:
        repo = args[args.index('--repo') + 1]
    if '--owner' in args:
        owner = args[args.index('--owner') + 1]
    dry = '--dry-run' in args
    want_pages = '--pages' in args      # 默认走 Netlify，不启用 GitHub Pages
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        print('!! 请先设置 GITHUB_TOKEN 环境变量（GitHub 个人访问令牌，需要 repo + workflow 权限）')
        return 2

    files = collect_files()
    total = sum(os.path.getsize(os.path.join(ROOT, f)) for f in files)
    print('待提交 %d 个文件，共 %.2f MB' % (len(files), total / 1048576.0))
    for f in files:
        print('   %-72s %8.1f KB' % (f, os.path.getsize(os.path.join(ROOT, f)) / 1024.0))

    st, me = api('GET', '/user', token)
    if st != 200:
        print('!! token 校验失败（%s）：%s' % (st, me))
        print('   令牌需要勾选 repo（或至少 Contents: read/write + Workflows: write + Pages: write）')
        return 3
    login = me.get('login')
    print('\n✔ token 有效，登录身份：%s' % login)
    if owner != login:
        print('  （注意：目标 owner=%s 与登录身份=%s 不同，将尝试在 owner 下建仓）' % (owner, login))

    st, r = api('GET', '/repos/%s/%s' % (owner, repo), token)
    exists = (st == 200)
    if exists:
        print('仓库已存在：%s' % r.get('html_url'))
    elif st == 404:
        if dry:
            print('（dry-run）将新建仓库 %s/%s' % (owner, repo))
        else:
            st, r = api('POST', '/user/repos', token, {
                'name': repo, 'private': False, 'auto_init': False,
                'description': '支付宝可申购基金 · 四大类筛选与组合回测（周更）'})
            if st not in (200, 201):
                print('!! 建仓失败（%s）：%s' % (st, r))
                return 4
            print('✔ 已创建仓库 %s' % r.get('html_url'))
    else:
        print('!! 查询仓库失败（%s）：%s' % (st, r))
        return 4

    if dry:
        print('\n（dry-run）清单与权限校验通过，未写远端。')
        return 0

    # ---- 空仓库（没有任何提交）时，Git Data API 的 blobs 会返回 409，
    #      所以先用 Contents API 造一个初始提交把仓库“激活”。
    st, head0 = api('GET', '/repos/%s/%s/git/ref/heads/%s' % (owner, repo, BRANCH), token)
    if st != 200:
        print('仓库还是空的，先造一个初始提交…')
        st, init = api('PUT', '/repos/%s/%s/contents/.gitkeep' % (owner, repo), token,
                       {'message': 'chore: 初始化仓库', 'branch': BRANCH,
                        'content': base64.b64encode(b'init\n').decode('ascii')})
        if st not in (200, 201):
            print('!! 初始化仓库失败（%s）：%s' % (st, init))
            return 5
        print('✔ 初始提交完成（%s）' % init.get('commit', {}).get('sha', '')[:7])

    # ---- 上传：blobs → tree → commit → ref
    print('\n开始上传…')
    blobs = []
    for i, f in enumerate(files, 1):
        p = os.path.join(ROOT, f)
        content = base64.b64encode(open(p, 'rb').read()).decode('ascii')
        st, b = api('POST', '/repos/%s/%s/git/blobs' % (owner, repo), token,
                    {'content': content, 'encoding': 'base64'})
        if st not in (200, 201):
            print('!! 上传 %s 失败（%s）：%s' % (f, st, b))
            return 5
        blobs.append({'path': f, 'mode': '100644', 'type': 'blob', 'sha': b['sha']})
        print('   [%2d/%2d] %s' % (i, len(files), f))
    st, tree = api('POST', '/repos/%s/%s/git/trees' % (owner, repo), token, {'tree': blobs})
    if st not in (200, 201):
        print('!! 建 tree 失败：%s' % (tree,))
        return 5
    st, head = api('GET', '/repos/%s/%s/git/ref/heads/%s' % (owner, repo, BRANCH), token)
    parents = [head['object']['sha']] if st == 200 else []
    st, commit = api('POST', '/repos/%s/%s/git/commits' % (owner, repo), token,
                     {'message': 'feat: 四大类基金组合筛选与回测站点（首次发布）',
                      'tree': tree['sha'], 'parents': parents})
    if st not in (200, 201):
        print('!! 建 commit 失败：%s' % (commit,))
        return 5
    if parents:
        st, res = api('PATCH', '/repos/%s/%s/git/refs/heads/%s' % (owner, repo, BRANCH), token,
                      {'sha': commit['sha'], 'force': True})
    else:
        st, res = api('POST', '/repos/%s/%s/git/refs' % (owner, repo), token,
                      {'ref': 'refs/heads/%s' % BRANCH, 'sha': commit['sha']})
    if st not in (200, 201):
        print('!! 更新分支失败：%s' % (res,))
        return 5
    print('✔ 代码已推送（%s @ %s）' % (BRANCH, commit['sha'][:7]))

    # ---- 发布通道
    if want_pages:
        st, pg = api('GET', '/repos/%s/%s/pages' % (owner, repo), token)
        if st == 200:
            st2, pg2 = api('PUT', '/repos/%s/%s/pages' % (owner, repo), token, {'build_type': 'workflow'})
            print('✔ GitHub Pages 已更新（build_type=workflow，HTTP %s）' % st2)
        else:
            st2, pg2 = api('POST', '/repos/%s/%s/pages' % (owner, repo), token, {'build_type': 'workflow'})
            print('✔ GitHub Pages 已开启' if st2 in (200, 201, 204)
                  else '! Pages 开启失败（%s）：%s' % (st2, pg2))
    else:
        print('· 未启用 GitHub Pages（按 Netlify 路线；要启用加 --pages）')

    # ---- 立刻触发一次工作流
    st, wf = api('POST', '/repos/%s/%s/actions/workflows/weekly.yml/dispatches' % (owner, repo),
                 token, {'ref': BRANCH})
    if st in (204, 201, 200):
        print('✔ 已触发 weekly.yml（等 2~4 分钟看 Actions 页）')
    else:
        print('! 触发工作流失败（%s）：%s' % (st, wf))

    print('\n=== 仓库已就绪 ===')
    print('  仓库：https://github.com/%s/%s' % (owner, repo))
    print('  动作：https://github.com/%s/%s/actions' % (owner, repo))
    print('\n=== 接下来在 Netlify 点 5 下（详见 DEPLOY_NETLIFY.md） ===')
    print('  1) https://app.netlify.com → Add new site → Import an existing project')
    print('  2) 选 GitHub → 授权 → 点仓库 %s' % repo)
    print('  3) Branch=main，Publish directory=deploy_site（netlify.toml 已写好，一般会自动读到）')
    print('  4) Deploy site')
    print('  5) （可选，强烈建议）Site configuration → Build & deploy → Build hooks')
    print('     建一个 hook → 把 URL 存成仓库 Secret：NETLIFY_BUILD_HOOK')
    if want_pages:
        print('\n  GitHub Pages：https://%s.github.io/%s/' % (owner.lower(), repo))
    return 0


if __name__ == '__main__':
    sys.exit(main())
