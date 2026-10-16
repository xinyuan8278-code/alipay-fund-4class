# -*- coding: utf-8 -*-
"""周更一键流水线（本地 Windows / GitHub Actions Linux 通用）

用法：
    python run_weekly.py            # 全量周更（含强制刷新净值缓存）
    python run_weekly.py --fast     # 跳过净值缓存刷新（调试用）
    QDII_UNTIL=2026-10-14 python run_weekly.py   # 固定历史口径（对齐版）

产物：
    outputs/final/alipay_fund_4class_portfolio_<YYYYMMDD>_<HHMMSS>_v9.html
    deploy_site/index.html          ← 发布包（GitHub Pages 直接用它）
"""
import os, sys, shutil, subprocess, time, glob, re

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(ROOT, 'scripts')
WORK = os.path.join(ROOT, 'work', 'qdii2026')
FINAL = os.path.join(ROOT, 'outputs', 'final')
SITE = os.path.join(ROOT, 'deploy_site')

STEPS = [
    ('01 候选池', ['h_universe.py']),
    ('02 逐日净值', ['b_fetch.py']),
    ('03 官方字段 + 费率', ['h_fetch.py']),
    ('04 自算指标', ['c_metrics.py']),
    ('05 四项打分（债券/黄金/能源）', ['m_pick.py']),
    ('06 A股/科创优选池', ['p_astock.py']),
    ('07 场内折溢价', ['j_exch.py']),
    ('08 换标闸门', ['swap_guard.py']),
    ('09 周度回测 + 5% 网格', ['n_bt2.py']),
    ('10 近一年权重滚动重构', ['v_wt_hist.py']),
    ('11 页面数据组装', ['s_page_data4.py']),
    ('12 渲染单文件 HTML', ['o_build_page9.py']),
]


def run(script, args=(), quiet=False):
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONPATH'] = SCRIPTS + os.pathsep + env.get('PYTHONPATH', '')
    cmd = [sys.executable, os.path.join(SCRIPTS, script)] + list(args)
    t0 = time.time()
    p = subprocess.run(cmd, cwd=SCRIPTS, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode('utf-8', 'replace')
    if not quiet:
        for line in out.strip().splitlines()[-6:]:
            print('    ' + line)
    if p.returncode != 0:
        print(out)
        raise SystemExit('!! %s 失败（退出码 %d）' % (script, p.returncode))
    print('   %s 完成 %.1fs' % (script, time.time() - t0))
    return out


def refresh_cache():
    """周更第一步：清掉在持腿 + 基准 + 货基的净值缓存，强制重取最新净值"""
    st = os.path.join(WORK, 'swap_state.json')
    codes = ['510300', '000198']
    if os.path.exists(st):
        import json
        try:
            hold = json.load(open(st, encoding='utf-8')).get('hold') or {}
            codes += [v['code'] for v in hold.values()]
        except Exception:
            pass
    n = 0
    for c in codes:
        p = os.path.join(WORK, 'cache', '%s.json' % c)
        if os.path.exists(p):
            os.remove(p)
            n += 1
    print('   已清理 %d 个净值缓存（在持腿 + 沪深300 + 货基）' % n)


def publish(latest):
    os.makedirs(SITE, exist_ok=True)
    shutil.copyfile(latest, os.path.join(SITE, 'index.html'))
    shutil.copyfile(latest, os.path.join(SITE, 'latest.html'))
    # 顺手把最近 8 期留档到 deploy_site/archive/
    arch = os.path.join(SITE, 'archive')
    os.makedirs(arch, exist_ok=True)
    shutil.copyfile(latest, os.path.join(arch, os.path.basename(latest)))
    old = sorted(glob.glob(os.path.join(arch, '*.html')), key=os.path.getmtime, reverse=True)
    for f in old[8:]:
        os.remove(f)
    print('发布包：%s/index.html（%.2f MB）'
          % (SITE, os.path.getsize(latest) / 1048576.0))


def main():
    fast = '--fast' in sys.argv
    t0 = time.time()
    print('=== 支付宝可申购基金 · 四大类筛选与组合回测 · 周更流水线 ===')
    print('数据口径：%s' % (os.environ.get('QDII_UNTIL') or '最新净值日'))
    if not fast:
        print('[00] 刷新净值缓存')
        refresh_cache()
    for name, scripts in STEPS:
        print('[%s]' % name)
        for sc in scripts:
            run(sc, quiet=False)
    # 取本次真实产物（不要写死版本号）
    files = [f for f in glob.glob(os.path.join(FINAL, '*_v9*.html')) if '_asof' not in f]
    files.sort(key=os.path.getmtime)
    if not files:
        raise SystemExit('!! 没有找到渲染产物')
    latest = files[-1]
    publish(latest)
    print('=== 完成，用时 %.1fs ===' % (time.time() - t0))
    print('产物：%s' % latest)


if __name__ == '__main__':
    main()
