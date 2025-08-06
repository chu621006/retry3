# utils/grade_analysis.py

import pandas as pd
import re
from .pdf_processing import normalize_text

def is_passing_gpa(gpa_str):
    gpa = normalize_text(gpa_str).upper()
    failing = {"D", "D-", "E", "F", "X", "不通過", "未通過", "不及格"}
    if not gpa: return False
    if gpa in {"通過","抵免","PASS","EXEMPT"}: return True
    if gpa in failing: return False
    if re.fullmatch(r'[A-C][+\-]?', gpa): return True
    if re.fullmatch(r'\d+(\.\d+)?', gpa):
        try: return float(gpa) >= 60.0
        except: pass
    return False

def parse_credit_and_gpa(text):
    t = normalize_text(text)
    if t.lower() in {"通過","抵免","pass","exempt"}: return 0.0, t
    m = re.match(r'([A-Fa-f][+\-]?)\s*(\d+(\.\d+)?)', t)
    if m: return float(m.group(2)), m.group(1).upper()
    m = re.match(r'(\d+(\.\d+)?)\s*([A-Fa-f][+\-]?)', t)
    if m: return float(m.group(1)), m.group(3).upper()
    m = re.search(r'(\d+(\.\d+)?)', t)
    if m: return float(m.group(1)), ""
    m = re.search(r'([A-Fa-f][+\-]?)', t)
    if m: return 0.0, m.group(1).upper()
    return 0.0, ""

def calculate_total_credits(df_list):
    print("===== DEBUG: 進入 calculate_total_credits =====")
    print(f"DEBUG: 總共收到 {len(df_list)} 個 DataFrame")
    total_credits = 0.0
    calculated_courses = []
    failed_courses = []

    for idx, df in enumerate(df_list):
        print(f"--- DEBUG: 處理第 {idx+1} 個 DataFrame ---")
        print("DEBUG: 列名:", df.columns.tolist())
        print("DEBUG: 前 3 列示例：")
        print(df.head(3))

        # 找關鍵欄位
        cols_norm = {re.sub(r'\s+','',c).lower():c for c in df.columns}
        def find_col(keys):
            for k in keys:
                if k.lower() in cols_norm:
                    return cols_norm[k.lower()]
            return None

        credit_col  = find_col(["學分","credit"])
        subject_col = find_col(["科目名稱","課程名稱","subject"])
        gpa_col     = find_col(["GPA","成績","grade"])
        year_col    = find_col(["學年","year"])
        sem_col     = find_col(["學期","semester"])
        print("DEBUG: 找到欄位 →", 
              f"subject={subject_col}", f"credit={credit_col}", 
              f"gpa={gpa_col}", f"year={year_col}", f"sem={sem_col}")

        if not subject_col or (not credit_col and not gpa_col):
            print("DEBUG: 欄位不足，跳過此 DataFrame")
            continue

        buffer_name = ""
        for ridx, row in df.iterrows():
            data = {c: normalize_text(row[c]) if pd.notna(row[c]) else "" for c in df.columns}
            subj_raw = data.get(subject_col,"")
            cred_txt = data.get(credit_col,"") if credit_col else ""
            gpa_txt  = data.get(gpa_col,"")    if gpa_col else ""

            cred, gpa = parse_credit_and_gpa(cred_txt)
            pc, pg = parse_credit_and_gpa(gpa_txt)
            if pg: gpa = pg
            if pc>0 and cred==0: cred = pc

            print(f"DEBUG Row {ridx}: subj='{subj_raw}' cred_txt='{cred_txt}'→{cred} gpa_txt='{gpa_txt}'→{gpa}")

            # 判斷完整
            complete = (
                cred>0 or is_passing_gpa(gpa)
                or cred_txt.lower() in {"通過","抵免"}
                or gpa_txt.lower() in {"通過","抵免"}
            )

            # 空行
            if all(not data.get(c,"") for c in [subject_col,credit_col,gpa_col] if c):
                buffer_name=""
                continue

            if complete:
                if buffer_name and cred==0:
                    name = f"{buffer_name} {subj_raw}".strip()
                else:
                    name = subj_raw
                print(f"DEBUG 完整課程，最終名稱='{name}'")
                buffer_name=""

                # 學年/學期
                acad=data.get(year_col,""); sem=data.get(sem_col,"")
                record={"學年度":acad,"學期":sem,
                        "科目名稱":name,"學分":cred,"GPA":gpa,"來源表格":idx+1}
                if gpa and not is_passing_gpa(gpa):
                    failed_courses.append(record)
                else:
                    total_credits += cred
                    calculated_courses.append(record)
            else:
                # buffer
                if subj_raw:
                    buffer_name=(buffer_name+" "+subj_raw).strip() if buffer_name else subj_raw
                    print(f"DEBUG buffer 累積='{buffer_name}'")

        if buffer_name:
            import streamlit as st
            st.warning(f"表格{idx+1} 殘留科目名稱「{buffer_name}」")

    print(f"===== DEBUG: exit calculate_total_credits with total_credits={total_credits} =====")
    return total_credits, calculated_courses, failed_courses
