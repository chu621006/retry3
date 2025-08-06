import streamlit as st
import pandas as pd
import pdfplumber
import re

def normalize(text):
    return re.sub(r"\s+", " ", text or "").strip()

def process_pdf_file(uploaded_file):
    """
    1) 用 pdfplumber.extract_text 拿到全文；
    2) 按行拆分，用 buffer 把“跨行断开的课程名”粘回到同一行；
    3) 再用正则提取所有：學年度、學期、課程名稱、學分、GPA；
    4) 产出一个 DataFrame，交给后端计算学分。
    """
    try:
        full_text = ""
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                full_text += page.extract_text() + "\n"

        # 先拆行
        raw_lines = [normalize(l) for l in full_text.splitlines() if normalize(l)]
        merged = []
        buf = ""
        # 如果一行末尾没学分＋GPA，就先存 buffer
        pattern_end = re.compile(r".+\s+\d+(?:\.\d+)?\s+[A-F][+\-]?$")
        for line in raw_lines:
            if buf:
                line = buf + " " + line
                buf = ""
            if not pattern_end.match(line):
                buf = line
            else:
                merged.append(line)
        # 万一最后还有 buffer，直接丢掉或 append?
        # if buf: merged.append(buf)

        # 然后对每一行，用正则提取：年、期、名、学分、GPA
        entries = []
        pattern = re.compile(
            r"(\d{3,4})\s*"                 # 學年度
            r"(上|下|春|夏|秋|冬)\s+"         # 學期
            r"(.+?)\s+"                      # 科目名稱（最短匹配）
            r"(\d+(?:\.\d+)?)\s+"            # 學分
            r"([A-F][+\-]?|通過|抵免)$"      # GPA 或「通過」字样
        )
        for ln in merged:
            m = pattern.match(ln)
            if m:
                y, sem, subj, cr, gpa = m.groups()
                entries.append({
                    "學年度": y,
                    "學期": sem,
                    "科目名稱": normalize(subj),
                    "學分": float(cr),
                    "GPA": gpa,
                })

        if not entries:
            st.warning("全文行级解析也未找到任何课程，请检查 PDF 是否是图档或扫描件。")
            return []

        df = pd.DataFrame(entries)
        st.success(f"共解析到 {len(df)} 门课程（行级正则方式）")
        return [df]

    except Exception as e:
        st.error(f"纯文本解析出错: {e}")
        return []
