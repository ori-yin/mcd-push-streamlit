# -*- coding: utf-8 -*-
"""
app.py - 麦当劳 Push 日报生成器 (Streamlit Web App)
使用方法：streamlit run app.py
"""
import streamlit as st
import json, csv, io
from datetime import datetime, timedelta
from data_parser import parse_csv, calc_date_range, totals_all, ch_totals, agg_ch_pt

st.set_page_config(
    page_title="麦当劳 Push 日报生成器",
    page_icon="📊",
    layout="wide"
)

# ─── 样式 ─────────────────────────────────────────────────────
st.markdown("""
<style>
  .block-container { padding-top: 1rem; }
  .mcd-header {
    background: linear-gradient(135deg, #DA291C, #b71c1c);
    border-radius: 14px; padding: 24px 32px; color: #fff;
    margin-bottom: 20px;
  }
  .mcd-header h1 { font-size: 22px; font-weight: 900; margin: 0 0 4px 0; }
  .mcd-header p { font-size: 13px; opacity: 0.85; margin: 0; }
  .stDownloadButton > button {
    background: linear-gradient(135deg, #DA291C, #b71c1c) !important;
    color: #fff !important; border: none !important;
    border-radius: 8px !important; font-weight: 700 !important;
    padding: 8px 20px !important; font-size: 14px !important;
  }
  .stDownloadButton > button:hover {
    background: linear-gradient(135deg, #b71c1c, #8B0000) !important;
  }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="mcd-header">
  <h1>📊 麦当劳 App Push 日报生成器</h1>
  <p>上传数据 CSV → 自动生成 HTML 日报 → 下载发送</p>
</div>
""", unsafe_allow_html=True)

# ─── 文件上传 ─────────────────────────────────────────────────
col1, col2 = st.columns([1, 3], gap="large")

with col1:
    st.markdown("#### ⚙️ 配置")
    st.info("📌 自动读取 CSV 中最新日期作为昨日")
    st.markdown("---")
    st.markdown("#### 📁 数据上传")

    uploaded = st.file_uploader(
    "上传渠道触达 CSV",
    type=["csv"],
    help="CSV 字段：发送日期, 计划类型, 渠道, Plan ID, Plan名称, 预算owner, 预计触达, 触达成功, 点击人次, 点击后下单人次, 订单GC, 订单Sales"
)

    if uploaded:
        st.success(f"✅ {uploaded.name}", icon="📄")

    can_generate = uploaded is not None
    if st.button("🚀 生成日报", type="primary", use_container_width=True, disabled=not can_generate):
        st.session_state['generate'] = True
    else:
        if 'generate' not in st.session_state:
            st.session_state['generate'] = False

