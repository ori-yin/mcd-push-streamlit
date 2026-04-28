# -*- coding: utf-8 -*-
"""
data_parser.py - 麦当劳 Push 日报数据解析模块
支持 Streamlit 上传和本地 CSV 两种模式
"""
import csv, io
from datetime import datetime, timedelta

# 字段名映射
COLS = {
    'date': 'send_date',
    'channel': '渠道',
    'ptype': '计划类型',
    'plan_id': 'Plan ID',
    'plan_name': 'Plan Name',
    'owner': '预算owner',
    'coupon': '是否用券',
    'reach_plan': '预计触达',
    'reach': '触达成功',
    'click': '点击人次',
    'order_click': '点击后下单人次',
    'gc': '订单GC',
    'sales': '订单Sales',
}


def parse_csv(file_or_path):
    """解析 CSV，返回 (rows_raw, plan_cnt_all, owner_agg, all_dates)

    rows_raw:    date → channel → ptype → metrics
    plan_cnt_all: date → channel → set(plan_id)
    owner_agg:   date → ptype → owner → metrics
    all_dates:   sorted list of dates
    """
    rows_raw    = {}
    plan_cnt_all = {}
    owner_agg   = {}

    # 支持文件对象或路径
    if hasattr(file_or_path, 'read'):
        pos = file_or_path.tell() if hasattr(file_or_path, 'tell') else 0
        raw = file_or_path.read()
        text = raw.decode('utf-8') if isinstance(raw, bytes) else raw
        if hasattr(file_or_path, 'seek'):
            file_or_path.seek(pos)
        f = io.StringIO(text)
    else:
        f = open(file_or_path, encoding='utf-8')

    reader = csv.DictReader(f)

    for row in reader:
        d   = row.get(COLS['date'], '').strip()
        ch  = row.get(COLS['channel'], '?').strip()
        pt  = row.get(COLS['ptype'], 'normal').strip().lower()
        pid = row.get(COLS['plan_id'], '').strip()
        own = row.get(COLS['owner'], '').strip() or '未知'
        if not d or d == COLS['date']:
            continue
        try:
            c  = float(row.get(COLS['click'], 0) or 0)
            r  = float(row.get(COLS['reach'], 0) or 0)
            g  = float(row.get(COLS['gc'], 0) or 0)
            s  = float(row.get(COLS['sales'], 0) or 0)
            oc = float(row.get(COLS['order_click'], 0) or 0)
            rp = float(row.get(COLS['reach_plan'], 0) or 0)
        except:
            continue

        # 标准化日期：去前导零
        parts = d.split()[0].split('/')
        d = f"{parts[0]}/{int(parts[1])}/{int(parts[2])}"

        rows_raw.setdefault(d, {}).setdefault(ch, {}).setdefault(pt, {
            'click':0,'reach':0,'gc':0,'sales':0,'order_click':0,'reach_plan':0
        })
        for k, v in [('click',c),('reach',r),('gc',g),('sales',s),('order_click',oc),('reach_plan',rp)]:
            rows_raw[d][ch][pt][k] += v
        plan_cnt_all.setdefault(d, {}).setdefault(ch, set()).add(pid)

        # owner 聚合（S4 数据源）
        owner_agg.setdefault(d, {}).setdefault(pt, {}).setdefault(own, {
            'click':0,'reach':0,'gc':0,'sales':0,'order_click':0,'reach_plan':0
        })
        for k, v in [('click',c),('reach',r),('gc',g),('sales',s),('order_click',oc),('reach_plan',rp)]:
            owner_agg[d][pt][own][k] += v

    f.close()

    def _key(d):
        p = d.split('/')
        return (int(p[1]), int(p[2]))
    all_dates = sorted(rows_raw.keys(), key=_key)
    return rows_raw, plan_cnt_all, owner_agg, all_dates


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


def calc_s4_data(owner_agg, DATE_Y, DATE_P, DATE_W):
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
    for ptype in ['aarr', 'normal']:
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
