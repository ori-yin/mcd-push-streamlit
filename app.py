# -*- coding: utf-8 -*-

"""

app.py - 麦当劳 Push 日报生成器 (Streamlit Web App)

使用方法：streamlit run app.py

"""

import streamlit as st

import json, csv, io
import pandas as pd
from io import BytesIO
# 字段名映射
# ══ 列名智能推断（不再写死中文字段名）═════════
# 从 CSV 实际列名动态推断每个字段用途
def _infer_cols(columns):
    """根据列名关键词推断字段映射"""
    col_lower = {str(c).strip(): str(c).strip() for c in columns}
    guess = {}
    
    # 日期列
    for kw in ['发送日期', 'send_date', '日期', 'date']:
        for c, cl in col_lower.items():
            if kw in cl:
                guess['date'] = c; break
        if 'date' in guess: break
    
    # 渠道
    for kw in ['渠道', 'channel']:
        for c, cl in col_lower.items():
            if kw in cl:
                guess['channel'] = c; break
        if 'channel' in guess: break
    
    # 计划类型
    for kw in ['计划类型', 'ptype', 'type']:
        for c, cl in col_lower.items():
            if kw in cl:
                guess['ptype'] = c; break
        if 'ptype' in guess: break
    
    # Plan ID
    for kw in ['plan_id', 'plan id', 'planid']:
        for c, cl in col_lower.items():
            if kw in cl:
                guess['plan_id'] = c; break
        if 'plan_id' in guess: break
    
    # Owner
    for kw in ['owner', '预算owner', '预算', '负责人']:
        for c, cl in col_lower.items():
            if kw in cl:
                guess['owner'] = c; break
        if 'owner' in guess: break
    
    # 点击
    for kw in ['点击人次', 'click']:
        for c, cl in col_lower.items():
            if kw in cl:
                guess['click'] = c; break
        if 'click' in guess: break
    
    # 触达成功
    for kw in ['触达成功', 'reach', '成功触达']:
        for c, cl in col_lower.items():
            if kw in cl:
                guess['reach'] = c; break
        if 'reach' in guess: break
    
    # 订单GC
    for kw in ['订单gc', 'gc', 'order_gc']:
        for c, cl in col_lower.items():
            if kw in cl:
                guess['gc'] = c; break
        if 'gc' in guess: break
    
    # 订单Sales
    for kw in ['订单sales', 'sales', 'order_sales']:
        for c, cl in col_lower.items():
            if kw in cl:
                guess['sales'] = c; break
        if 'sales' in guess: break
    
    # 点击后下单
    for kw in ['点击后下单人次', 'order_click', '下单点击']:
        for c, cl in col_lower.items():
            if kw in cl:
                guess['order_click'] = c; break
        if 'order_click' in guess: break
    
    # 预计触达 / reach_plan
    for kw in ['预计触达', 'reach_plan', 'reachplan', '预估触达']:
        for c, cl in col_lower.items():
            if kw in cl:
                guess['reach_plan'] = c; break
        if 'reach_plan' in guess: break
    
    return guess




