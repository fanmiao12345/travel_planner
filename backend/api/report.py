"""旅行报告生成器"""

from __future__ import annotations
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape
import re
import zipfile


def generate_report_html(state: dict) -> str:
    """从 final_state 生成精美的 HTML 旅行报告。"""

    # 提取数据
    destination = state.get("destination", "未指定")
    origin = state.get("origin", "未指定")
    dates = state.get("dates", {})
    start_date = dates.get("start", "未定")
    end_date = dates.get("end", "未定")
    days = dates.get("days", "?")
    budget = state.get("budget", "未指定")
    people = state.get("people_count", 1)
    style = state.get("travel_style", "经典")

    # 各维度内容（dict 字段取 content，list 字段 join）
    def _content(val):
        if isinstance(val, dict):
            return val.get("content", str(val))
        if isinstance(val, list):
            return "\n\n".join(str(v) for v in val)
        return str(val) if val else ""

    route = _content(state.get("route_plan"))
    weather = _content(state.get("weather_info"))
    transport = _content(state.get("transport_options"))
    accommodation = _content(state.get("accommodation_options"))
    food = _content(state.get("food_recommendations"))
    budget_detail = _content(state.get("budget_breakdown"))
    final_plan = _content(state.get("final_plan"))

    # 证据来源
    evidence = state.get("evidence_sources", []) or []
    evidence_rows = ""
    for e in evidence:
        if isinstance(e, dict):
            evidence_rows += f"""
            <tr>
                <td>{e.get('id', '')}</td>
                <td>{e.get('title', e.get('source', ''))}</td>
                <td>{e.get('source_type', '')}</td>
                <td><a href="{e.get('url', '#')}" target="_blank">{e.get('url', '链接')[:40]}</a></td>
            </tr>"""

    # 质量报告
    quality = state.get("quality_report", {}) or {}
    score = quality.get("score", "N/A")

    # Markdown → 简单 HTML 转换（处理标题、列表、加粗）
    def _md_to_html(text: str) -> str:
        if not text:
            return "<p>暂无数据</p>"
        import re
        lines = text.split("\n")
        html_lines = []
        in_list = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                continue
            # 标题
            if stripped.startswith("### "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h4>{stripped[4:]}</h4>")
            elif stripped.startswith("## "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h3>{stripped[3:]}</h3>")
            elif stripped.startswith("# "):
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                html_lines.append(f"<h2>{stripped[2:]}</h2>")
            elif stripped.startswith("- ") or stripped.startswith("* "):
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                item = stripped[2:]
                item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
                html_lines.append(f"<li>{item}</li>")
            elif re.match(r'^\d+\.\s', stripped):
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                item = re.sub(r'^\d+\.\s', '', stripped)
                item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
                html_lines.append(f"<li>{item}</li>")
            else:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                stripped = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
                html_lines.append(f"<p>{stripped}</p>")
        if in_list:
            html_lines.append("</ul>")
        return "\n".join(html_lines)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>旅行计划报告 — {destination}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
    background: #0f172a; color: #e2e8f0; line-height: 1.7;
  }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 40px 24px; }}
  .header {{
    text-align: center; padding: 48px 0 32px;
    border-bottom: 2px solid rgba(45, 212, 191, 0.3);
  }}
  .header h1 {{
    font-size: 2rem; color: #5eead4;
    background: linear-gradient(135deg, #5eead4, #38bdf8);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }}
  .header .meta {{ color: #94a3b8; margin-top: 8px; font-size: 0.9rem; }}
  .info-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px; margin: 32px 0;
  }}
  .info-card {{
    background: #1e293b; border-radius: 12px; padding: 16px;
    border: 1px solid #334155;
  }}
  .info-card .label {{ font-size: 0.8rem; color: #64748b; text-transform: uppercase; }}
  .info-card .value {{ font-size: 1.2rem; color: #f1f5f9; margin-top: 4px; }}
  .section {{
    background: #1e293b; border-radius: 16px; padding: 28px;
    margin: 24px 0; border: 1px solid #334155;
  }}
  .section h2 {{
    font-size: 1.3rem; color: #5eead4; margin-bottom: 16px;
    padding-bottom: 8px; border-bottom: 1px solid #334155;
  }}
  .section h3 {{ color: #7dd3fc; margin: 16px 0 8px; }}
  .section h4 {{ color: #94a3b8; margin: 12px 0 6px; }}
  .section p {{ margin: 8px 0; color: #cbd5e1; }}
  .section ul {{ margin: 8px 0 8px 20px; }}
  .section li {{ margin: 4px 0; color: #cbd5e1; }}
  .section strong {{ color: #f1f5f9; }}
  .section a {{ color: #38bdf8; }}
  .score-badge {{
    display: inline-block; background: linear-gradient(135deg, #0d9488, #0891b2);
    color: white; padding: 4px 16px; border-radius: 20px;
    font-weight: bold; font-size: 1.1rem;
  }}
  table {{
    width: 100%; border-collapse: collapse; margin: 12px 0;
  }}
  th, td {{
    padding: 8px 12px; text-align: left; border-bottom: 1px solid #334155;
    font-size: 0.9rem;
  }}
  th {{ color: #94a3b8; font-weight: 600; }}
  td {{ color: #cbd5e1; }}
  .footer {{
    text-align: center; padding: 32px 0; color: #475569;
    font-size: 0.8rem; border-top: 1px solid #1e293b; margin-top: 32px;
  }}
  @media print {{
    body {{ background: #fff; color: #1e293b; }}
    .section {{ border: 1px solid #e2e8f0; }}
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>✈️ 旅行计划报告</h1>
    <div class="meta">{origin} → {destination} | 生成时间：{now}</div>
  </div>

  <div class="info-grid">
    <div class="info-card">
      <div class="label">出发地</div>
      <div class="value">{origin}</div>
    </div>
    <div class="info-card">
      <div class="label">目的地</div>
      <div class="value">{destination}</div>
    </div>
    <div class="info-card">
      <div class="label">日期</div>
      <div class="value">{start_date} ~ {end_date}</div>
    </div>
    <div class="info-card">
      <div class="label">天数</div>
      <div class="value">{days} 天</div>
    </div>
    <div class="info-card">
      <div class="label">预算</div>
      <div class="value">¥{budget}</div>
    </div>
    <div class="info-card">
      <div class="label">人数</div>
      <div class="value">{people} 人</div>
    </div>
    <div class="info-card">
      <div class="label">风格</div>
      <div class="value">{style}</div>
    </div>
    <div class="info-card">
      <div class="label">质量评分</div>
      <div class="value"><span class="score-badge">{score}</span></div>
    </div>
  </div>

  {"" if not final_plan or final_plan == "暂无数据" else f'''
  <div class="section">
    <h2>📋 完整行程方案</h2>
    {_md_to_html(final_plan)}
  </div>
  '''}

  {"" if not route or route == "暂无数据" else f'''
  <div class="section">
    <h2>🗺️ 路线规划</h2>
    {_md_to_html(route)}
  </div>
  '''}

  {"" if not weather or weather == "暂无数据" else f'''
  <div class="section">
    <h2>🌤️ 天气预报</h2>
    {_md_to_html(weather)}
  </div>
  '''}

  {"" if not transport or transport == "暂无数据" else f'''
  <div class="section">
    <h2>🚄 交通方案</h2>
    {_md_to_html(transport)}
  </div>
  '''}

  {"" if not accommodation or accommodation == "暂无数据" else f'''
  <div class="section">
    <h2>🏨 住宿推荐</h2>
    {_md_to_html(accommodation)}
  </div>
  '''}

  {"" if not food or food == "暂无数据" else f'''
  <div class="section">
    <h2>🍜 美食推荐</h2>
    {_md_to_html(food)}
  </div>
  '''}

  {"" if not budget_detail or budget_detail == "暂无数据" else f'''
  <div class="section">
    <h2>💰 预算明细</h2>
    {_md_to_html(budget_detail)}
  </div>
  '''}

  {"" if not evidence_rows else f'''
  <div class="section">
    <h2>📚 数据来源</h2>
    <table>
      <thead><tr><th>编号</th><th>来源</th><th>类型</th><th>链接</th></tr></thead>
      <tbody>{evidence_rows}</tbody>
    </table>
  </div>
  '''}

  <div class="footer">
    由出游计划自动规划多智能体平台生成 | {now}
  </div>
</div>
</body>
</html>"""

    return html


def generate_report_docx(state: dict) -> bytes:
    """从 final_state 生成 Word docx 文档。"""

    destination = state.get("destination", "未指定")
    origin = state.get("origin", "未指定")
    dates = state.get("dates", {}) or {}
    evidence = state.get("evidence_sources", []) or []
    quality = state.get("quality_report", {}) or {}

    def _content(val):
        if isinstance(val, dict):
            return val.get("content", "")
        if isinstance(val, list):
            return "\n\n".join(str(v) for v in val if v)
        return str(val) if val else ""

    def _clean_markdown(text: str) -> list[str]:
        text = str(text or "").replace("\r\n", "\n")
        lines: list[str] = []
        for raw in text.split("\n"):
            line = raw.strip()
            if not line:
                lines.append("")
                continue
            line = re.sub(r"^#{1,6}\s*", "", line)
            line = re.sub(r"^\s*[-*]\s+", "• ", line)
            line = re.sub(r"^\s*\d+\.\s+", lambda m: m.group(0), line)
            line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            line = re.sub(r"`(.+?)`", r"\1", line)
            lines.append(line)
        return lines

    def _p(text: str = "", style: str | None = None) -> str:
        style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        preserve = ' xml:space="preserve"' if text.startswith(" ") or text.endswith(" ") else ""
        return f"<w:p>{style_xml}<w:r><w:t{preserve}>{escape(text)}</w:t></w:r></w:p>"

    paragraphs: list[str] = []
    paragraphs.append(_p("旅行计划报告", "Title"))
    paragraphs.append(_p(f"{origin} → {destination}", "Subtitle"))
    paragraphs.append(_p(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}"))
    paragraphs.append(_p(""))

    meta = [
        f"出发地：{origin}",
        f"目的地：{destination}",
        f"日期：{dates.get('start', '未定')} ~ {dates.get('end', '未定')}",
        f"天数：{dates.get('days', '?')} 天",
        f"预算：¥{state.get('budget', '未指定')}",
        f"人数：{state.get('people_count', 1)} 人",
        f"风格：{state.get('travel_style', '经典')}",
        f"质量评分：{quality.get('score', 'N/A')}",
    ]
    paragraphs.append(_p("基础信息", "Heading1"))
    for item in meta:
        paragraphs.append(_p(item))

    sections = [
        ("完整行程方案", _content(state.get("final_plan"))),
        ("路线规划", _content(state.get("route_plan"))),
        ("天气预报", _content(state.get("weather_info"))),
        ("交通方案", _content(state.get("transport_options"))),
        ("住宿推荐", _content(state.get("accommodation_options"))),
        ("美食推荐", _content(state.get("food_recommendations"))),
        ("预算明细", _content(state.get("budget_breakdown"))),
    ]
    for title, content in sections:
        if not content:
            continue
        paragraphs.append(_p(""))
        paragraphs.append(_p(title, "Heading1"))
        for line in _clean_markdown(content):
            paragraphs.append(_p(line))

    paragraphs.append(_p(""))
    paragraphs.append(_p("数据来源", "Heading1"))
    if evidence:
        for item in evidence:
            if not isinstance(item, dict):
                continue
            source_id = item.get("id", "")
            title = item.get("title") or item.get("category") or "来源"
            source_type = item.get("source_type") or item.get("source") or ""
            url = item.get("url") or ""
            official = "官方/权威来源" if item.get("is_official") else "普通搜索来源，需二次确认"
            paragraphs.append(_p(f"{source_id} {title} | {source_type} | {official}"))
            if url:
                paragraphs.append(_p(f"链接：{url}"))
            if item.get("snippet"):
                paragraphs.append(_p(f"摘要：{item.get('snippet')}"))
    else:
        paragraphs.append(_p("暂无工具返回的可引用来源，所有事实性信息请出行前二次确认。"))

    warnings = quality.get("warnings") or []
    if warnings:
        paragraphs.append(_p(""))
        paragraphs.append(_p("质量检查提醒", "Heading1"))
        for warning in warnings:
            paragraphs.append(_p(f"• {warning}"))

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {"".join(paragraphs)}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
    </w:sectPr>
  </w:body>
</w:document>'''

    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="24"/><w:color w:val="666666"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
</w:styles>'''

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''

    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    doc_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types)
        docx.writestr("_rels/.rels", rels)
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", styles_xml)
        docx.writestr("word/_rels/document.xml.rels", doc_rels)
    return buffer.getvalue()
