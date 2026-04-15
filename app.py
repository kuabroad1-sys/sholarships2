import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# 웹 페이지 설정
st.set_page_config(page_title="장학금 관리 시스템", layout="wide")

st.title("🎓 외국인 장학금 수혜 대상자 산출 시스템")

# 1. 사이드바 설정: 예산 및 비율 입력
st.sidebar.header("⚙️ 시스템 설정")
total_budget_limit = st.sidebar.number_input("전체 예산(원)", value=500000000, step=10000000)

st.sidebar.markdown("---")
st.sidebar.subheader("📊 선발 인원 비율 설정 (1/n)")
n_100 = st.sidebar.number_input("100% 장학 기준 (1/n)", value=65)
n_60 = st.sidebar.number_input("60% 장학 기준 (1/n)", value=24)
n_30 = st.sidebar.number_input("30% 장학 기준 (1/n)", value=20)
n_10 = st.sidebar.number_input("10% 장학 기준 (1/n)", value=12)

# 2. 파일 업로드 섹션
st.subheader("1. 데이터 업로드")
col1, col2 = st.columns(2)
with col1:
    mapping_file = st.file_uploader("계열확인(수업료 포함) 파일 업로드", type=['xlsx'])
with col2:
    student_file = st.file_uploader("학생 기초 데이터(2.xlsx) 업로드", type=['xlsx'])

st.markdown("---")

# 3. 분석 시작 버튼 (파일이 둘 다 있을 때만 활성화)
start_button = False
if mapping_file is not None and student_file is not None:
    start_button = st.button("🚀 장학금 산출 시작", use_container_width=True)
else:
    st.info("💡 위에서 두 종류의 엑셀 파일을 모두 업로드해야 시작 버튼이 나타납니다.")

# 4. 버튼을 눌렀을 때만 로직 실행
if start_button:
    with st.spinner('데이터를 분석하여 장학 대상자를 산출 중입니다...'):
        # 데이터 로드
        mapping_df = pd.read_excel(mapping_file)
        student_df = pd.read_excel(student_file)
        
        # 대학명을 키로 하는 매핑 정보 생성
        mapping_dict = mapping_df.set_index('대학').to_dict(orient='index')

        def get_info(college):
            info = mapping_dict.get(college, {'계열': '기타', '수업료': 0})
            return pd.Series([info['계열'], info['수업료']])

        # 학생 데이터에 계열 및 수업료 매칭
        student_df[['계열', '수업료']] = student_df['대학'].apply(get_info)

        # 3. 필터링 로직 (제외 조건 적용)
        eligible_df = student_df[
            (student_df['등록학기수'] < 8) &
            (student_df['포기전 최종학기 취득학점'] >= 12) &
            (student_df['국적'] != '대한민국') &
            (student_df['추천기관'] != '국립국제교육원') &
            (student_df['포기전 최종학기 평점평균'] >= 3.0)
        ].copy()

        T = len(eligible_df)
        
        # 4. 등급별 총 쿼터 계산 (올림 처리)
        quotas = {
            '100%': (np.ceil(T / n_100) if n_100 > 0 else 0, 1.0),
            '60%': (np.ceil(T / n_60) if n_60 > 0 else 0, 0.6),
            '30%': (np.ceil(T / n_30) if n_30 > 0 else 0, 0.3),
            '10%': (np.ceil(T / n_10) if n_10 > 0 else 0, 0.1)
        }

        # 5. 계열별 비율 및 선발 로직
        group_ratios = eligible_df['계열'].value_counts() / T
        final_list = []
        cutoffs = []

        available_groups = mapping_df['계열'].unique()

        for group in available_groups:
            if group not in group_ratios:
                continue
                
            group_df = eligible_df[eligible_df['계열'] == group].sort_values(by='포기전 최종학기 평점평균', ascending=False)
            ratio = group_ratios[group]
            
            for grade, (total_q, rate) in quotas.items():
                g_quota = int(round(total_q * ratio))
                if g_quota <= 0:
                    cutoffs.append({'계열': group, '등급': grade, '최저학점': '대상없음'})
                    continue
                
                temp_top = group_df.head(g_quota)
                if not temp_top.empty:
                    last_student = temp_top.iloc[-1]
                    cut_off_gpa = last_student['포기전 최종학기 평점평균']
                    
                    selected = group_df[group_df['포기전 최종학기 평점평균'] >= cut_off_gpa].copy()
                    selected = selected[~selected['학번'].isin([s['학번'] for s in final_list])]
                    
                    for _, row in selected.iterrows():
                        student_data = row.to_dict()
                        student_data['장학등급'] = grade
                        student_data['수혜금액'] = int(row['수업료'] * rate)
                        final_list.append(student_data)
                    
                    cutoffs.append({'계열': group, '등급': grade, '최저학점': f"{cut_off_gpa:.2f}"})
                    group_df = group_df[~group_df['학번'].isin(selected['학번'])]
                else:
                    cutoffs.append({'계열': group, '등급': grade, '최저학점': '대상없음'})

        # 6. 결과 시각화 및 요약
        final_df = pd.DataFrame(final_list)
        total_spent = final_df['수혜금액'].sum() if not final_df.empty else 0

        st.subheader("2. 선발 결과 요약")
        m1, m2, m3 = st.columns(3)
        m1.metric("총 대상 인원", f"{T}명")
        m2.metric("실제 집행액", f"{total_spent:,}원")
        budget_usage = (total_spent / total_budget_limit * 100) if total_budget_limit > 0 else 0
        m3.metric("예산 대비", f"{budget_usage:.1f}%")

        if total_spent > total_budget_limit:
            st.error(f"⚠️ 예산 초과: {total_spent - total_budget_limit:,}원이 부족합니다.")
        else:
            st.success(f"✅ 예산 안정권: {total_budget_limit - total_spent:,}원의 여유가 있습니다.")

        # 7. 계열별 커트라인 표 표시
        st.subheader("📍 계열별 선발 커트라인 (최저 학점)")
        if cutoffs:
            cutoff_df = pd.DataFrame(cutoffs)
            cutoff_pivot = cutoff_df.pivot(index='계열', columns='등급', values='최저학점')
            grade_order = [g for g in ['100%', '60%', '30%', '10%'] if g in cutoff_pivot.columns]
            st.table(cutoff_pivot[grade_order])

        # 8. 상세 명단 출력 및 엑셀 다운로드
        st.subheader("3. 상세 수혜자 명단")
        if not final_df.empty:
            display_cols = ['계열', '대학', '학과', '학번', '성명', '포기전 최종학기 평점평균', '장학등급', '수혜금액']
            existing_cols = [c for c in display_cols if c in final_df.columns]
            st.dataframe(final_df[existing_cols])

            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False, sheet_name='선발명단')
                if cutoffs:
                    cutoff_pivot.to_excel(writer, sheet_name='커트라인정보')
            
            st.download_button(
                label="📥 결과 엑셀 다운로드",
                data=output.getvalue(),
                file_name="장학금_선발_최종결과.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("선발 조건에 맞는 학생이 없습니다.")