def parse_csv(file_or_path):
    """解析 CSV，返回 (rows_raw, plan_cnt_all, owner_agg, all_dates, col_map, raw_df, ch_list, ptypes_seen)
    """
    rows_raw     = {}
    plan_cnt_all = {}
    owner_agg    = {}

    encodings = ['utf-8', 'gbk', 'gb2312', 'latin1']
    df = None

    if hasattr(file_or_path, 'read'):
        bytes_data = file_or_path.read()
        for enc in encodings:
            try:
                df = pd.read_csv(BytesIO(bytes_data), encoding=enc, on_bad_lines='skip')
                break
            except Exception:
                continue
        if df is None:
            raise ValueError("无法读取 CSV 文件，请检查文件格式")
    else:
        for enc in encodings:
            try:
                df = pd.read_csv(file_or_path, encoding=enc, on_bad_lines='skip')
                break
            except UnicodeDecodeError:
                continue
        else:
            df = pd.read_csv(file_or_path, encoding='utf-8', on_bad_lines='skip')

    # 动态推断列名
    col_map = _infer_cols(df.columns.tolist())
    date_col = col_map.get('date', '')
    if not date_col:
        raise ValueError(f"找不到日期列。实际列名：{list(df.columns)}")

    def g(col_key, default=0):
        cn = col_map.get(col_key, '')
        if not cn or cn not in df.columns:
            return default
        return cn  # 返回列名，让调用方用 row.get()

    channels_seen = set()
    ptypes_seen   = set()
    owners_seen   = set()

    for _, row in df.iterrows():
        d = str(row[date_col]).strip() if pd.notna(row[date_col]) else ''
        if not d or d == str(date_col):
            continue

        # 规范化日期
        raw_d = d.split()[0].replace('-', '/')
        parts = raw_d.split('/')
        if len(parts) != 3:
            continue
        d_fmt = f"{parts[0]}/{int(parts[1])}/{int(parts[2])}"

        ch  = str(row.get(g('channel', ''), '?')).strip()
        pt  = str(row.get(g('ptype', ''), 'normal')).strip().lower() or 'normal'
        pid = str(row.get(g('plan_id', ''), '')).strip()
        own = str(row.get(g('owner', ''), '')).strip() or '未知'

        channels_seen.add(ch)
        ptypes_seen.add(pt)
        owners_seen.add(own)

        def m(col_key, default=0):
            cn = col_map.get(col_key, '')
            if not cn or cn not in df.columns:
                return default
            val = row.get(cn, default)
            try:
                return float(val) if pd.notna(val) else default
            except (ValueError, TypeError):
                return default

        c  = m('click', 0)
        r  = m('reach', 0)
        gv = m('gc', 0)
        s  = m('sales', 0)
        oc = m('order_click', 0)
        rp = m('reach_plan', 0)

        rows_raw.setdefault(d_fmt, {}).setdefault(ch, {}).setdefault(pt, {
            'click':0,'reach':0,'gc':0,'sales':0,'order_click':0,'reach_plan':0
        })
        for k, v in [('click',c),('reach',r),('gc',gv),('sales',s),('order_click',oc),('reach_plan',rp)]:
            rows_raw[d_fmt][ch][pt][k] += v
        plan_cnt_all.setdefault(d_fmt, {}).setdefault(ch, set()).add(pid)

        owner_agg.setdefault(d_fmt, {}).setdefault(pt, {}).setdefault(own, {
            'click':0,'reach':0,'gc':0,'sales':0,'order_click':0,'reach_plan':0
        })
        for k, v in [('click',c),('reach',r),('gc',gv),('sales',s),('order_click',oc),('reach_plan',rp)]:
            owner_agg[d_fmt][pt][own][k] += v

    def _key(d):
        p = d.split('/')
        return (int(p[1]), int(p[2]))
    all_dates = sorted(rows_raw.keys(), key=_key)
    ch_list = sorted(channels_seen)

    return rows_raw, plan_cnt_all, owner_agg, all_dates, col_map, df, ch_list, ptypes_seen


def calc_date_range(all_dates):
    """从数据中自动计算昨日/前日/周均日期范围
    
    注意：返回的日期格式必须与 parse_csv 中 rows_raw 的 key 一致（去前导零）
    """
    if not all_dates:
        return None, None, []
    latest = all_dates[-1]
    parts = latest.split('/')
    latest_dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
    prev_dt = latest_dt - timedelta(days=1)
    DATE_Y = latest  # 最新日期 = 昨日（已是去前导零格式）
    # 前日：去前导零保持一致
    DATE_P = f"{prev_dt.year}/{prev_dt.month}/{prev_dt.day}"
    # 上周7天：必须去前导零，与 rows_raw key 匹配！
    DATE_W = []
    for i in range(1, 8):  # 1~7天前
        d = latest_dt - timedelta(days=i)
        DATE_W.append(f"{d.year}/{d.month}/{d.day}")
    return DATE_Y, DATE_P, DATE_W


