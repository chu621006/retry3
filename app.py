import streamlit as st
import pandas as pd
import sys
from utils.pdf_processing import process_pdf_file
from utils.grade_analysis import calculate_total_credits
import utils.grade_analysis

print("【DEBUG】sys.path:", sys.path)
print("【DEBUG】utils.grade_analysis module path:", utils.grade_analysis.__file__)

def main():
    st.set_page_config(page_title="PDF 成績單學分計算工具", layout="wide")
    st.title("📄 PDF 成績單學分計算工具")

    st.write("請上傳您的 PDF 成績單檔案，工具將嘗試提取其中的表格數據並計算總學分。")
    st.write("您也可以輸入目標學分，查看還差多少學分。")

    uploaded_file = st.file_uploader("選擇一個 PDF 檔案", type="pdf")

    if uploaded_file is not None:
        st.success(f"已上傳檔案: **{uploaded_file.name}**")
        with st.spinner("正在處理 PDF，請稍候..."):
            extracted_dfs = process_pdf_file(uploaded_file)

        if extracted_dfs:
            try:
                print("【DEBUG】呼叫 calculate_total_credits 前")
                total_credits, calculated_courses, failed_courses = calculate_total_credits(extracted_dfs)
                print("【DEBUG】呼叫 calculate_total_credits 後")
            except Exception as e:
                st.error(f"學分計算階段出現錯誤: {e}")
                st.stop()

            st.markdown("---")
            st.markdown("## ✅ 查詢結果")
            st.markdown(
                f"目前總學分: <span style='color:green; font-size: 24px;'>**{total_credits:.2f}**</span>",
                unsafe_allow_html=True,
            )

            target_credits = st.number_input(
                "輸入您的目標學分 (例如：128)",
                min_value=0.0,
                value=128.0,
                step=1.0,
                help="您可以設定一個畢業學分目標，工具會幫您計算還差多少學分。",
            )

            credit_difference = target_credits - total_credits
            if credit_difference > 0:
                st.write(
                    f"距離畢業所需學分 (共{target_credits:.0f}學分) **{credit_difference:.2f}**"
                )
            elif credit_difference < 0:
                st.write(
                    f"已超越畢業學分 (共{target_credits:.0f}學分) **{abs(credit_difference):.2f}**"
                )
            else:
                st.write(
                    f"已達到畢業所需學分 (共{target_credits:.0f}學分) **0.00**"
                )

            st.markdown("---")
            st.markdown("### 📚 通過的課程列表")
            if calculated_courses:
                courses_df = pd.DataFrame(calculated_courses)
                display_cols = ["學年度", "學期", "科目名稱", "學分", "GPA"]
                final_display_cols = [col for col in display_cols if col in courses_df.columns]
                st.dataframe(
                    courses_df[final_display_cols], height=300, use_container_width=True
                )
            else:
                st.info("沒有找到可以計算學分的科目。")

            if failed_courses:
                st.markdown("---")
                st.markdown("### ⚠️ 不及格的課程列表")
                failed_df = pd.DataFrame(failed_courses)
                display_failed_cols = [
                    "學年度",
                    "學期",
                    "科目名稱",
                    "學分",
                    "GPA",
                    "來源表格",
                ]
                final_display_failed_cols = [
                    col for col in display_failed_cols if col in failed_df.columns
                ]
                st.dataframe(
                    failed_df[final_display_failed_cols],
                    height=200,
                    use_container_width=True,
                )
                st.info("這些科目因成績不及格 ('D', 'E', 'F' 等) 而未計入總學分。")

            if calculated_courses or failed_courses:
                if calculated_courses:
                    csv_data_passed = pd.DataFrame(calculated_courses).to_csv(
                        index=False, encoding="utf-8-sig"
                    )
                    st.download_button(
                        label="下載通過的科目列表為 CSV",
                        data=csv_data_passed,
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_calculated_courses.csv",
                        mime="text/csv",
                        key="download_passed_btn",
                    )
                if failed_courses:
                    csv_data_failed = pd.DataFrame(failed_courses).to_csv(
                        index=False, encoding="utf-8-sig"
                    )
                    st.download_button(
                        label="下載不及格的科目列表為 CSV",
                        data=csv_data_failed,
                        file_name=f"{uploaded_file.name.replace('.pdf', '')}_failed_courses.csv",
                        mime="text/csv",
                        key="download_failed_btn",
                    )
        else:
            st.warning("未從 PDF 中提取到任何表格數據。請檢查 PDF 內容或嘗試調整 `pdfplumber` 的表格提取設定。")
    else:
        st.info("請上傳 PDF 檔案以開始處理。")

if __name__ == "__main__":
    main()
