# 麦当劳 App Push 日报生成器

基于 Streamlit 的 Web 应用，上传 CSV 数据自动生成可视化日报。

## 功能

- 📊 自动读取 CSV 中的最新日期作为"昨日"
- 📈 Part 1: 整体 KPI + 14天趋势图（触达+CTR组合图）
- 📈 Part 2: 渠道明细 + 折线图
- 📈 Part 3: 渠道 × 计划类型（AARR / Normal）
- 📥 一键下载 HTML 文件，微信打开即可

## 字段要求

CSV 文件需包含以下字段：

| 字段名 | 说明 |
|--------|------|
| 发送日期 | 发送日期，格式：2026/4/16 |
| 计划类型 | AARR 或 Normal |
| 渠道 | APP Push / 企微1v1 / 微信小程序订阅消息 / 短信 |
| Plan ID | 计划ID |
| Plan名称 | 计划名称 |
| 预算owner | 预算归属 |
| 是否用券 | 是否用券 |
| 预计触达 | 预计触达人数 |
| 触达成功 | 实际触达人数 |
| 点击人次 | 点击次数 |
| 点击后下单人次 | 点击后下单人数 |
| 订单GC | 订单成交额 |
| 订单Sales | 订单销售额 |

## 部署方式

### 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

### 部署到 Streamlit Cloud（免费）

1. 将代码上传到 GitHub 仓库
2. 打开 [share.streamlit.io](https://share.streamlit.io)
3. 用 GitHub 登录 → 选仓库 → 选分支 → 填 `app.py`
4. 点击 Deploy → 完成

部署后会得到一个链接如 `https://your-app.streamlit.app`，分享给同事即可使用。

## 项目结构

```
mcd_push_streamlit/
├── app.py              # Streamlit Web 应用
├── data_parser.py      # 数据解析模块
├── requirements.txt    # Python 依赖
└── README.md           # 本文件
```
