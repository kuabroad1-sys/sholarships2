import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="장학금 관리 시스템", layout="wide")

st.title("🎓 외국인 장학금 수혜 대상자 산출 시스템")

# 1. 사이드바 - 설정 및 예산 입력
st.sidebar.header("설정")
total_budget_limit = st.sidebar.number_input("전체 예산(원)", value=500000000, step=10000000)

# 2. 파일 업로드
st.subheader("1. 데이터 업로드")
col1, col2 = st.columns(2)
with col1:
    mapping_file = st.file_uploader("계열확인(수업료 포함) 파일 업로드", type=['xlsx'])
with col2:
    student_file = st.file_uploader("학생 기초 데이터(2.xlsx) 업로드", type=['xlsx'])

if mapping_file and student_file:
    # 데이터 로드
    mapping_df = pd.read_excel(mapping_file)
    student_df = pd.read_excel(student_file)
    mapping_dict = mapping_df.set_index('대학').to_dict(orient='index')

    # 매핑 함수
    def get_info(college):
        info = mapping_dict.get(college, {'계열': '기타', '수업료': 0})
        return pd.Series([info['계열'], info['수업료']])

    student_df[['계열', '수업료']] = student_df['대학'].apply(get_info)

    # 3. 필터링
    eligible_df = student_df[
        (student_df['등록학기수'] < 8) &
        (student_df['포기전 최종학기 취득학점'] >= 12) &
        (student_df['국적'] != '대한민국') &
        (student_df['추천기관'] != '국립국제교육원') &
        (student_df['포기전 최종학기 평점평균'] >= 3.0)
    ].copy()

    T = len(eligible_df)
    
    # 4. 등급별 쿼터 산출 (올림)
    quotas = {
        '100%': (np.ceil(T / 65), 1.0),
        '60%': (np.ceil(T / 24), 0.6),
        '30%': (np.ceil(T / 20), 0.3),
        '10%': (np.ceil(T / 12), 0.1)
    }

    # 5. 계열 비율 및 선발
    group_ratios = eligible_df['계열'].value_counts() / T
    final_list = []

    for group in group_ratios.index:
        group_df = eligible_df[eligible_df['계열'] == group].sort_values(by='포기전 최종학기 평점평균', ascending=False)
        ratio = group_ratios[group]
        
        for grade, (total_q, rate) in quotas.items():
            g_quota = int(round(total_q * ratio))
            if g_quota == 0: continue
            
            temp_top = group_df.head(g_quota)
            if not temp_top.empty:
                cut_off_gpa = temp_top.iloc[-1]['포기전 최종학기 평점평균']
                selected = group_df[group_df['포기전 최종학기 평점평균'] >= cut_off_gpa].copy()
                selected = selected[~selected['학번'].isin([s['학번'] for s in final_list])]
                
                for _, row in selected.iterrows():
                    student_data = row.to_dict()
                    student_data['장학등급'] = grade
                    student_data['수혜금액'] = int(row['수업료'] * rate)
                    final_list.append(student_data)
                
                group_df = group_df[~group_df['학번'].isin(selected['학번'])]

    # 6. 결과 전시
    final_df = pd.DataFrame(final_list)
    total_spent = final_df['수혜금액'].sum()

    st.subheader("2. 산출 결과 요약")
    m1, m2, m3 = st.columns(3)
    m1.metric("총 유효 대상자", f"{T}명")
    m2.metric("실제 집행액", f"{total_spent:,}원")
    
    if total_spent > total_budget_limit:
        st.error(f"⚠️ 예산 초과: {total_spent - total_budget_limit:,}원이 더 필요합니다.")
    else:
        st.success(f"✅ 예산 안정권: {total_budget_limit - total_spent:,}원의 여유가 있습니다.")

    st.dataframe(final_df[['계열', '대학', '학과', '학번', '성명', '포기전 최종학기 평점평균', '장학등급', '수혜금액']])

    # 7. 엑셀 다운로드 버튼
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        final_df.to_excel(writer, index=False, sheet_name='Sheet1')
    
    st.download_button(
        label="📥 최종 결과 엑셀 다운로드",
        data=output.getvalue(),
        file_name="장학금_선발_결과.xlsx",
        mime="application/vnd.ms-excel"
    )