with col2:
    if not uploaded:
        st.markdown("#### 📋 日报预览")
        st.markdown("""
        <div style="background:#fff;border-radius:14px;padding:60px 40px;text-align:center;
                    color:#999;border:1px solid #eee;box-shadow:0 2px 10px rgba(0,0,0,.03);">
          <div style="font-size:52px;margin-bottom:16px;">📊</div>
          <div style="font-size:16px;font-weight:700;color:#666;">上传 CSV 后点击「生成日报」</div>
          <div style="font-size:13px;margin-top:8px;color:#aaa;">下载 HTML 文件后，直接发微信打开即可</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # ── 生成逻辑 ──────────────────────────────────────────────
        try:
            rows_raw, plan_cnt_all, owner_agg, all_dates = parse_csv(uploaded)
            DATE_Y, DATE_P, DATE_W = calc_date_range(all_dates)

            st.markdown(f"#### 📋 日报预览 `{DATE_Y}`")

            # 解析日期标签
            def fmt_d(d):
                if not d: return '\u2014'
                parts = d.split('/')
                if len(parts) < 3: return str(d)
                return f"{int(parts[1])}月{int(parts[2])}日"

            date_y_label = fmt_d(DATE_Y)
            date_p_label = fmt_d(DATE_P)
            date_w_start = fmt_d(DATE_W[0]) if DATE_W else '\u2014'
            date_w_end   = fmt_d(DATE_W[-1]) if DATE_W else '\u2014'

            ch_list = ["APP Push", "企微1v1", "微信小程序订阅消息", "短信"]
            CH_NAMES = {
                "APP Push": "APP Push",
                "企微1v1": "企微1v1",
                "微信小程序订阅消息": "微信小程序",
                "短信": "短信"
            }

            # ── 辅助函数 ──────────────────────────────────────────
            def ctr_v(c, r):
                return c/r*100 if r else 0

            def fmt(v, typ="num"):
                if v is None: return "-"
                if typ == "ctr": return f"{v:.2f}%"
                if typ == "pct": return f"{v:.1f}%"
                if abs(v) >= 1_000_000: return f"{v/1_000_000:.2f}M"
                if abs(v) >= 1_000: return f"{v/1_000:.1f}K"
                return f"{v:.0f}"

            def chg(y, b, pct=False):
                if not b: return "—"

                if isinstance(y, str): y = float(y.replace(b"%",b"").replace(b"pp",b""))
                if isinstance(b, str): b = float(b.replace(b"%",b"").replace(b"pp",b""))
                d = (y-b)/b*100
                return f"{'+' if d>=0 else ''}{d:.1f}{'pp' if pct else '%'}"

            def ccls(y, b):
                if not b: return ""
                return "up" if y>b else "dn" if y<b else ""

            def pp(y, b):
                return chg(y, b, pct=True)

            # ── S1 整体 KPI ────────────────────────────────────────
            metric_names = {
                'reach_plan':'预计触达','reach':'触达成功','click':'点击人次',
                'order_click':'点击后下单','gc':'订单GC','sales':'订单Sales'
            }
            metrics = ['reach_plan','reach','click','order_click','gc','sales']

            ty = totals_all(rows_raw, [DATE_Y])
            tp = totals_all(rows_raw, [DATE_P])
            tw = totals_all(rows_raw, DATE_W)
            ctr_y = ctr_v(ty['click'], ty['reach'])
            ctr_p = ctr_v(tp['click'], tp['reach'])
            ctr_w = ctr_v(tw['click'], tw['reach'])

            s1_rows = ""
            for m in metrics:
                y_, p_, w_ = ty[m], tp[m], tw[m]/7
                s1_rows += f'<tr><td class="metric-name">{metric_names[m]}</td>' \
                           f'<td class="right">{fmt(y_)}</td>' \
                           f'<td class="right">{fmt(p_)}</td>' \
                           f'<td class="right {ccls(y_,p_)}">{chg(y_,p_)}</td>' \
                           f'<td class="right">{fmt(w_)}</td>' \
                           f'<td class="right {ccls(y_,w_)}">{chg(y_,w_)}</td></tr>\n'
            s1_rows += f'<tr><td class="metric-name">CTR</td>' \
                       f'<td class="right">{ctr_y:.2f}%</td>' \
                       f'<td class="right">{ctr_p:.2f}%</td>' \
                       f'<td class="right {ccls(ctr_y,ctr_p)}">{pp(ctr_y,ctr_p)}</td>' \
                       f'<td class="right">{ctr_w:.2f}%</td>' \
                       f'<td class="right {ccls(ctr_y,ctr_w)}">{pp(ctr_y,ctr_w)}</td></tr>\n'

            # ── S2 渠道明细 ──────────────────────────────────────
            metric_sections = [
                ("触达成功", "num", lambda yc_,pc_,wc_: (yc_['reach'], pc_['reach'], wc_['reach']/7)),
                ("CTR",      "ctr", lambda yc_,pc_,wc_: (ctr_v(yc_['click'],yc_['reach']), ctr_v(pc_['click'],pc_['reach']), ctr_v(wc_['click']/7,wc_['reach']/7))),
                ("触达成功率","pct", lambda yc_,pc_,wc_: (yc_['reach']/yc_['reach_plan']*100 if yc_['reach_plan'] else 0, pc_['reach']/pc_['reach_plan']*100 if pc_['reach_plan'] else 0, (wc_['reach']/wc_['reach_plan']*100) if wc_['reach_plan'] else 0)),
            ]

            s2_rows = ""
            for metric_label, typ, extractor in metric_sections:
                s2_rows += f'<tr class="sub-header"><td colspan="6">{metric_label}</td></tr>\n'
                for ch in ch_list:
                    yc_ = ch_totals(rows_raw, ch, [DATE_Y])
                    pc_ = ch_totals(rows_raw, ch, [DATE_P])
                    wc_ = ch_totals(rows_raw, ch, DATE_W)
                    y_v, p_v, w_v = extractor(yc_, pc_, wc_)
                    vp = pp(y_v, p_v) if typ in ("ctr","pct") else chg(y_v, p_v)
                    vw = pp(y_v, w_v) if typ in ("ctr","pct") else chg(y_v, w_v)
                    s2_rows += f'<tr><td class="metric-name">{CH_NAMES[ch]}</td>' \
                               f'<td class="right">{fmt(y_v,typ)}</td>' \
                               f'<td class="right">{fmt(p_v,typ)}</td>' \
                               f'<td class="right {ccls(y_v,p_v)}">{vp}</td>' \
                               f'<td class="right">{fmt(w_v,typ)}</td>' \
                               f'<td class="right {ccls(y_v,w_v)}">{vw}</td></tr>\n'

            # ── S3 渠道 × 计划类型 ─────────────────────────────────
            PTYPE_ORDER = ["aarr", "normal"]
            PTYPE_LABELS = {"aarr": "AARR", "normal": "Normal"}

            s3_html = ""
            for ch in ch_list:
                for ptype in PTYPE_ORDER:
                    yd  = agg_ch_pt(rows_raw, ch, ptype, [DATE_Y])
                    pd_ = agg_ch_pt(rows_raw, ch, ptype, [DATE_P])
                    wd  = agg_ch_pt(rows_raw, ch, ptype, DATE_W)
                    if all(yd[k]==0 for k in ['reach','click','order_click','gc','sales']):
                        continue
                    label = f"{CH_NAMES[ch]} / {PTYPE_LABELS[ptype]}"
                    s3_html += f'<tr class="sub-header"><td colspan="6">{label}</td></tr>\n'
                    for name, y_, p_, wv, is_ctr in [
                        ("预计触达",   yd['reach_plan'],  pd_['reach_plan'],  wd['reach_plan']/7,  False),
                        ("触达成功",   yd['reach'],        pd_['reach'],        wd['reach']/7,        False),
                        ("点击人次",   yd['click'],        pd_['click'],        wd['click']/7,        False),
                        ("点击后下单", yd['order_click'],  pd_['order_click'],  wd['order_click']/7, False),
                        ("订单GC",     yd['gc'],           pd_['gc'],           wd['gc']/7,           False),
                        ("订单Sales",  yd['sales'],        pd_['sales'],        wd['sales']/7,        False),
                        ("CTR",        ctr_v(yd['click'],yd['reach']), ctr_v(pd_['click'],pd_['reach']), ctr_v(wd['click']/7,wd['reach']/7), True),
                    ]:
                        typ_ = "ctr" if is_ctr else "num"
                        vp = pp(y_, p_) if is_ctr else chg(y_, p_)
                        vw = pp(y_, wv) if is_ctr else chg(y_, wv)
                        s3_html += f'<tr><td>{name}</td>' \
                                   f'<td class="right">{fmt(y_,typ_)}</td>' \
                                   f'<td class="right">{fmt(p_,typ_)}</td>' \
                                   f'<td class="right {ccls(y_,p_)}">{vp}</td>' \
                                   f'<td class="right">{fmt(wv,typ_)}</td>' \
                                   f'<td class="right {ccls(y_,wv)}">{vw}</td></tr>\n'

            # ── S1 combo chart 数据 ──────────────────────────────
            s1_reach_js = json.dumps([totals_all(rows_raw, [d])['reach'] for d in all_dates], ensure_ascii=False)
            s1_ctr_js   = json.dumps([ctr_v(totals_all(rows_raw, [d])['click'], totals_all(rows_raw, [d])['reach']) for d in all_dates], ensure_ascii=False)

            # ── S2 chart 数据 ────────────────────────────────────
            x_dates_js  = json.dumps([fmt_d(d) for d in all_dates], ensure_ascii=False)
            ch_names_js = json.dumps({ch: CH_NAMES[ch] for ch in ch_list}, ensure_ascii=False)
            ch_colors_js = json.dumps({
                "APP Push":"#DA291C","企微1v1":"#FFC72C",
                "微信小程序订阅消息":"#46B5D8","短信":"#888888"
            }, ensure_ascii=False)
            y_data_js = json.dumps({ch: [rows_raw.get(d,{}).get(ch,{}) for d in all_dates] for ch in ch_list}, ensure_ascii=False)

            # ── S3-a: AARR vs Normal ─────────────────────────────
            reach_aarr_js   = json.dumps([sum(rows_raw.get(d,{}).get(ch,{}).get('aarr',{}).get('reach',0) for ch in ch_list) for d in all_dates], ensure_ascii=False)
            reach_normal_js  = json.dumps([sum(rows_raw.get(d,{}).get(ch,{}).get('normal',{}).get('reach',0) for ch in ch_list) for d in all_dates], ensure_ascii=False)

            # ── S3-b: 渠道 Plan 个数 ──────────────────────────────
            plan_cnt_js = json.dumps({ch: [len(plan_cnt_all.get(d,{}).get(ch, set())) for d in all_dates] for ch in ch_list}, ensure_ascii=False)

            # ── HTML ───────────────────────────────────────────────

            # ===== S4: 按计划类型 x 预算 Owner ========================
            SEND_DATE = 'send_date'
            PTYPE_COL = '计划类型'
            CLICK_COL = '点击人次'
            REACH_COL = '触达成功'
            GC_COL    = '订单GC'
            SALES_COL = '订单Sales'
            ORDER_COL = '点击后下单人次'
            PLAN_COL  = '预计触达'

            s4_html = ''
            s4_chart_owners_js = '[]'
            s4_chart_y_js = '[]'
            s4_chart_w_js = '[]'


            if owner_agg:
                s4_by_ptype = {}




                uploaded.seek(0)
                # 复用 data_parser.py 中的编码处理函数
                from data_parser import read_csv_with_encoding
                
                f = read_csv_with_encoding(uploaded)
                reader = csv.DictReader(f)
                for row in reader:
                    d   = row.get(SEND_DATE, '').strip().split()[0]
                    pt  = row.get(PTYPE_COL, '').strip()
                    oid = row.get('预算owner', '[NULL]').strip()
                    if not d or d == SEND_DATE:
                        continue
                f.close()
                
                        try:
                            c  = float(row.get(CLICK_COL, 0) or 0)
                            r  = float(row.get(REACH_COL, 0) or 0)
                            g  = float(row.get(GC_COL, 0) or 0)
                            s  = float(row.get(SALES_COL, 0) or 0)
                            oc = float(row.get(ORDER_COL, 0) or 0)
                            rp = float(row.get(PLAN_COL, 0) or 0)
                        except:
                            continue
                        if pt not in s4_by_ptype:
                            s4_by_ptype[pt] = {}
                        if oid not in s4_by_ptype[pt]:
                            s4_by_ptype[pt][oid] = {'y':{},'p':{},'w':{}}
                        if d == DATE_Y:
                            bucket = 'y'
                        elif d == DATE_P:
                            bucket = 'p'
                        elif d in DATE_W:
                            bucket = 'w'
                        else:
                            continue
                        if d not in s4_by_ptype[pt][oid][bucket]:
                            s4_by_ptype[pt][oid][bucket][d] = {'click':0,'reach':0,'gc':0,'sales':0,'order_click':0,'reach_plan':0}
                        for k, v in [('click',c),('reach',r),('gc',g),('sales',s),('order_click',oc),('reach_plan',rp)]:
                            s4_by_ptype[pt][oid][bucket][d][k] += v

                def s4_owner_totals(pkey, owner, key):
                    data = s4_by_ptype.get(pkey, {}).get(owner, {}).get(key, {})
                    t = {'click':0,'reach':0,'gc':0,'sales':0,'order_click':0,'reach_plan':0}
                    for d, vals in data.items():
                        for k in t:
                            t[k] += vals.get(k, 0)
                    if key == 'w':
                        for k in t:
                            t[k] = t[k] / 7
                    return t

                def s4_ctr(click, reach):
                    return 0.0 if reach == 0 else (click/reach*100)

                OWNER_ORDER = ['Reach','BF','McCafe','Membership','MDS','Field MKT','Chicken','OMM','[NULL]']
                PTYPE_S4    = [('aarr','AARR'), ('normal','Normal')]

                s4_html = ''
                for pkey, ptype_label in PTYPE_S4:
                    owners_in_ptype = [o for o in OWNER_ORDER if o in s4_by_ptype.get(pkey, {})]
                    if not owners_in_ptype:
                        continue
                    s4_html += '<tr class=sub-header><td colspan=6>' + ptype_label + '</td></tr>' + chr(10)
                    for owner in owners_in_ptype:
                        yd = s4_owner_totals(pkey, owner, 'y')
                        pd_ = s4_owner_totals(pkey, owner, 'p')
                        wd  = s4_owner_totals(pkey, owner, 'w')
                        if all(yd[k]==0 for k in ['reach','click','order_click','gc','sales']):
                            continue
                        s4_html += '<tr class=sub-header><td colspan=6>' + owner + '</td></tr>' + chr(10)
                        y_ctr = s4_ctr(yd['click'],yd['reach'])
                        p_ctr = s4_ctr(pd_['click'],pd_['reach'])
                        w_ctr = s4_ctr(wd['click'],wd['reach'])
                        for name, y_, p_, wv, is_ctr, y_c, p_c, w_c in [
                            ('预计触达',  yd['reach_plan'], pd_['reach_plan'], wd['reach_plan'], False, None, None, None),
                            ('触达成功',  yd['reach'],       pd_['reach'],       wd['reach'],       False, None, None, None),
                            ('点击人次',  yd['click'],       pd_['click'],       wd['click'],       False, None, None, None),
                            ('点击后下单', yd['order_click'], pd_['order_click'], wd['order_click'], False, None, None, None),
                            ('订单GC',    yd['gc'],           pd_['gc'],          wd['gc'],          False, None, None, None),
                            ('订单Sales', yd['sales'],       pd_['sales'],       wd['sales'],       False, None, None, None),
                            ('CTR',       None,              None,               None,              True,  y_ctr, p_ctr, w_ctr),
                        ]:
                            if is_ctr:
                                typ_ = 'ctr'
                                y_disp, p_disp, wv_disp = y_c, p_c, w_c
                                vp = pp(y_c, p_c) if y_c != '--' and p_c != '--' else '--'
                                vw = pp(y_c, w_c) if y_c != '--' and w_c != '--' else '--'
                                c1 = ccls(y_c, p_c) if y_c != '--' and p_c != '--' else ''
                                c2 = ccls(y_c, w_c) if y_c != '--' and w_c != '--' else ''
                            else:
                                typ_ = 'num'
                                y_disp, p_disp, wv_disp = y_, p_, wv
                                vp = chg(y_, p_)
                                vw = chg(y_, wv)
                                c1 = ccls(y_, p_)
                                c2 = ccls(y_, wv)
                            c1_class = 'up' if c1 == 'up' else 'dn' if c1 == 'dn' else ''
                            c2_class = 'up' if c2 == 'up' else 'dn' if c2 == 'dn' else ''
                            row = f'<tr><td>{name}</td><td class="right">{fmt(y_disp,typ_)}</td><td class="right">{fmt(p_disp,typ_)}</td><td class="right {c1_class}">{vp}</td><td class="right">{fmt(wv_disp,typ_)}</td><td class="right {c2_class}">{vw}</td></tr>\n'
                            s4_html += row

                def s4_owner_reach(owner, key):
                    total = 0
                    for pt in ['aarr','normal']:
                        total += s4_owner_totals(pt, owner, key)['reach']
                    return total

                owner_order_rev = {o: -i for i, o in enumerate(OWNER_ORDER)}
                s4_chart_owners = sorted(
                    [o for o in OWNER_ORDER if s4_owner_reach(o, 'y') > 0],
                    key=lambda o: owner_order_rev.get(o, 0)
                )
                s4_chart_y = [s4_owner_reach(o, 'y') for o in s4_chart_owners]
                s4_chart_w = [round(s4_owner_reach(o, 'w')) for o in s4_chart_owners]
                s4_chart_owners_js = json.dumps(s4_chart_owners, ensure_ascii=False)
                s4_chart_y_js  = json.dumps(s4_chart_y, ensure_ascii=False)
                s4_chart_w_js  = json.dumps(s4_chart_w, ensure_ascii=False)

            html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>Push 日报 {date_y_label}</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:Arial,sans-serif; background:#f5f6fa; color:#222; font-size:13px; }}
.wrap {{ max-width:1200px; margin:0 auto; padding:16px; }}
.header {{ background:#DA291C; color:#fff; padding:14px 20px; border-radius:6px; display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }}
.header h1 {{ font-size:18px; font-weight:bold; }}
.header .sub {{ font-size:12px; opacity:0.9; }}
.header .badge {{ background:#FFBC0D; color:#000; font-size:11px; font-weight:bold; padding:3px 8px; border-radius:3px; }}
.card {{ background:#fff; border-radius:6px; padding:16px 20px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }}
.card-title {{ font-size:14px; font-weight:bold; color:#DA291C; margin-bottom:12px; padding-bottom:8px; border-bottom:2px solid #FFBC0D; }}
table {{ width:100%; border-collapse:collapse; margin-bottom:4px; table-layout:fixed; }}
th {{ background:#f0f0f0; padding:5px 8px; text-align:left; font-size:11px; color:#555; white-space:nowrap; }}
td {{ padding:5px 8px; border-bottom:1px solid #f5f5f5; font-size:12px; overflow:hidden; text-overflow:ellipsis; }}
.metric-name {{ font-weight:bold; white-space:nowrap; }}
th.right, td.right {{ text-align:right; }}
td.up {{ color:#DA291C; }}
td.dn {{ color:#00A04A; }}
tr.sub-header td {{ background:#fafafa; font-weight:bold; font-size:11px; color:#DA291C; padding:4px 8px; }}
.chart-row {{ display:flex; gap:12px; flex-wrap:wrap; }}
.chart-box {{ flex:1; min-width:300px; }}
.plot {{ height:320px; }}
</style>
</head>
<body>
<div class="wrap">
<div class="header">
  <div>
    <h1>麦当劳 Push 日报</h1>
    <div class="sub">上周：{date_w_start} ~ {date_w_end}　｜　昨日：{date_y_label}</div>
  </div>
  <div class="badge">日报 · {date_y_label}</div>
</div>

<div class="card">
  <div class="card-title">1. 整体 KPI</div>
  <div id="chart-s1" class="plot"></div>
  <table style="margin-top:12px;">
    <thead><tr><th style="width:110px">指标</th><th class="right">{date_y_label}</th><th class="right">{date_p_label}</th><th class="right">昨日vs前日</th><th class="right">上周日均</th><th class="right">昨日vs上周日均</th></tr></thead>
    <tbody>{s1_rows}</tbody>
  </table>
</div>

<div class="card">
  <div class="card-title">2. 渠道明细</div>
  <div id="chart-s2" class="plot"></div>
  <table style="margin-top:12px;">
    <thead><tr><th style="width:90px">渠道</th><th class="right">{date_y_label}</th><th class="right">{date_p_label}</th><th class="right">昨日vs前日</th><th class="right">上周日均</th><th class="right">昨日vs上周日均</th></tr></thead>
    <tbody>{s2_rows}</tbody>
  </table>
</div>

<div class="card">
  <div class="card-title">3. 渠道 × 计划类型（AARR / Normal）</div>
  <div class="chart-row">
    <div class="chart-box"><div id="chart-s3a" class="plot"></div></div>
    <div class="chart-box"><div id="chart-s3b" class="plot"></div></div>
  </div>
  <table style="margin-top:12px;">
    <thead><tr><th style="width:140px"></th><th class="right">{date_y_label}</th><th class="right">{date_p_label}</th><th class="right">昨日vs前日</th><th class="right">上周日均</th><th class="right">昨日vs上周日均</th></tr></thead>
    <tbody>{s3_html}</tbody>
  </table>
</div>

<div class="card">
  <div class="card-title">4. 按计划类型 × 预算 Owner</div>
  <div id="chart-s4" class="plot"></div>
  <table>
    <thead><tr><th style="width:140px"></th><th class="right">{date_y_label}</th><th class="right">{date_p_label}</th><th class="right">昨日vs前日</th><th class="right">上周日均</th><th class="right">昨日vs上周日均</th></tr></thead>
    <tbody>{s4_html}</tbody>
  </table>
</div>
</div>

<script>
// S1 combo
(function() {{
  const x = {x_dates_js};
  Plotly.newPlot('chart-s1', [
    {{ x, y: {s1_reach_js}, type: 'bar', name: '触达成功', marker: {{ color: '#DA291C', opacity: 0.85 }}, yaxis: 'y', hovertemplate: '%{{y:.0f}}<extra></extra>' }},
    {{ x, y: {s1_ctr_js}, type: 'scatter', mode: 'lines+markers', name: 'CTR', line: {{ color: '#FFC72C', width: 2.5 }}, marker: {{ color: '#FFC72C', size: 6 }}, yaxis: 'y2', hovertemplate: '%{{y:.2f}}<extra></extra>' }}
  ], {{
    title: {{ text: '近14天触达成功 & CTR趋势', font: {{ size: 13, color: '#DA291C' }}, x: 0.5 }},
    yaxis: {{ title: '触达成功', titlefont: {{ color: '#DA291C', size: 11 }}, tickfont: {{ size: 10 }}, gridcolor: '#f0f0f0', rangemode: 'tozero' }},
    yaxis2: {{ title: 'CTR', titlefont: {{ color: '#FFC72C', size: 11 }}, tickfont: {{ color: '#FFC72C', size: 10 }}, tickformat: '.2f', overlaying: 'y', side: 'right', gridcolor: 'transparent', rangemode: 'tozero' }},
    xaxis: {{ tickfont: {{ size: 10 }}, gridcolor: '#f0f0f0', tickangle: -30 }},
    legend: {{ orientation: 'h', y: -0.22, font: {{ size: 11 }} }},
    margin: {{ b: 60, l: 60, r: 60, t: 40 }}, plot_bgcolor: '#fff', height: 320
  }}, {{ responsive: true }});
}})();

// S2: 渠道折线
(function() {{
  const xLabels = {x_dates_js};
  const chNames = {ch_names_js};
  const chColors = {ch_colors_js};
  const rawData = {y_data_js};
  const traces = Object.keys(rawData).map(ch => ({{
    x: xLabels,
    y: rawData[ch].map(d => (d["aarr"]||{{"reach":0}})["reach"] + (d["normal"]||{{"reach":0}})["reach"]),
    type: 'scatter', mode: 'lines+markers', name: chNames[ch],
    line: {{ color: chColors[ch], width: 2 }}, marker: {{ size: 5 }},
    hovertemplate: '%{{y:.0f}}<extra></extra>'
  }}));
  Plotly.newPlot('chart-s2', traces, {{
    title: {{ text: '近14天各渠道触达成功', font: {{ size: 13, color: '#DA291C' }}, x: 0.5 }},
    yaxis: {{ title: '触达成功', titlefont: {{ size: 11 }}, tickfont: {{ size: 10 }}, gridcolor: '#f0f0f0', rangemode: 'tozero' }},
    xaxis: {{ tickfont: {{ size: 10 }}, gridcolor: '#f0f0f0', tickangle: -30 }},
    legend: {{ orientation: 'h', y: -0.2, font: {{ size: 11 }} }},
    margin: {{ b: 60, l: 60, r: 20, t: 40 }}, plot_bgcolor: '#fff', height: 320
  }}, {{ responsive: true }});
}})();

// S3-a
(function() {{
  const x = {x_dates_js};
  Plotly.newPlot('chart-s3a', [
    {{ x, y: {reach_aarr_js}, type: 'scatter', mode: 'lines+markers', name: 'AARR', line: {{ color: '#DA291C', width: 2 }}, marker: {{ size: 5 }}, hovertemplate: '%{{y:.0f}}<extra></extra>' }},
    {{ x, y: {reach_normal_js}, type: 'scatter', mode: 'lines+markers', name: 'Normal', line: {{ color: '#46B5D8', width: 2 }}, marker: {{ size: 5 }}, hovertemplate: '%{{y:.0f}}<extra></extra>' }}
  ], {{
    title: {{ text: 'AARR vs Normal 触达成功', font: {{ size: 13, color: '#DA291C' }}, x: 0.5 }},
    yaxis: {{ title: '触达成功', titlefont: {{ size: 11 }}, tickfont: {{ size: 10 }}, gridcolor: '#f0f0f0', rangemode: 'tozero' }},
    xaxis: {{ tickfont: {{ size: 10 }}, gridcolor: '#f0f0f0', tickangle: -30 }},
    legend: {{ orientation: 'h', y: -0.2, font: {{ size: 11 }} }},
    margin: {{ b: 60, l: 60, r: 20, t: 40 }}, plot_bgcolor: '#fff', height: 320
  }}, {{ responsive: true }});
}})();

// S3-b
(function() {{
  const x = {x_dates_js};
  const chNames = {ch_names_js};
  const chColors = {ch_colors_js};
  const raw = {plan_cnt_js};
  const traces = Object.keys(raw).map(ch => ({{
    x, y: raw[ch], type: 'scatter', mode: 'lines+markers', name: chNames[ch],
    line: {{ color: chColors[ch], width: 2 }}, marker: {{ size: 5 }},
    hovertemplate: '%{{y:.0f}}<extra></extra>'
  }}));
  Plotly.newPlot('chart-s3b', traces, {{
    title: {{ text: '各渠道 Plan 个数', font: {{ size: 13, color: '#DA291C' }}, x: 0.5 }},
    yaxis: {{ title: 'Plan 个数', titlefont: {{ size: 11 }}, tickfont: {{ size: 10 }}, gridcolor: '#f0f0f0', rangemode: 'tozero', dtick: 10 }},
    xaxis: {{ tickfont: {{ size: 10 }}, gridcolor: '#f0f0f0', tickangle: -30 }},
    legend: {{ orientation: 'h', y: -0.2, font: {{ size: 11 }} }},
    margin: {{ b: 60, l: 60, r: 20, t: 40 }}, plot_bgcolor: '#fff', height: 320
  }}, {{ responsive: true }});
}})();

// ---- S4: 各BU昨日触达成功 vs 上周日均横向条形图 ----
(function() {{
  const owners = {s4_chart_owners_js};
  const yData = {s4_chart_y_js};
  const wData = {s4_chart_w_js};
  Plotly.newPlot('chart-s4', [
    {{
      y: owners, x: yData,
      type: 'bar', orientation: 'h', name: '{date_y_label}',
      marker: {{ color: '#DA291C', opacity: 0.9 }},
      hovertemplate: '%{{y}}<br>昨日触达成功: %{{x:.0f}}<extra></extra>'
    }},
    {{
      y: owners, x: wData,
      type: 'bar', orientation: 'h', name: '上周日均',
      marker: {{ color: '#FFC72C', opacity: 0.75 }},
      hovertemplate: '%{{y}}<br>上周日均: %{{x:.0f}}<extra></extra>'
    }}
  ], {{
    title: {{ text: '各BU触达成功对比（昨日 vs 上周日均）', font: {{ size: 13, color: '#DA291C' }}, x: 0.5 }},
    xaxis: {{ title: '触达成功', titlefont: {{ size: 11 }}, tickfont: {{ size: 10 }}, gridcolor: '#f0f0f0', rangemode: 'tozero' }},
    yaxis: {{ title: '', tickfont: {{ size: 11 }}, gridcolor: 'transparent' }},
    legend: {{ orientation: 'h', y: -0.18, font: {{ size: 11 }} }},
    margin: {{ b: 50, l: 90, r: 20, t: 40 }}, plot_bgcolor: '#fff', height: Math.max(280, owners.length * 32 + 60), barmode: 'group'
  }}, {{ responsive: true }});
}})();
</script>
</body>
</html>"""

            # 内嵌预览
            st.components.v1.html(html, height=2400, scrolling=True)

            # 下载按钮
            date_str = DATE_Y.replace('/', '')
            st.download_button(
                "📥 下载 HTML 日报",
                data=html.encode('utf-8'),
                file_name=f"mcd_report_{date_str}.html",
                mime="text/html",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"❌ 生成失败：{e}")