def totals_all(rows_raw, dates):
    t = {'click':0,'reach':0,'gc':0,'sales':0,'order_click':0,'reach_plan':0}
    for d in dates:
        if d not in rows_raw:
            continue
        for ch, pts in rows_raw[d].items():
            for pt, vals in pts.items():
                for k in t:
                    t[k] += vals.get(k, 0)
    return t


def ch_totals(rows_raw, ch, dates):
    t = {'click':0,'reach':0,'gc':0,'sales':0,'order_click':0,'reach_plan':0}
    for d in dates:
        if d not in rows_raw or ch not in rows_raw[d]:
            continue
        for pt, vals in rows_raw[d][ch].items():
            for k in t:
                t[k] += vals.get(k, 0)
    return t


def agg_ch_pt(rows_raw, ch, ptype, dates):
    t = {'click':0,'reach':0,'gc':0,'sales':0,'order_click':0,'reach_plan':0}
    for d in dates:
        if d not in rows_raw or ch not in rows_raw[d]:
            continue
        if ptype not in rows_raw[d][ch]:
            continue
        for k, v in rows_raw[d][ch][ptype].items():
            t[k] += v
    return t


def calc_s4_data(owner_agg, DATE_Y, DATE_P, DATE_W, ptypes_seen=None):
    if ptypes_seen is None: ptypes_seen = {'aarr', 'normal'}
    """计算 S4 按 Owner 数据
    返回: {
        'aarr':  [{owner, reach_y, reach_p, reach_w, ctr_y, ctr_p, ctr_w, ...}, ...],
        'normal': [...]
    }
    """
    METRICS = ['reach', 'click', 'order_click', 'gc', 'sales', 'reach_plan']

    def _sum(dates, ptype, owner):
        t = {k: 0.0 for k in METRICS}
        for d in dates:
            if d not in owner_agg or ptype not in owner_agg[d]:
                continue
            if owner not in owner_agg[d][ptype]:
                continue
            for k in METRICS:
                t[k] += owner_agg[d][ptype][owner].get(k, 0)
        return t

    def _ctr(m):
        return m['click'] / m['reach'] * 100 if m['reach'] else 0

    result = {}
    for ptype in sorted(ptypes_seen or ['aarr', 'normal']):
        owners = set()
        for d, pts in owner_agg.items():
            if ptype in pts:
                owners.update(pts[ptype].keys())

        rows = []
        for owner in sorted(owners):
            yd = _sum([DATE_Y], ptype, owner)
            pd = _sum([DATE_P], ptype, owner)
            wd = _sum(DATE_W, ptype, owner)
            rows.append({
                'owner': owner,
                'reach_plan_y': yd['reach_plan'],
                'reach_plan_p': pd['reach_plan'],
                'reach_plan_w': wd['reach_plan'] / 7,
                'reach_y': yd['reach'],
                'reach_p': pd['reach'],
                'reach_w': wd['reach'] / 7,
                'click_y': yd['click'],
                'click_p': pd['click'],
                'click_w': wd['click'] / 7,
                'order_click_y': yd['order_click'],
                'order_click_p': pd['order_click'],
                'order_click_w': wd['order_click'] / 7,
                'ctr_y': _ctr(yd),
                'ctr_p': _ctr(pd),
                'ctr_w': _ctr(wd),
                'gc_y': yd['gc'],
                'gc_p': pd['gc'],
                'gc_w': wd['gc'] / 7,
                'sales_y': yd['sales'],
                'sales_p': pd['sales'],
                'sales_w': wd['sales'] / 7,
            })
        result[ptype] = rows

    return result

from datetime import datetime, timedelta




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

        help="CSV 字段：send_date, 计划类型, 渠道, Plan ID, 预算owner, 预计触达, 触达成功, 点击人次, 点击后下单人次, 订单GC, 订单Sales"

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

            rows_raw, plan_cnt_all, owner_agg, all_dates, col_map, raw_df, ch_list, ptypes_seen = parse_csv(uploaded)

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



            ch_list = sorted(channels_seen)  # 动态从 CSV 发现

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

            PTYPE_ORDER = sorted(ptypes_seen)  # 动态从 CSV 发现

            PTYPE_LABELS = {pt: pt.upper() for pt in ptypes_seen}



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



            s4_result = calc_s4_data(owner_agg, DATE_Y, DATE_P, DATE_W, ptypes_seen)

            # 按昨日触达量降序排列 owner（动态）
            owner_reach = {}
            for d, pts in owner_agg.items():
                for pt, owners in pts.items():
                    for own, m in owners.items():
                        owner_reach[own] = owner_reach.get(own, 0) + m.get('reach', 0)
            OWNER_ORDER = sorted(owner_reach.keys(), key=lambda o: owner_reach.get(o, 0), reverse=True)
            if not OWNER_ORDER:
                OWNER_ORDER = ['未知']
            PTYPE_S4    = [(pt, pt.upper()) for pt in sorted(ptypes_seen)]

            s4_html = ''
            for pkey, ptype_label in PTYPE_S4:
                rows = s4_result.get(pkey, [])
                owner_order_idx = {o: i for i, o in enumerate(OWNER_ORDER)}
                rows_sorted = sorted(rows, key=lambda r: owner_order_idx.get(r['owner'], 999))
                if not rows_sorted:
                    continue
                s4_html += '<tr class=sub-header><td colspan=6>' + ptype_label + '</td></tr>\n'
                for row in rows_sorted:
                    owner = row['owner']
                    s4_html += '<tr class=sub-header><td colspan=6>' + owner + '</td></tr>\n'
                    for name, y_v, p_v, wv, is_ctr in [
                        ('预计触达',    row['reach_plan_y'],       row['reach_plan_p'],       row['reach_plan_w'],       False),
                        ('触达成功',    row['reach_y'],            row['reach_p'],            row['reach_w'],             False),
                        ('点击人次',    row['click_y'],            row['click_p'],            row['click_w'],             False),
                        ('点击后下单',  row['order_click_y'],      row['order_click_p'],      row['order_click_w'],       False),
                        ('订单GC',      row['gc_y'],               row['gc_p'],               row['gc_w'],                False),
                        ('订单Sales',   row['sales_y'],            row['sales_p'],            row['sales_w'],             False),
                        ('CTR',         row['ctr_y'],              row['ctr_p'],              row['ctr_w'],               True),
                    ]:
                        if is_ctr:
                            typ_ = 'ctr'
                            vp = pp(y_v, p_v) if y_v and p_v else '--'
                            vw = pp(y_v, wv) if y_v and wv else '--'
                            c1 = ccls(y_v, p_v) if y_v and p_v else ''
                            c2 = ccls(y_v, wv) if y_v and wv else ''
                        else:
                            typ_ = 'num'
                            vp = chg(y_v, p_v)
                            vw = chg(y_v, wv)
                            c1 = ccls(y_v, p_v)
                            c2 = ccls(y_v, wv)
                        c1_class = 'up' if c1 == 'up' else 'dn' if c1 == 'dn' else ''
                        c2_class = 'up' if c2 == 'up' else 'dn' if c2 == 'dn' else ''
                        s4_html += '<tr><td>' + name + '</td><td class="right">' + fmt(y_v,typ_) + '</td><td class="right">' + fmt(p_v,typ_) + '</td><td class="right ' + c1_class + '">' + vp + '</td><td class="right">' + fmt(wv,typ_) + '</td><td class="right ' + c2_class + '">' + vw + '</td></tr>\n'

            # S4 图表数据
            def s4_owner_reach(owner, key):
                total = 0.0
                k_map = {'y': 'reach_y', 'p': 'reach_p', 'w': 'reach_w'}
                col = k_map.get(key, '')
                for pkey in ['aarr','normal']:
                    for row in s4_result.get(pkey, []):
                        if row['owner'] == owner:
                            total += row.get(col, 0)
                return total

            s4_chart_owners = [o for o in OWNER_ORDER if s4_owner_reach(o, 'y') > 0]
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

